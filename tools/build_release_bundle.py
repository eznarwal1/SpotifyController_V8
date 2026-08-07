from __future__ import annotations

from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess


def find_repo_root(start: Path) -> Path:
    result = subprocess.run(
        ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        raise SystemExit("Could not locate repository.")
    return Path(result.stdout.strip()).resolve()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        raise SystemExit(result.stderr.strip() or "Git command failed.")
    return result.stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a full-file replacement release bundle."
    )
    parser.add_argument("release_name")
    parser.add_argument(
        "files",
        nargs="+",
        help="Repository-relative paths to include.",
    )
    parser.add_argument(
        "--output",
        default="releases",
    )
    args = parser.parse_args()

    root = find_repo_root(Path.cwd())

    if git(root, "status", "--porcelain"):
        raise SystemExit(
            "Repository must be clean before building a release bundle."
        )

    output_root = root / args.output
    bundle = output_root / args.release_name
    changed = bundle / "changed_files"

    if bundle.exists():
        shutil.rmtree(bundle)

    changed.mkdir(parents=True)

    manifest_files = []

    for text in args.files:
        relative = Path(text)
        source = root / relative

        if not source.exists():
            raise SystemExit(f"Missing source: {relative}")

        target = changed / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

        manifest_files.append(
            {
                "path": relative.as_posix(),
                "sha256": sha256(target),
            }
        )

    manifest = {
        "release": args.release_name,
        "base_commit": git(root, "rev-parse", "HEAD"),
        "base_branch": git(root, "branch", "--show-current"),
        "files": manifest_files,
    }

    (bundle / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print("Built release bundle:", bundle)
    print("Base commit:", manifest["base_commit"])
    print("Files:", len(manifest_files))


if __name__ == "__main__":
    main()
