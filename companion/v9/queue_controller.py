from __future__ import annotations

from dataclasses import dataclass

from spotify_controller import SpotifyController
from ui_state import AppState
from v8_controller import V8Controller
from v9.queue_window import (
    build_queue_window,
    find_preserved_selection,
)


@dataclass(slots=True)
class QueueFollowState:
    previous_queue: tuple[str, ...] = ()
    selected_track: str = ""
    manual_navigation: bool = False


class QueueController:
    """Own Queue browsing, follow-mode, windowing, and activation."""

    def __init__(
        self,
        spotify: SpotifyController,
        state: AppState,
        v8: V8Controller,
    ) -> None:
        self.spotify = spotify
        self.state = state
        self.v8 = v8
        self.follow = QueueFollowState()

    def queue(self) -> list[str]:
        return self.spotify._chrome_bridge.selected_or_playing_queue()

    def refresh_window(self) -> tuple[list[str], int]:
        queue = self.queue()

        (
            queue_source,
            _queue_available,
            _queue_status,
        ) = self.spotify._chrome_bridge.selected_queue_status()

        if not queue:
            self.v8.state.queue_index = 0
            self.state.queue_source = queue_source
            self.state.queue_entries = []
            self.state.queue_selected_index = 0
            self.follow = QueueFollowState()
            return queue, 0

        queue_tuple = tuple(queue)
        queue_changed = (
            bool(self.follow.previous_queue)
            and queue_tuple != self.follow.previous_queue
        )

        if queue_changed:
            if not self.follow.manual_navigation:
                self.v8.state.queue_index = 0
            elif self.follow.selected_track:
                self.v8.state.queue_index = find_preserved_selection(
                    self.follow.selected_track,
                    self.v8.state.queue_index,
                    queue,
                )

        window = build_queue_window(
            queue,
            self.v8.state.queue_index,
            visible_rows=4,
            preferred_rows_above=1,
        )

        self.v8.state.queue_index = window.global_selected_index
        self.state.queue_entries = list(window.rows)
        self.state.queue_selected_index = window.local_selected_index
        self.state.queue_source = (
            f"{queue_source}  "
            f"{window.global_selected_index + 1}/{window.total}"
            if queue_source
            else f"{window.global_selected_index + 1}/{window.total}"
        )

        self.follow.previous_queue = queue_tuple
        self.follow.selected_track = queue[
            window.global_selected_index
        ]

        return queue, window.global_selected_index

    def home(self) -> bool:
        queue = self.queue()
        self.v8.state.queue_index = 0
        self.follow.manual_navigation = False
        self.follow.selected_track = ""
        self.refresh_window()
        return bool(queue)

    def move(self, delta: int) -> bool:
        queue = self.queue()

        if not queue:
            self.refresh_window()
            return False

        self.follow.manual_navigation = True
        self.v8.state.queue_index = max(
            0,
            min(
                self.v8.state.queue_index + int(delta),
                len(queue) - 1,
            ),
        )
        self.refresh_window()
        return True

    def select_current(self) -> tuple[bool, int]:
        queue = self.queue()

        if not queue:
            return False, 0

        index = max(
            0,
            min(self.v8.state.queue_index, len(queue) - 1),
        )

        success = self.spotify._chrome_bridge.activate_queue_item(
            index
        )

        if success:
            self.follow.manual_navigation = False
            self.follow.selected_track = ""

        return success, index
