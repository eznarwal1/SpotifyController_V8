from lyrics import LyricLine, Lyrics, parse_synced_lyrics


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


if __name__ == "__main__":
    test_parse_and_sync()
    print("Lyrics tests passed.")
