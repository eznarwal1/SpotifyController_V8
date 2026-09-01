from __future__ import annotations

from dataclasses import dataclass

from themes import ThemeManager

VIEWS = (
    "now_playing",
    "lyrics",
    "queue",
    "discord",
    # "themes" page removed
)


@dataclass(slots=True)
class V8State:
    view: str = "now_playing"
    queue_index: int = 0


class V8Controller:
    def __init__(self) -> None:
        self.state = V8State()
        self.themes = ThemeManager()

    def next_view(self) -> str:
        index = VIEWS.index(self.state.view)
        self.state.view = VIEWS[(index + 1) % len(VIEWS)]
        return self.state.view

    def now_playing(self) -> None:
        self.state.view = "now_playing"

    def move_selection(self, amount: int) -> None:
        if self.state.view == "queue":
            self.state.queue_index = max(
                0,
                self.state.queue_index + amount,
            )
        # themes page removed: keep ThemeManager available for rendering

    def activate(self) -> str:
        if self.state.view == "queue":
            return f"queue_play:{self.state.queue_index}"
        # themes page removed
        return "none"

    def change_volume(self, amount: int) -> bool:
        # No mixer view available; delegate volume changes to global handlers.
        return False

