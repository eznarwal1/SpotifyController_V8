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


if __name__ == "__main__":
    test_manual_session_survives_title_change()
    print("Source-selection regression test passed.")
