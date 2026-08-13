from __future__ import annotations

import asyncio

from ui_state import AppState

from v9.state_sender import reset_state_sender, send_state_if_changed


class FakeSerial:
    def __init__(self) -> None:
        self.is_connected = True
        self.lines: list[str] = []

    def send_line(self, line: str):
        self.lines.append(line)
        return True


async def exercise() -> None:
    serial = FakeSerial()
    state = AppState()

    assert await send_state_if_changed(serial, state)
    assert len(serial.lines) == 1
    assert not await send_state_if_changed(serial, state)
    assert len(serial.lines) == 1

    state.volume = 37
    assert await send_state_if_changed(serial, state)
    assert len(serial.lines) == 2

    serial.is_connected = False
    assert not await send_state_if_changed(serial, state)

    serial.is_connected = True
    assert await send_state_if_changed(serial, state)
    assert len(serial.lines) == 3

    reset_state_sender(serial)
    assert await send_state_if_changed(serial, state)
    assert len(serial.lines) == 4


if __name__ == "__main__":
    asyncio.run(exercise())
    print("V9.13C state sender tests passed.")
