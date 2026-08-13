from __future__ import annotations

import asyncio

from protocol import make_state_message
from serial_manager import SerialManager
from ui_state import AppState

_last_message_by_manager: dict[int, str] = {}


def reset_state_sender(
    serial_manager: SerialManager,
) -> None:
    _last_message_by_manager.pop(id(serial_manager), None)


async def send_state_if_changed(
    serial_manager: SerialManager,
    state: AppState,
    *,
    force: bool = False,
) -> bool:
    """Skip byte-identical JSON state lines while preserving reconnect sends."""
    key = id(serial_manager)

    if not serial_manager.is_connected:
        _last_message_by_manager.pop(key, None)
        return False

    message = make_state_message(state)

    if not force and _last_message_by_manager.get(key) == message:
        return False

    result = await asyncio.to_thread(
        serial_manager.send_line,
        message,
    )

    if result is False:
        return False

    _last_message_by_manager[key] = message
    return True
