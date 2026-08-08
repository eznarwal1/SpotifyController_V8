from __future__ import annotations

from dataclasses import dataclass

from audio_mixer import ApplicationMixer
from themes import ThemeManager


VIEWS = (
    "now_playing",
    "queue",
    "mixer",
    "themes",
)


@dataclass(slots=True)
class V8State:
    view: str = "now_playing"
    queue_index: int = 0
    mixer_index: int = 0


class V8Controller:
    def __init__(self) -> None:
        self.state = V8State()
        self.mixer = ApplicationMixer()
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
        elif self.state.view == "mixer":
            count = len(self.mixer.sessions())
            if count:
                self.state.mixer_index = (
                    self.state.mixer_index + amount
                ) % count
        elif self.state.view == "themes":
            self.themes.move(amount)

    def activate(self) -> str:
        if self.state.view == "queue":
            return f"queue_play:{self.state.queue_index}"
        if self.state.view == "mixer":
            self.mixer.toggle_mute(self.state.mixer_index)
            return "mixer_mute"
        if self.state.view == "themes":
            return f"theme:{self.themes.apply_selected()}"
        return "none"

    def change_volume(self, amount: int) -> bool:
        if self.state.view != "mixer":
            return False
        return self.mixer.change_volume(
            self.state.mixer_index,
            amount,
        )

