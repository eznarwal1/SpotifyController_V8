from __future__ import annotations

from protocol import make_state_message, parse_command_message
from ui_state import AppState, MediaState


def main() -> None:
    state = AppState(
        media=MediaState(
            application="Spotify.exe",
            title="Test Song",
            artist="Test Artist",
            album="Test Album",
            playback_status="Playing",
            position_seconds=65,
            duration_seconds=240,
            shuffle_active=False,
            repeat_mode="List",
        ),
        volume=42,
        muted=False,
        spotify_connected=True,
    )

    state_message = make_state_message(state)

    print("State message sent to ESP32:")
    print(state_message)

    sample_commands = [
        '{"type":"command","command":"play_pause"}',
        '{"type":"command","command":"repeat"}',
        '{"type":"command","command":"volume","amount":2}',
        '{"type":"command","command":"volume","amount":-2}',
        '{"type":"command","command":"mute"}',
        '{"type":"event","event":"view_applied"}',
        'not valid json',
    ]

    print("Parsed ESP32 commands:")

    for raw_command in sample_commands:
        parsed = parse_command_message(raw_command)
        print(f"{raw_command} -> {parsed}")

    assert parse_command_message(
        '{"type":"event","event":"view_applied"}'
    ) == {"type": "event", "event": "view_applied"}
    assert parse_command_message('{"type":"event"}') is None


if __name__ == "__main__":
    main()
