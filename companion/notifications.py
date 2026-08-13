from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass(slots=True)
class Notification:
    text: str
    created_at: float
    expires_at: float


class NotificationCenter:
    def __init__(self) -> None:
        self._items: list[Notification] = []
        self._last_discord_call = False
        self._last_battery_bucket: int | None = None

    def push(self, text: str, seconds: float = 5.0) -> None:
        now = time.monotonic()
        self._items.append(
            Notification(
                text=text,
                created_at=now,
                expires_at=now + max(1.0, seconds),
            )
        )
        self._items = self._items[-8:]

    def update_status(
        self,
        *,
        discord_call: bool,
        battery_present: bool,
        battery_percent: int,
        battery_charging: bool,
    ) -> None:
        if discord_call and not self._last_discord_call:
            self.push("Discord call connected")
        elif self._last_discord_call and not discord_call:
            self.push("Discord call ended")

        self._last_discord_call = discord_call

        if battery_present:
            bucket = int(battery_percent) // 10
            if (
                self._last_battery_bucket is not None
                and bucket < self._last_battery_bucket
                and battery_percent <= 20
                and not battery_charging
            ):
                self.push(f"Battery low: {battery_percent}%")
            self._last_battery_bucket = bucket

    def active(self) -> list[Notification]:
        now = time.monotonic()
        self._items = [
            item for item in self._items
            if item.expires_at > now
        ]
        return list(self._items)

    def latest_text(self) -> str:
        items = self.active()
        return items[-1].text if items else ""
