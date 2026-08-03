from __future__ import annotations

from serial_manager import SerialManager


def main() -> None:
    ports = SerialManager.list_available_ports()

    print("Available serial ports:")

    if not ports:
        print("  None found.")
    else:
        for device, description in ports:
            print(f"  {device}: {description}")

    serial_manager = SerialManager()
    connected = serial_manager.connect()

    print()
    print(f"Connected: {connected}")
    print(f"Selected port: {serial_manager.port_name}")

    serial_manager.disconnect()


if __name__ == "__main__":
    main()