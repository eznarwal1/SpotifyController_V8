from __future__ import annotations

import argparse
from pathlib import Path

CACHE_DIR = Path(__file__).resolve().parent / "artwork_cache"


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage the artwork cache.")
    parser.add_argument(
        "command",
        nargs="?",
        default="status",
        choices=("status", "clear"),
    )
    args = parser.parse_args()

    files = sorted(CACHE_DIR.glob("*.rgb565")) if CACHE_DIR.exists() else []

    if args.command == "clear":
        for path in files:
            path.unlink(missing_ok=True)
        print(f"Deleted {len(files)} cached images.")
        return

    total = sum(path.stat().st_size for path in files)
    print(f"Cache folder: {CACHE_DIR}")
    print(f"Cached images: {len(files)}")
    print(f"Cache size: {total / (1024 * 1024):.2f} MB")


if __name__ == "__main__":
    main()
