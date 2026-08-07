from view_controller import ViewController


def test_forward_wrap() -> None:
    controller = ViewController(
        order=("now_playing", "queue", "mixer"),
        current="now_playing",
    )
    assert controller.next() == "queue"
    assert controller.next() == "mixer"
    assert controller.next() == "now_playing"


def test_backward_wrap() -> None:
    controller = ViewController(
        order=("now_playing", "queue", "mixer"),
        current="now_playing",
    )
    assert controller.previous() == "mixer"
    assert controller.previous() == "queue"
    assert controller.previous() == "now_playing"


def test_set_and_home() -> None:
    controller = ViewController(
        order=("now_playing", "queue", "mixer"),
        current="queue",
    )
    assert controller.set("mixer") == "mixer"
    assert controller.home() == "now_playing"


def test_unknown_view_rejected() -> None:
    controller = ViewController(
        order=("now_playing", "queue"),
    )
    try:
        controller.set("themes")
    except ValueError:
        pass
    else:
        raise AssertionError("Unknown view should raise ValueError.")


if __name__ == "__main__":
    test_forward_wrap()
    test_backward_wrap()
    test_set_and_home()
    test_unknown_view_rejected()
    print("V9 view-controller tests passed.")
