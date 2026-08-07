from queue_window import (
    build_queue_window,
    find_preserved_selection,
)


def test_empty() -> None:
    window = build_queue_window([], 0)
    assert window.rows == ()
    assert window.total == 0
    assert window.global_selected_index == 0


def test_first_item() -> None:
    queue = ["A", "B", "C", "D", "E"]
    window = build_queue_window(queue, 0)
    assert window.rows == ("A", "B", "C", "D")
    assert window.local_selected_index == 0
    assert window.start_index == 0


def test_middle_item() -> None:
    queue = ["A", "B", "C", "D", "E", "F"]
    window = build_queue_window(queue, 3)
    assert window.rows == ("C", "D", "E", "F")
    assert window.local_selected_index == 1
    assert window.global_selected_index == 3


def test_last_item() -> None:
    queue = ["A", "B", "C", "D", "E", "F"]
    window = build_queue_window(queue, 5)
    assert window.rows == ("C", "D", "E", "F")
    assert window.local_selected_index == 3
    assert window.start_index == 2


def test_preserve_selected_track() -> None:
    queue = ["A", "B", "C", "D"]
    assert find_preserved_selection("C", 2, queue) == 2


def test_duplicate_prefers_nearest() -> None:
    queue = ["A", "B", "A", "C"]
    assert find_preserved_selection("A", 2, queue) == 2


if __name__ == "__main__":
    test_empty()
    test_first_item()
    test_middle_item()
    test_last_item()
    test_preserve_selected_track()
    test_duplicate_prefers_nearest()
    print("V9 queue-window tests passed.")
