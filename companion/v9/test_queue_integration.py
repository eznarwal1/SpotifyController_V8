from queue_window import build_queue_window, find_preserved_selection


def test_four_row_behavior() -> None:
    queue = ["A", "B", "C", "D", "E", "F"]

    assert build_queue_window(queue, 0).rows == ("A", "B", "C", "D")

    middle = build_queue_window(queue, 3)
    assert middle.rows == ("C", "D", "E", "F")
    assert middle.local_selected_index == 1

    last = build_queue_window(queue, 5)
    assert last.rows == ("C", "D", "E", "F")
    assert last.local_selected_index == 3


def test_selection_survives_queue_shift() -> None:
    new_queue = ["B", "C", "D", "E", "F"]
    assert find_preserved_selection(
        "D",
        3,
        new_queue,
    ) == 2


if __name__ == "__main__":
    test_four_row_behavior()
    test_selection_survives_queue_shift()
    print("V9.13B queue integration tests passed.")
