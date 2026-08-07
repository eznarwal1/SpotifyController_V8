from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from typing import Iterable


def find_repo_root(start: Path | None = None) -> Path:
    start = (start or Path.cwd()).resolve()

    result = subprocess.run(
        ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
        text=True,
        capture_output=True,
    )
    if result.returncode == 0 and result.stdout.strip():
        return Path(result.stdout.strip()).resolve()

    for candidate in (start, *start.parents):
        if (candidate / ".git").exists():
            return candidate.resolve()

    fallback = Path.home() / "Downloads" / "SpotifyController_V8"
    if (fallback / ".git").exists():
        return fallback.resolve()

    raise SystemExit("Could not locate the SpotifyController Git repository.")


ROOT = find_repo_root(Path(__file__).resolve().parent)
RELEASE_STATE = ROOT / ".release_state.json"


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        raise SystemExit(result.stderr.strip() or "Git command failed.")
    return result.stdout.strip()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def repo_clean() -> bool:
    return not bool(git("status", "--porcelain"))


def capture_state() -> None:
    if not repo_clean():
        raise SystemExit(
            "Repository is not clean. Commit the working state before "
            "capturing a release base."
        )

    data = {
        "branch": git("branch", "--show-current"),
        "commit": git("rev-parse", "HEAD"),
    }
    RELEASE_STATE.write_text(
        json.dumps(data, indent=2) + "\n",
        encoding="utf-8",
    )
    print("Captured release base:")
    print("  branch:", data["branch"])
    print("  commit:", data["commit"])


def verify_state() -> None:
    if not RELEASE_STATE.exists():
        raise SystemExit(
            ".release_state.json is missing. "
            "Run capture_release_state.bat first."
        )

    expected = json.loads(RELEASE_STATE.read_text(encoding="utf-8"))
    actual = {
        "branch": git("branch", "--show-current"),
        "commit": git("rev-parse", "HEAD"),
    }

    if expected != actual:
        raise SystemExit(
            "Release state mismatch.\n"
            f"Expected: {expected}\n"
            f"Actual:   {actual}"
        )

    if not repo_clean():
        raise SystemExit("Repository has uncommitted changes.")

    print("Release state verification: PASS")


def validate_manifest(manifest_path: Path) -> dict:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))

    required = {"release", "base_commit", "base_branch", "files"}
    missing = required - set(data)
    if missing:
        raise SystemExit(
            "Manifest missing required field(s): "
            + ", ".join(sorted(missing))
        )

    if not isinstance(data["files"], list):
        raise SystemExit("Manifest 'files' must be a list.")

    return data


def install_bundle(bundle_dir: Path) -> None:
    bundle_dir = bundle_dir.resolve()
    manifest_path = bundle_dir / "manifest.json"
    changed_dir = bundle_dir / "changed_files"

    if not manifest_path.exists():
        raise SystemExit(f"Manifest not found: {manifest_path}")

    manifest = validate_manifest(manifest_path)

    current_branch = git("branch", "--show-current")
    current_commit = git("rev-parse", "HEAD")

    if current_branch != manifest["base_branch"]:
        raise SystemExit(
            f"Wrong branch. Expected {manifest['base_branch']}, "
            f"found {current_branch}."
        )

    if current_commit != manifest["base_commit"]:
        raise SystemExit(
            "Wrong base commit.\n"
            f"Expected: {manifest['base_commit']}\n"
            f"Current:  {current_commit}"
        )

    if not repo_clean():
        raise SystemExit(
            "Repository is not clean. Commit or discard changes first."
        )

    backup_root = (
        bundle_dir
        / "backup"
        / manifest["release"]
    )
    if backup_root.exists():
        shutil.rmtree(backup_root)

    changed: list[str] = []

    for entry in manifest["files"]:
        relative = Path(entry["path"])
        source = changed_dir / relative
        target = ROOT / relative

        if not source.exists():
            raise SystemExit(f"Bundle source missing: {source}")

        expected_sha = entry.get("sha256")
        if expected_sha and sha256(source) != expected_sha:
            raise SystemExit(
                f"Bundle checksum failed for {relative}"
            )

        backup_target = backup_root / relative
        if target.exists():
            backup_target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, backup_target)

        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        changed.append(str(relative))

    metadata = {
        "release": manifest["release"],
        "base_commit": manifest["base_commit"],
        "base_branch": manifest["base_branch"],
        "changed_files": changed,
    }
    (bundle_dir / "installed_state.json").write_text(
        json.dumps(metadata, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Installed {manifest['release']}.")
    print("Changed files:")
    for path in changed:
        print("  ", path)
    print()
    print("Review in GitHub Desktop, run checks, hardware-test if needed,")
    print("then commit.")


def restore_bundle(bundle_dir: Path) -> None:
    bundle_dir = bundle_dir.resolve()
    state_path = bundle_dir / "installed_state.json"

    if not state_path.exists():
        raise SystemExit(
            "installed_state.json not found; this bundle has not been "
            "installed by the sync tool."
        )

    state = json.loads(state_path.read_text(encoding="utf-8"))
    backup_root = bundle_dir / "backup" / state["release"]
    changed_dir = bundle_dir / "changed_files"

    for relative_text in state["changed_files"]:
        relative = Path(relative_text)
        backup = backup_root / relative
        target = ROOT / relative

        if backup.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup, target)
        else:
            # If the target did not exist before install, remove the copied file.
            try:
                target.unlink()
            except FileNotFoundError:
                pass

    print(f"Restored files changed by {state['release']}.")


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("capture")
    sub.add_parser("verify")

    install = sub.add_parser("install")
    install.add_argument("bundle_dir")

    restore = sub.add_parser("restore")
    restore.add_argument("bundle_dir")

    args = parser.parse_args()

    if args.command == "capture":
        capture_state()
    elif args.command == "verify":
        verify_state()
    elif args.command == "install":
        install_bundle(Path(args.bundle_dir))
    elif args.command == "restore":
        restore_bundle(Path(args.bundle_dir))


if __name__ == "__main__":
    main()
