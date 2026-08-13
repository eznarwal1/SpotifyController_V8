from __future__ import annotations

import os
import subprocess
import threading
import time
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import comtypes
    import comtypes.client
    from comtypes import GUID
except Exception as exc:
    logging.debug("discord_desktop: comtypes import failed: %s", exc)
    comtypes = None
    GUID = None


CLSID_CUIAutomation_TEXT = "{FF48DBA4-60EF-4201-AA87-54103EEF594E}"

TREE_SCOPE_CHILDREN = 0x2
TREE_SCOPE_DESCENDANTS = 0x4

UIA_NAME = 30005
UIA_CONTROL_TYPE = 30003
UIA_AUTOMATION_ID = 30011
UIA_CLASS_NAME = 30012

UIA_BUTTON_CONTROL_TYPE = 50000
UIA_LIST_ITEM_CONTROL_TYPE = 50007
UIA_TEXT_CONTROL_TYPE = 50020
UIA_DOCUMENT_CONTROL_TYPE = 50030
UIA_PANE_CONTROL_TYPE = 50033

UIA_INVOKE_PATTERN_ID = 10000


@dataclass(frozen=True)
class DiscordDesktopSnapshot:
    available: bool = False
    accessibility_ready: bool = False
    server: str = ""
    channel: str = ""
    messages: tuple[str, ...] = ()
    voice_connected: bool = False
    muted: bool = False
    deafened: bool = False
    detail: str = ""


def _clean(value: Any) -> str:
    return " ".join(str(value or "").replace("\r", " ").replace("\n", " ").split())


class DiscordDesktopBridge:
    """
    Read/control the visible Discord desktop client through Windows UI Automation.

    Discord is Electron/Chromium. Its renderer accessibility tree must be enabled
    with --force-renderer-accessibility=complete; otherwise Windows sees only the
    outer Chrome_WidgetWin_1 frame.
    """

    def __init__(self, *, poll_seconds: float = 0.75) -> None:
        self._poll_seconds = max(0.35, poll_seconds)
        self._lock = threading.Lock()
        self._snapshot = DiscordDesktopSnapshot()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._pending_command: str | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return

        self._stop.clear()
        self._thread = threading.Thread(
            target=self._worker,
            name="DiscordDesktopBridge",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def snapshot(self) -> DiscordDesktopSnapshot:
        with self._lock:
            return self._snapshot

    def enqueue_command(self, command: str) -> bool:
        if command not in {"discord_mute", "discord_deafen"}:
            return False

        with self._lock:
            if not self._snapshot.accessibility_ready:
                return False
            self._pending_command = command
        return True

    @staticmethod
    def _find_discord_exe() -> Path | None:
        local = Path(os.environ.get("LOCALAPPDATA", ""))
        candidates: list[tuple[str, Path]] = []

        for root_name in ("Discord", "DiscordCanary", "DiscordPTB"):
            root = local / root_name
            if not root.exists():
                continue

            for app_dir in root.glob("app-*"):
                exe = app_dir / "Discord.exe"
                if exe.exists():
                    candidates.append((app_dir.name, exe))

        if not candidates:
            return None

        candidates.sort(reverse=True)
        return candidates[0][1]

    @classmethod
    def launch_accessible_discord(cls) -> tuple[bool, str]:
        exe = cls._find_discord_exe()
        if exe is None:
            return False, "Discord.exe was not found under LOCALAPPDATA."

        try:
            subprocess.Popen(
                [str(exe), "--force-renderer-accessibility=complete"],
                cwd=str(exe.parent),
            )
        except OSError as exc:
            return False, f"Could not launch Discord: {exc}"

        return True, str(exe)

    @staticmethod
    def _prop(element, prop_id: int, default: Any = "") -> Any:
        try:
            value = element.GetCurrentPropertyValue(prop_id)
            return default if value is None else value
        except Exception as exc:
            logging.debug("_prop: GetCurrentPropertyValue failed: %s", exc)
            return default

    @classmethod
    def _name(cls, element) -> str:
        return _clean(cls._prop(element, UIA_NAME, ""))

    @classmethod
    def _class(cls, element) -> str:
        return _clean(cls._prop(element, UIA_CLASS_NAME, ""))

    @classmethod
    def _automation_id(cls, element) -> str:
        return _clean(cls._prop(element, UIA_AUTOMATION_ID, ""))

    @classmethod
    def _control_type(cls, element) -> int:
        try:
            return int(cls._prop(element, UIA_CONTROL_TYPE, 0))
        except Exception as exc:
            logging.debug("_control_type: failed: %s", exc)
            return 0

    @staticmethod
    def _create_uia():
        if comtypes is None or GUID is None:
            raise RuntimeError("comtypes is unavailable")

        module = None
        for candidate in (
            "UIAutomationCore.dll",
            r"C:\Windows\System32\UIAutomationCore.dll",
        ):
            try:
                module = comtypes.client.GetModule(candidate)
                break
            except Exception as exc:
                logging.debug("_create_uia: GetModule candidate %s failed: %s", candidate, exc)
                pass

        interface = getattr(module, "IUIAutomation", None) if module else None

        if interface is None:
            from comtypes.gen import UIAutomationClient
            interface = UIAutomationClient.IUIAutomation

        return comtypes.client.CreateObject(
            GUID(CLSID_CUIAutomation_TEXT),
            interface=interface,
        )

    @classmethod
    def _find_window(cls, uia):
        root = uia.GetRootElement()
        items = root.FindAll(
            TREE_SCOPE_CHILDREN,
            uia.CreateTrueCondition(),
        )

        for index in range(items.Length):
            element = items.GetElement(index)
            name = cls._name(element)
            lower = name.casefold()

            if (
                cls._class(element) == "Chrome_WidgetWin_1"
                and (
                    lower.endswith(" - discord")
                    or lower == "discord"
                )
                and "google chrome" not in lower
                and "microsoft edge" not in lower
            ):
                return element

        return None

    @classmethod
    def _descendants(cls, uia, root):
        return root.FindAll(
            TREE_SCOPE_DESCENDANTS,
            uia.CreateTrueCondition(),
        )

    @classmethod
    def _renderer_accessible(cls, elements) -> bool:
        # v5 showed Discord exposes a RootWebArea Document when forced
        # accessibility is active. Without it the tree contains only ~7 panes.
        for index in range(elements.Length):
            element = elements.GetElement(index)
            if (
                cls._control_type(element) == UIA_DOCUMENT_CONTROL_TYPE
                and cls._automation_id(element) == "RootWebArea"
            ):
                return True
        return False

    @classmethod
    def _channel_info(cls, elements) -> tuple[str, str]:
        server = ""
        channel = ""

        # Strong channel signal from v5: Group name "general (channel)".
        for index in range(elements.Length):
            element = elements.GetElement(index)
            name = cls._name(element)
            if name.casefold().endswith(" (channel)"):
                channel = name[:-10].strip()
                if channel:
                    break

        # Strong header signal from v5: "FRC San Diego: general".
        if channel:
            suffix = f": {channel}".casefold()
            for index in range(elements.Length):
                element = elements.GetElement(index)
                if cls._control_type(element) != UIA_TEXT_CONTROL_TYPE:
                    continue
                name = cls._name(element)
                if name.casefold().endswith(suffix):
                    server = name[: -len(suffix)].strip()
                    break

        # Window title fallback: "#general | Server - Discord".
        if not channel or not server:
            for index in range(elements.Length):
                element = elements.GetElement(index)
                if cls._automation_id(element) != "RootWebArea":
                    continue
                title = cls._name(element)
                if " | " in title:
                    left, right = title.split(" | ", 1)
                    if not channel:
                        channel = left.lstrip("#").strip()
                    if not server:
                        server = right.removesuffix(" - Discord").strip()
                break

        return server, channel

    @classmethod
    def _message_text_from_row(cls, uia, row) -> str:
        """
        Prefer the accessible message Group under each chat-messages-* ListItem.

        v5 exposes rows like:
          ListItem aid=chat-messages-...
          Group name='Author , message text , 7:29 AM'
        """
        try:
            children = row.FindAll(
                TREE_SCOPE_DESCENDANTS,
                uia.CreateTrueCondition(),
            )
        except Exception as exc:
            logging.debug("_message_text_from_row: FindAll failed: %s", exc)
            children = None

        if children is not None:
            best_group = ""
            text_nodes: list[str] = []

            for index in range(children.Length):
                element = children.GetElement(index)
                name = cls._name(element)
                if not name:
                    continue

                control_type = cls._control_type(element)
                class_name = cls._class(element)

                if (
                    control_type in (50026, 50025)
                    and "message__" in class_name
                    and "replying to" not in name.casefold()
                ):
                    best_group = name
                    break

                if control_type == UIA_TEXT_CONTROL_TYPE:
                    lower = name.casefold()
                    if lower in {"add reaction", "edited"}:
                        continue
                    if "saturday," in lower or "sunday," in lower:
                        continue
                    text_nodes.append(name)

            if best_group:
                # Discord group names use " , " separators:
                # Author , message , time
                pieces = [
                    piece.strip()
                    for piece in best_group.split(" , ")
                    if piece.strip()
                ]
                if len(pieces) >= 2:
                    author = pieces[0]
                    body = pieces[1]
                    return f"{author}: {body}"

            # Fallback: compact useful text nodes.
            if text_nodes:
                deduped: list[str] = []
                for value in text_nodes:
                    if value not in deduped:
                        deduped.append(value)

                if len(deduped) >= 2:
                    # Header text often begins "Author Yesterday at ...".
                    author = deduped[0].split(" Yesterday at ", 1)[0]
                    body = deduped[-1]
                    if author and body and author != body:
                        return f"{author}: {body}"

                return deduped[-1]

        return cls._name(row)

    @classmethod
    def _messages(cls, uia, elements) -> tuple[str, ...]:
        rows = []

        for index in range(elements.Length):
            element = elements.GetElement(index)
            if cls._control_type(element) != UIA_LIST_ITEM_CONTROL_TYPE:
                continue

            automation_id = cls._automation_id(element)
            class_name = cls._class(element)

            if not automation_id.startswith("chat-messages-"):
                continue
            if "messageListItem" not in class_name:
                continue

            rows.append(element)

        output: list[str] = []
        for row in rows[-8:]:
            text = _clean(cls._message_text_from_row(uia, row))
            if not text:
                continue
            if text not in output:
                output.append(text)

        return tuple(output[-8:])

    @classmethod
    def _voice_state(cls, elements) -> tuple[bool, bool, bool]:
        voice_connected = False
        muted = False
        deafened = False

        for index in range(elements.Length):
            element = elements.GetElement(index)
            name = cls._name(element)
            lower = name.casefold()
            if not lower:
                continue

            if "voice connected" in lower:
                voice_connected = True

            if lower == "unmute":
                muted = True
            elif lower == "mute":
                # The v5 tree exposed a Mute button plus an Unmute status text
                # while muted. Do not force muted False here; presence of
                # "Unmute" is the stronger state signal.
                pass

            if lower == "undeafen":
                deafened = True

        return voice_connected, muted, deafened

    @classmethod
    def _find_button(cls, elements, labels: set[str]):
        exact = []
        fuzzy = []

        for index in range(elements.Length):
            element = elements.GetElement(index)
            if cls._control_type(element) != UIA_BUTTON_CONTROL_TYPE:
                continue

            name = cls._name(element).casefold()
            if name in labels:
                exact.append(element)
            elif any(label in name for label in labels):
                fuzzy.append(element)

        return exact[-1] if exact else (fuzzy[-1] if fuzzy else None)

    @staticmethod
    def _invoke(element) -> bool:
        if element is None:
            return False

        try:
            from comtypes.gen import UIAutomationClient
            pattern = element.GetCurrentPattern(UIA_INVOKE_PATTERN_ID)
            invoke = pattern.QueryInterface(
                UIAutomationClient.IUIAutomationInvokePattern
            )
            invoke.Invoke()
            return True
        except Exception as exc:
            logging.debug("_invoke: invoke pattern failed: %s", exc)
            return False

    @classmethod
    def _perform_command(cls, elements, command: str) -> bool:
        if command == "discord_mute":
            button = cls._find_button(
                elements,
                {"mute", "unmute", "mute microphone", "unmute microphone"},
            )
            return cls._invoke(button)

        if command == "discord_deafen":
            button = cls._find_button(
                elements,
                {"deafen", "undeafen", "deafen audio", "undeafen audio"},
            )
            return cls._invoke(button)

        return False

    def _set_snapshot(self, snapshot: DiscordDesktopSnapshot) -> None:
        with self._lock:
            self._snapshot = snapshot

    def _take_command(self) -> str | None:
        with self._lock:
            command = self._pending_command
            self._pending_command = None
            return command

    def _worker(self) -> None:
        if comtypes is None:
            self._set_snapshot(
                DiscordDesktopSnapshot(
                    detail="comtypes unavailable",
                )
            )
            return

        try:
            # COM must be initialized in the worker thread.
            comtypes.CoInitialize()
        except Exception as exc:
            logging.debug("DiscordDesktopBridge: CoInitialize failed: %s", exc)

        try:
            uia = self._create_uia()
        except Exception as exc:
            logging.exception("DiscordDesktopBridge: UI Automation init failed")
            self._set_snapshot(
                DiscordDesktopSnapshot(
                    detail=f"UI Automation init failed: {exc}",
                )
            )
            return

        while not self._stop.is_set():
            try:
                window = self._find_window(uia)
                if window is None:
                    self._set_snapshot(
                        DiscordDesktopSnapshot(
                            available=False,
                            detail="Discord desktop window not found",
                        )
                    )
                    self._stop.wait(self._poll_seconds)
                    continue

                elements = self._descendants(uia, window)
                accessible = self._renderer_accessible(elements)

                if not accessible:
                    self._set_snapshot(
                        DiscordDesktopSnapshot(
                            available=True,
                            accessibility_ready=False,
                            detail=(
                                "Discord desktop is running without renderer "
                                "accessibility. Relaunch with "
                                "--force-renderer-accessibility=complete."
                            ),
                        )
                    )
                    self._stop.wait(self._poll_seconds)
                    continue

                command = self._take_command()
                if command is not None:
                    self._perform_command(elements, command)
                    # Give Discord a moment to update its accessibility state.
                    time.sleep(0.08)
                    elements = self._descendants(uia, window)

                server, channel = self._channel_info(elements)
                messages = self._messages(uia, elements)
                voice_connected, muted, deafened = self._voice_state(elements)

                self._set_snapshot(
                    DiscordDesktopSnapshot(
                        available=True,
                        accessibility_ready=True,
                        server=server,
                        channel=channel,
                        messages=messages,
                        voice_connected=voice_connected,
                        muted=muted,
                        deafened=deafened,
                        detail="Discord Desktop",
                    )
                )
            except Exception as exc:
                logging.exception("DiscordDesktopBridge worker loop error")
                self._set_snapshot(
                    DiscordDesktopSnapshot(
                        available=True,
                        detail=f"Discord desktop read error: {exc}",
                    )
                )

            self._stop.wait(self._poll_seconds)


_bridge: DiscordDesktopBridge | None = None


def get_discord_desktop_bridge() -> DiscordDesktopBridge:
    global _bridge

    if _bridge is None:
        _bridge = DiscordDesktopBridge()

    return _bridge
