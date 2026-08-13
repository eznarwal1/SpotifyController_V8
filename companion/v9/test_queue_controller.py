from __future__ import annotations

from types import SimpleNamespace

from ui_state import AppState

from v9.queue_controller import QueueController


class FakeBridge:
    def __init__(self, queue):
        self.items = list(queue)
        self.activated = []

    def selected_or_playing_queue(self):
        return list(self.items)

    def selected_queue_status(self):
        return "Spotify Web", True, "available"

    def activate_queue_item(self, index):
        self.activated.append(index)
        return True


class FakeSpotify:
    def __init__(self, queue):
        self._chrome_bridge = FakeBridge(queue)


class FakeV8:
    def __init__(self):
        self.state = SimpleNamespace(
            view="queue",
            queue_index=0,
        )


def build(queue):
    spotify = FakeSpotify(queue)
    state = AppState()
    v8 = FakeV8()
    return QueueController(spotify, state, v8), spotify, state, v8


def test_window_and_move() -> None:
    controller, _spotify, state, v8 = build(
        ["A", "B", "C", "D", "E", "F"]
    )

    controller.refresh_window()
    assert state.queue_entries == ["A", "B", "C", "D"]
    assert state.queue_selected_index == 0

    assert controller.move(1)
    assert v8.state.queue_index == 1

    assert controller.move(1)
    assert controller.move(1)
    assert v8.state.queue_index == 3
    assert state.queue_entries == ["C", "D", "E", "F"]
    assert state.queue_selected_index == 1


def test_home_and_select() -> None:
    controller, spotify, _state, v8 = build(
        ["A", "B", "C"]
    )

    controller.move(2)
    assert v8.state.queue_index == 2

    success, index = controller.select_current()
    assert success
    assert index == 2
    assert spotify._chrome_bridge.activated == [2]

    controller.home()
    assert v8.state.queue_index == 0


def test_follow_after_queue_shift() -> None:
    controller, spotify, _state, v8 = build(
        ["A", "B", "C", "D"]
    )

    controller.refresh_window()
    controller.move(2)
    assert v8.state.queue_index == 2

    spotify._chrome_bridge.items = ["B", "C", "D", "E"]
    controller.refresh_window()
    assert v8.state.queue_index == 1


if __name__ == "__main__":
    test_window_and_move()
    test_home_and_select()
    test_follow_after_queue_shift()
    print("V9.13D queue controller tests passed.")
