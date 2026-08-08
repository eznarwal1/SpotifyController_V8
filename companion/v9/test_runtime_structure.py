from pathlib import Path


def test_main_is_orchestration_focused() -> None:
    main = Path(__file__).parents[1] / "main.py"
    text = main.read_text(encoding="utf-8")

    assert "async def artwork_loop(" not in text
    assert "async def metadata_image_loop(" not in text
    assert "async def source_image_loop(" not in text
    assert "async def polling_loop(" not in text
    assert "from v9.media_tasks import" in text
    assert "from v9.runtime_state import" in text


if __name__ == "__main__":
    test_main_is_orchestration_focused()
    print("V9.13E runtime structure test passed.")
