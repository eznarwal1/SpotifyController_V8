from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class QueueWindow:
    rows: tuple[str, ...]
    local_selected_index: int
    global_selected_index: int
    start_index: int
    total: int


def clamp_index(index: int, total: int) -> int:
    if total <= 0:
        return 0
    return max(0, min(int(index), total - 1))


def build_queue_window(
    entries: list[str] | tuple[str, ...],
    selected_index: int,
    *,
    visible_rows: int = 4,
    preferred_rows_above: int = 1,
) -> QueueWindow:
    """
    Build the stable display window for a large Queue.

    The ESP32 can keep a fixed number of LVGL rows while the PC tracks the
    global Queue index.
    """
    if visible_rows <= 0:
        raise ValueError("visible_rows must be positive.")

    items = tuple(str(item) for item in entries if str(item).strip())
    total = len(items)

    if total == 0:
        return QueueWindow(
            rows=(),
            local_selected_index=0,
            global_selected_index=0,
            start_index=0,
            total=0,
        )

    selected = clamp_index(selected_index, total)
    max_start = max(0, total - visible_rows)

    start = max(
        0,
        min(
            selected - max(0, preferred_rows_above),
            max_start,
        ),
    )

    rows = items[start:start + visible_rows]

    return QueueWindow(
        rows=rows,
        local_selected_index=selected - start,
        global_selected_index=selected,
        start_index=start,
        total=total,
    )


def find_preserved_selection(
    previous_selected_track: str,
    previous_index: int,
    new_queue: list[str] | tuple[str, ...],
) -> int:
    """
    Preserve the same selected track across a Queue refresh when possible.

    If duplicate titles exist, choose the matching item closest to the previous
    global index.
    """
    items = tuple(new_queue)
    if not items:
        return 0

    if previous_selected_track:
        matches = [
            index
            for index, item in enumerate(items)
            if item == previous_selected_track
        ]
        if matches:
            return min(matches, key=lambda index: abs(index - previous_index))

    return clamp_index(previous_index, len(items))
