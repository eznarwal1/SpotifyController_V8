from __future__ import annotations

from v9.navigation_bridge import V8ViewNavigator, discover_v8_view_order


class FakeState:
    def __init__(self, view: str) -> None:
        self.view = view


class FakeV8:
    def __init__(
        self,
        order=("now_playing", "queue", "mixer", "themes"),
        current="now_playing",
    ) -> None:
        self.order = tuple(order)
        self.state = FakeState(current)

    def next_view(self) -> str:
        index = self.order.index(self.state.view)
        self.state.view = self.order[(index + 1) % len(self.order)]
        return self.state.view


def test_discovery_restores_original() -> None:
    v8 = FakeV8(current="queue")
    assert discover_v8_view_order(v8) == (
        "queue", "mixer", "themes", "now_playing"
    )
    assert v8.state.view == "queue"


def test_navigation() -> None:
    v8 = FakeV8()
    nav = V8ViewNavigator.create(v8)
    assert nav.next() == "queue"
    assert nav.previous() == "now_playing"
    assert nav.set("mixer") == "mixer"
    assert nav.home() == "now_playing"


def test_external_change_adopted() -> None:
    v8 = FakeV8()
    nav = V8ViewNavigator.create(v8)
    v8.state.view = "mixer"
    assert nav.current == "mixer"
    assert nav.next() == "themes"


if __name__ == "__main__":
    test_discovery_restores_original()
    test_navigation()
    test_external_change_adopted()
    print("V9.13C navigation bridge tests passed.")
