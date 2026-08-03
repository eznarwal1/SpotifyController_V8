from __future__ import annotations

from dataclasses import dataclass

from mixer_model import build_mixer_state


@dataclass
class Session:
    name: str
    volume: int
    muted: bool


def main() -> None:
    state = build_mixer_state(
        [
            Session("Spotify.exe", 81, False),
            Session("chrome.exe", 44, True),
        ],
        selected_index=99,
    )

    assert state.selected_index == 1
    assert state.entries[0].display_text == "Spotify.exe  81%"
    assert state.entries[1].display_text == "chrome.exe  44% [Muted]"

    print("V9 native-mixer state test passed.")


if __name__ == "__main__":
    main()