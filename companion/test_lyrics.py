from lyrics import LyricLine, Lyrics, parse_synced_lyrics, select_best_record


def test_parse_and_sync() -> None:
    parsed = parse_synced_lyrics(
        "[00:10.50]First line\n[00:14.250][00:20.00]Second line"
    )
    assert parsed == (
        LyricLine(10.5, "First line"),
        LyricLine(14.25, "Second line"),
        LyricLine(20.0, "Second line"),
    )
    lyrics = Lyrics(parsed, "")
    assert lyrics.active_index(9) == 0
    assert lyrics.active_index(15) == 1
    assert lyrics.active_index(21) == 2


def test_native_lyrics_preferred_over_romanized() -> None:
    records = [
        {
            "trackName": "Right Now (Romanized)",
            "artistName": "NewJeans",
            "duration": 160,
            "syncedLyrics": "[00:01.00]mada mada",
        },
        {
            "trackName": "Right Now",
            "artistName": "NewJeans",
            "duration": 160,
            "syncedLyrics": "[00:01.00]まだまだ",
        },
    ]
    selected = select_best_record(records, "Right Now", "NewJeans", 160)
    assert selected is records[1]


if __name__ == "__main__":
    test_parse_and_sync()
    test_native_lyrics_preferred_over_romanized()
    print("Lyrics tests passed.")
