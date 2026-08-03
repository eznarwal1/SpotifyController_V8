from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pycaw.pycaw import AudioUtilities


@dataclass(slots=True)
class MixerSession:
    key: str
    name: str
    volume: int
    muted: bool
    session_count: int = 1


class ApplicationMixer:
    """
    Windows per-application mixer using stable process keys.

    Duplicate sessions from the same process are grouped, expired sessions are
    filtered, and volume/mute changes are applied to every active session in
    the selected group.
    """

    @staticmethod
    def _session_name(session: Any) -> str:
        process = getattr(session, "Process", None)

        if process is not None:
            try:
                return process.name()
            except Exception:
                pass

        display = str(getattr(session, "DisplayName", "") or "").strip()
        return display or "System audio"

    @staticmethod
    def _process_id(session: Any) -> int:
        process = getattr(session, "Process", None)

        if process is not None:
            try:
                return int(process.pid)
            except Exception:
                pass

        return 0

    @staticmethod
    def _is_usable(session: Any) -> bool:
        simple = getattr(session, "SimpleAudioVolume", None)
        if simple is None:
            return False

        control = getattr(session, "_ctl", None)
        if control is not None:
            try:
                # 0 inactive, 1 active, 2 expired. Keep active and inactive,
                # but never keep expired sessions.
                if int(control.GetState()) == 2:
                    return False
            except Exception:
                pass

        return True

    def _group_key(self, session: Any) -> str:
        name = self._session_name(session)
        pid = self._process_id(session)
        return f"{pid}:{name.casefold()}"

    def _groups(self) -> dict[str, list[Any]]:
        groups: dict[str, list[Any]] = {}

        try:
            sessions = AudioUtilities.GetAllSessions()
        except Exception:
            return groups

        for session in sessions:
            if not self._is_usable(session):
                continue

            key = self._group_key(session)
            groups.setdefault(key, []).append(session)

        return groups

    def sessions(self) -> list[MixerSession]:
        result: list[MixerSession] = []

        for key, group in self._groups().items():
            volumes: list[float] = []
            muted_states: list[bool] = []

            for session in group:
                simple = session.SimpleAudioVolume
                try:
                    volumes.append(float(simple.GetMasterVolume()))
                    muted_states.append(bool(simple.GetMute()))
                except Exception:
                    continue

            if not volumes:
                continue

            name = self._session_name(group[0])
            result.append(
                MixerSession(
                    key=key,
                    name=name,
                    volume=max(
                        0,
                        min(100, round(sum(volumes) / len(volumes) * 100)),
                    ),
                    muted=all(muted_states) if muted_states else False,
                    session_count=len(volumes),
                )
            )

        result.sort(key=lambda item: (item.name.casefold(), item.key))
        return result

    def _selected_key(self, selected_index: int) -> str | None:
        visible = self.sessions()
        if not visible:
            return None
        return visible[selected_index % len(visible)].key

    def change_volume(self, selected_index: int, amount: int) -> bool:
        key = self._selected_key(selected_index)
        if key is None:
            return False

        group = self._groups().get(key, [])
        changed = False

        for session in group:
            simple = session.SimpleAudioVolume

            try:
                current = float(simple.GetMasterVolume())
                target = max(0.0, min(1.0, current + amount / 100.0))
                simple.SetMasterVolume(target, None)
                changed = True
            except Exception:
                continue

        return changed

    def toggle_mute(self, selected_index: int) -> bool:
        key = self._selected_key(selected_index)
        if key is None:
            return False

        group = self._groups().get(key, [])
        current_states: list[bool] = []

        for session in group:
            try:
                current_states.append(
                    bool(session.SimpleAudioVolume.GetMute())
                )
            except Exception:
                continue

        if not current_states:
            return False

        target = not all(current_states)
        changed = False

        for session in group:
            try:
                session.SimpleAudioVolume.SetMute(target, None)
                changed = True
            except Exception:
                continue

        return changed
