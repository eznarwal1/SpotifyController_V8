from __future__ import annotations

from queue_model import QueueEntry, normalize_queue_entries


def main() -> None:
    entries = normalize_queue_entries(
        [
            {"title": "Song One", "artist": "Artist A"},
            ("Song Two", "Artist B"),
            "Song Three - Artist C",
            "Song One - Artist A",
            {"title": "   ", "artist": "Ignored"},
        ]
    )

    assert entries == [
        QueueEntry("Song One", "Artist A"),
        QueueEntry("Song Two", "Artist B"),
        QueueEntry("Song Three", "Artist C"),
    ]
    assert entries[0].display_text == "Song One - Artist A"
    assert QueueEntry("Instrumental").display_text == "Instrumental"

    print("V9 queue-model test passed.")


if __name__ == "__main__":
    main()
