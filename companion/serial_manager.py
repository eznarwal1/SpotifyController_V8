from __future__ import annotations

import asyncio
import json
import threading
import time
from typing import Any

import serial
from serial import SerialException, SerialTimeoutException
from serial.tools import list_ports

from protocol import (
    make_artwork_packet,
    make_background_packet,
    make_metadata_packet,
    make_source_packet,
    make_view_packet,
    parse_command_message,
)


class SerialManager:
    """Manage and automatically reconnect the USB serial display."""

    READY_PROTOCOL = 2

    def __init__(
        self,
        port: str | None = None,
        baudrate: int = 2000000,
    ) -> None:
        self._preferred_port = port
        self._baudrate = baudrate
        self._serial: serial.Serial | None = None
        self._last_port: str | None = None
        self._write_lock = threading.Lock()

    @property
    def is_connected(self) -> bool:
        return self._serial is not None and self._serial.is_open

    @property
    def port_name(self) -> str | None:
        if self._serial is not None:
            return self._serial.port
        return self._last_port

    @staticmethod
    def list_available_ports() -> list[tuple[str, str]]:
        return [
            (port.device, port.description or "Unknown device")
            for port in list_ports.comports()
        ]

    @staticmethod
    def _looks_like_display(port: Any) -> bool:
        likely_terms = (
            "esp32",
            "usb serial",
            "usb-serial",
            "cp210",
            "ch340",
            "ch910",
            "jtag",
            "uart",
        )
        searchable = " ".join(
            [
                getattr(port, "device", "") or "",
                getattr(port, "description", "") or "",
                getattr(port, "manufacturer", "") or "",
                getattr(port, "product", "") or "",
            ]
        ).lower()
        return any(term in searchable for term in likely_terms)

    def _candidate_ports(self) -> list[str]:
        if self._preferred_port:
            return [self._preferred_port]

        ports = list(list_ports.comports())
        likely = [port.device for port in ports if self._looks_like_display(port)]
        other = [port.device for port in ports if port.device not in likely]

        if self._last_port in likely:
            likely.remove(self._last_port)
            likely.insert(0, self._last_port)
        elif self._last_port in other:
            other.remove(self._last_port)
            other.insert(0, self._last_port)

        return likely + other

    @staticmethod
    def _is_ready_message(line: str) -> bool:
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            return False

        return (
            isinstance(message, dict)
            and message.get("type") == "ready"
            and int(message.get("protocol", 0)) == SerialManager.READY_PROTOCOL
        )

    def _open_port(self, port: str) -> serial.Serial | None:
        try:
            connection = serial.Serial(
                port=port,
                baudrate=self._baudrate,
                timeout=0.10,
                write_timeout=5,
            )
        except (SerialException, OSError):
            return None

        deadline = time.monotonic() + 3.0
        saw_valid_text = False

        try:
            while time.monotonic() < deadline:
                raw = connection.readline()
                if not raw:
                    continue

                try:
                    line = raw.decode("utf-8").strip()
                except UnicodeDecodeError:
                    continue

                if not line:
                    continue

                saw_valid_text = True
                if self._is_ready_message(line):
                    connection.reset_input_buffer()
                    return connection

            if port == self._last_port and saw_valid_text:
                connection.reset_input_buffer()
                return connection

        except (SerialException, SerialTimeoutException, OSError):
            pass

        try:
            connection.close()
        except OSError:
            pass
        return None

    def connect(self) -> bool:
        if self.is_connected:
            return True

        for port in self._candidate_ports():
            connection = self._open_port(port)
            if connection is None:
                continue

            self._serial = connection
            self._last_port = port
            return True

        likely_ports = [
            port.device
            for port in list_ports.comports()
            if self._looks_like_display(port)
        ]
        if len(likely_ports) == 1:
            try:
                self._serial = serial.Serial(
                    port=likely_ports[0],
                    baudrate=self._baudrate,
                    timeout=0.10,
                    write_timeout=5,
                )
                self._last_port = likely_ports[0]
                time.sleep(0.20)
                self._serial.reset_input_buffer()
                return True
            except (SerialException, OSError):
                self._serial = None

        return False

    def disconnect(self) -> None:
        if self._serial is not None:
            try:
                if self._serial.is_open:
                    self._serial.close()
            finally:
                self._serial = None

    def send_line(self, message: str) -> bool:
        if not self.is_connected or self._serial is None:
            return False

        payload = (message.rstrip("\r\n") + "\n").encode("utf-8")

        try:
            with self._write_lock:
                self._serial.write(payload)
            return True
        except (SerialException, SerialTimeoutException, OSError):
            self.disconnect()
            return False

    def send_artwork(
        self,
        rgb565_bytes: bytes,
        width: int,
        height: int,
        chunk_size: int = 16384,
    ) -> bool:
        packet = make_artwork_packet(rgb565_bytes, width, height)

        if not self.is_connected or self._serial is None:
            return False

        try:
            with self._write_lock:
                for offset in range(0, len(packet), chunk_size):
                    self._serial.write(packet[offset : offset + chunk_size])
                self._serial.flush()
            return True
        except (SerialException, SerialTimeoutException, OSError):
            self.disconnect()
            return False

    def send_metadata_image(
        self,
        rgb565_bytes: bytes,
        width: int,
        height: int,
        chunk_size: int = 16384,
    ) -> bool:
        """Send one PC-rendered metadata panel."""
        packet = make_metadata_packet(rgb565_bytes, width, height)

        if not self.is_connected or self._serial is None:
            return False

        try:
            with self._write_lock:
                for offset in range(0, len(packet), chunk_size):
                    self._serial.write(packet[offset : offset + chunk_size])
                self._serial.flush()
            return True
        except (SerialException, SerialTimeoutException, OSError):
            self.disconnect()
            return False

    def send_source_image(
        self,
        rgb565_bytes: bytes,
        width: int,
        height: int,
        chunk_size: int = 16384,
    ) -> bool:
        """Send one PC-rendered source-selector label."""
        packet = make_source_packet(rgb565_bytes, width, height)

        if not self.is_connected or self._serial is None:
            return False

        try:
            with self._write_lock:
                for offset in range(0, len(packet), chunk_size):
                    self._serial.write(packet[offset : offset + chunk_size])
                self._serial.flush()
            return True
        except (SerialException, SerialTimeoutException, OSError):
            self.disconnect()
            return False

    def send_view_image(
        self,
        rgb565_bytes: bytes,
        width: int,
        height: int,
        chunk_size: int = 16384,
    ) -> bool:
        packet = make_view_packet(rgb565_bytes, width, height)

        if not self.is_connected or self._serial is None:
            return False

        try:
            with self._write_lock:
                for offset in range(0, len(packet), chunk_size):
                    self._serial.write(packet[offset : offset + chunk_size])
                self._serial.flush()
            return True
        except (SerialException, SerialTimeoutException, OSError):
            self.disconnect()
            return False

    def send_background_image(
        self,
        rgb565_bytes: bytes,
        width: int,
        height: int,
        chunk_size: int = 16384,
    ) -> bool:
        packet = make_background_packet(
            rgb565_bytes,
            width,
            height,
        )

        if not self.is_connected or self._serial is None:
            return False

        try:
            with self._write_lock:
                for offset in range(0, len(packet), chunk_size):
                    self._serial.write(
                        packet[offset : offset + chunk_size]
                    )
                self._serial.flush()
            return True
        except (
            SerialException,
            SerialTimeoutException,
            OSError,
        ):
            self.disconnect()
            return False

    def read_command(self) -> dict[str, Any] | None:
        if not self.is_connected or self._serial is None:
            return None

        try:
            raw_bytes = self._serial.readline()
        except (SerialException, OSError):
            self.disconnect()
            return None

        if not raw_bytes:
            return None

        try:
            raw_message = raw_bytes.decode("utf-8").strip()
        except UnicodeDecodeError:
            return None

        return parse_command_message(raw_message)

    async def maintain_connection(
        self,
        stop_event: asyncio.Event,
        retry_seconds: float = 2.0,
    ) -> None:
        while not stop_event.is_set():
            if not self.is_connected:
                await asyncio.to_thread(self.connect)
            await asyncio.sleep(retry_seconds)
