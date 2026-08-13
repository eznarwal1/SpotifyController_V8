"""
Create a minimal ZIP bundle of the companion/ package for distribution.
Excludes caches, virtualenvs, and large generated assets.

Usage:
    python companion/tools/make_bundle.py --output ../companion_bundle.zip

The resulting ZIP contains a runnable layout and simple install/run scripts.
"""
from __future__ import annotations

import argparse
import os
import zipfile
from pathlib import Path

EXCLUDE_DIRS = {"artwork_cache", "background_cache", ".venv", "__pycache__"}
EXCLUDE_EXTS = {".pyc", ".pyo"}

BASE = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = Path(__file__).resolve().parents[2] / "companion_bundle.zip"

LAUNCH_BAT = r"""@echo off
python -m venv venv
venv\Scripts\pip install --upgrade pip
venv\Scripts\pip install -r requirements.txt
venv\Scripts\python main.py
"""

LAUNCH_SH = """#!/usr/bin/env bash
python -m venv venv
. venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
python main.py
"""


def should_exclude(path: Path, base: Path) -> bool:
    rel = path.relative_to(base)
    parts = set(rel.parts)
    if parts & EXCLUDE_DIRS:
        return True
    if path.suffix in EXCLUDE_EXTS:
        return True
    return False


def make_bundle(output: Path) -> None:
    output = output.resolve()
    if output.exists():
        output.unlink()

    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(BASE):
            root_path = Path(root)
            # filter dirs in-place to avoid walking excluded dirs
            dirs[:] = [d for d in dirs if not should_exclude(root_path / d, BASE)]

            for fname in files:
                fpath = root_path / fname
                if should_exclude(fpath, BASE):
                    continue
                arcname = fpath.relative_to(BASE.parent)  # include companion/ prefix
                z.write(fpath, arcname.as_posix())

        # Add launchers and README
        z.writestr("companion/run.bat", LAUNCH_BAT)
        z.writestr("companion/run.sh", LAUNCH_SH)
        z.writestr("companion/README-BUNDLE.txt", "Create a venv and pip install -r requirements.txt, then run main.py")

    print(f"Created bundle: {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", "-o", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()
    make_bundle(Path(args.output))
