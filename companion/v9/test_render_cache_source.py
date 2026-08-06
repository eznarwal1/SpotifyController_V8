from __future__ import annotations

from pathlib import Path


def main() -> None:
    repository = Path(__file__).resolve().parents[2]
    source = (
        repository
        / "CrowPanel Firmware"
        / "CrowPanelSpotify V2"
        / "src"
        / "SpotifyUI.cpp"
    ).read_text(encoding="utf-8")

    required = (
        "bool queueStateChanged(",
        "bool mixerStateChanged(",
        "bool statusStateChanged(",
        "if (queueChanged)",
        "if (mixerChanged)",
        "if (metadataChanged)",
        "if (progressChanged)",
    )

    for marker in required:
        assert marker in source, marker

    visibility = source[
        source.index("void SpotifyUI::updatePageVisibility()"):
        source.index("void SpotifyUI::updateNativeQueue()")
    ]
    assert "lv_obj_move_background(backgroundImageObject_);" not in visibility

    print("V9 render-cache source test passed.")


if __name__ == "__main__":
    main()
