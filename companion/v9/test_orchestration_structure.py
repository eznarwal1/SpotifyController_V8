from pathlib import Path


def test_main_is_small_orchestrator() -> None:
    main = Path(__file__).parents[1] / "main.py"
    text = main.read_text(encoding="utf-8")

    assert "async def serial_command_loop(" not in text
    assert "async def command_loop(" not in text
    assert "async def v8_view_loop(" not in text
    assert "from v9.input_tasks import" in text
    assert "from v9.view_tasks import" in text

    line_count = len(text.splitlines())
    assert line_count < 250, line_count


if __name__ == "__main__":
    test_main_is_small_orchestrator()
    print("V9.13F orchestration structure test passed.")
