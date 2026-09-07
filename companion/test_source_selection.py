from __future__ import annotations

import asyncio
from types import SimpleNamespace

from spotify_controller import SpotifyController


class FakeSession:
    def __init__(self, app_id: str, title: str) -> None:
        self.source_app_user_model_id = app_id
        self.title = title

    async def try_get_media_properties_async(self):
        return SimpleNamespace(title=self.title)


class FakeChromeTab:
    def __init__(self, tab_id: int, label: str) -> None:
        self.tab_id = tab_id
        self.source_label = label


class FakeChromeBridge:
    def __init__(self, tabs: list[FakeChromeTab]) -> None:
        self.tabs = tabs

    def list_tabs(self) -> list[FakeChromeTab]:
        return list(self.tabs)


def test_manual_session_survives_title_change() -> None:
    controller = SpotifyController()
    spotify = FakeSession("Spotify.exe", "First song")
    other = FakeSession("Other.exe", "Other song")
    controller._all_sessions = lambda: [other, spotify]  # type: ignore[method-assign]
    controller._selected_session = spotify  # type: ignore[assignment]
    controller._manual_session_key = ("Spotify.exe", "First song")

    spotify.title = "Second song"
    selected = asyncio.run(controller._select_active_media_session())

    assert selected is spotify
    assert controller._manual_session_key == (
        "Spotify.exe",
        "Second song",
    )


def test_chrome_sources_wrap_without_falling_back_to_auto() -> None:
    controller = SpotifyController()
    spotify = FakeChromeTab(10, "Chrome - Spotify")
    youtube = FakeChromeTab(20, "Chrome - YouTube")
    controller._chrome_bridge = FakeChromeBridge(  # type: ignore[assignment]
        [spotify, youtube]
    )
    controller._all_sessions = lambda: []  # type: ignore[method-assign]
    controller._manual_chrome_tab_id = youtube.tab_id

    selected = asyncio.run(controller.cycle_media_source())

    assert selected == spotify.source_label
    assert controller._manual_chrome_tab_id == spotify.tab_id

    # Playback/title-driven bridge ordering must not affect the next source.
    controller._chrome_bridge.tabs = [youtube, spotify]  # type: ignore[attr-defined]
    selected = asyncio.run(controller.cycle_media_source())

    assert selected == youtube.source_label
    assert controller._manual_chrome_tab_id == youtube.tab_id


if __name__ == "__main__":
    test_manual_session_survives_title_change()
    test_chrome_sources_wrap_without_falling_back_to_auto()
    print("Source-selection regression test passed.")
