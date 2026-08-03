from __future__ import annotations

from queue_protocol import build_queue_state


def main() -> None:
    state = build_queue_state(
        [
            "Song One - Artist A",
            "Song Two - Artist B",
            "夜に駆ける - YOASOBI",
        ],
        source="Spotify Web",
        selected_index=99,
    )

    assert state.source == "Spotify Web"
    assert state.selected_index == 2
    assert state.display_rows() == [
        "Song One - Artist A",
        "Song Two - Artist B",
        "夜に駆ける - YOASOBI",
    ]
    print("V9 native-queue state test passed.")


if __name__ == "__main__":
    main()
