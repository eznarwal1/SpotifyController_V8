from __future__ import annotations

import json
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent
THEMES_PATH = BASE_DIR / "themes.json"
SETTINGS_PATH = BASE_DIR / "v8_settings.json"


class ThemeManager:
    def __init__(self) -> None:
        self._themes = json.loads(
            THEMES_PATH.read_text(encoding="utf-8")
        )
        self._keys = list(self._themes)
        self._selected_index = 0
        self._active_key = self._load_active_key()

    def _load_active_key(self) -> str:
        try:
            settings = json.loads(
                SETTINGS_PATH.read_text(encoding="utf-8")
            )
            key = str(settings.get("theme", "default"))
            if key in self._themes:
                return key
        except Exception:
            pass
        return "default"

    def _save(self) -> None:
        SETTINGS_PATH.write_text(
            json.dumps({"theme": self._active_key}, indent=2),
            encoding="utf-8",
        )

    def themes(self) -> list[tuple[str, dict[str, Any]]]:
        return [(key, self._themes[key]) for key in self._keys]

    def selected_index(self) -> int:
        return self._selected_index

    def move(self, amount: int) -> None:
        if not self._keys:
            return
        self._selected_index = (
            self._selected_index + amount
        ) % len(self._keys)

    def apply_selected(self) -> str:
        self._active_key = self._keys[self._selected_index]
        self._save()
        return self._active_key

    def active(self) -> dict[str, Any]:
        return self._themes[self._active_key]

    def selected(self) -> tuple[str, dict[str, Any]]:
        key = self._keys[self._selected_index]
        return key, self._themes[key]
