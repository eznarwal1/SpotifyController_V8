from __future__ import annotations

from dataclasses import dataclass


DEFAULT_VIEW_ORDER = (
    "now_playing",
    "queue",
    "mixer",
    "discord",
    "themes",
)


@dataclass(slots=True)
class ViewController:
    """
    Pure page-navigation state.

    This module intentionally has no serial, rendering, LVGL, or Spotify
    dependencies so page behavior can be tested without hardware.
    """

    order: tuple[str, ...] = DEFAULT_VIEW_ORDER
    current: str = "now_playing"

    def __post_init__(self) -> None:
        if not self.order:
            raise ValueError("View order cannot be empty.")

        if len(set(self.order)) != len(self.order):
            raise ValueError("View order cannot contain duplicates.")

        if self.current not in self.order:
            self.current = self.order[0]

    def set(self, view: str) -> str:
        if view not in self.order:
            raise ValueError(f"Unknown view: {view}")
        self.current = view
        return self.current

    def home(self) -> str:
        return self.set("now_playing" if "now_playing" in self.order else self.order[0])

    def next(self) -> str:
        index = self.order.index(self.current)
        self.current = self.order[(index + 1) % len(self.order)]
        return self.current

    def previous(self) -> str:
        index = self.order.index(self.current)
        self.current = self.order[(index - 1) % len(self.order)]
        return self.current

    def index(self) -> int:
        return self.order.index(self.current)
