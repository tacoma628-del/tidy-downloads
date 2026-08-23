#!/usr/bin/env python3
"""Tidy files sitting in a Downloads folder into Type/YYYY-MM/ subfolders.

Preview is the default. Pass --apply to move files. Never deletes or overwrites.
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

CATEGORY_FOLDERS = (
    "PDFs",
    "Images",
    "Archives",
    "Videos",
    "Audio",
    "Docs",
    "Other",
)

INCOMPLETE_SUFFIXES = (
    ".crdownload",
    ".download",
    ".part",
    ".partial",
    ".tmp",
)

EXTENSIONS = {
    ".pdf": "PDFs",
    ".png": "Images",
    ".jpg": "Images",
    ".jpeg": "Images",
    ".gif": "Images",
    ".webp": "Images",
    ".heic": "Images",
    ".tif": "Images",
    ".tiff": "Images",
    ".bmp": "Images",
    ".svg": "Images",
    ".zip": "Archives",
    ".tar": "Archives",
    ".gz": "Archives",
    ".tgz": "Archives",
    ".7z": "Archives",
    ".rar": "Archives",
    ".dmg": "Archives",
    ".pkg": "Archives",
    ".mp4": "Videos",
    ".mov": "Videos",
    ".mkv": "Videos",
    ".avi": "Videos",
    ".webm": "Videos",
    ".mp3": "Audio",
    ".wav": "Audio",
    ".m4a": "Audio",
    ".aac": "Audio",
    ".flac": "Audio",
    ".doc": "Docs",
    ".docx": "Docs",
    ".xls": "Docs",
    ".xlsx": "Docs",
    ".ppt": "Docs",
    ".pptx": "Docs",
    ".txt": "Docs",
    ".rtf": "Docs",
    ".md": "Docs",
    ".csv": "Docs",
    ".pages": "Docs",
    ".numbers": "Docs",
    ".key": "Docs",
}


@dataclass(frozen=True)
class ApplyResult:
    moved: int
    planned: int


def classify(path: Path) -> str:
    return EXTENSIONS.get(path.suffix.lower(), "Other")


def month_folder(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m")


def is_skippable(path: Path) -> bool:
    if path.name.startswith("."):
        return True
    if path.is_dir():
        return True
    if path.suffix.lower() in INCOMPLETE_SUFFIXES:
        return True
    lower = path.name.lower()
    return any(lower.endswith(suffix) for suffix in INCOMPLETE_SUFFIXES)


def plan_moves(downloads_dir: Path) -> list[tuple[Path, Path]]:
    root = downloads_dir.expanduser()
    planned: list[tuple[Path, Path]] = []
    reserved = set(CATEGORY_FOLDERS)
    used: set[Path] = set()

    for item in sorted(root.iterdir(), key=lambda p: p.name.lower()):
        if item.name in reserved:
            continue
        if is_skippable(item):
            continue
        dest = _unique_against(root / classify(item) / month_folder(item) / item.name, used)
        if dest == item:
            continue
        planned.append((item, dest))
        used.add(dest)
    return planned


def _unique_against(dest: Path, used: set[Path]) -> Path:
    if not dest.exists() and dest not in used:
        return dest
    stem, suffix = dest.stem, dest.suffix
    n = 2
    while True:
        candidate = dest.with_name(f"{stem}-{n}{suffix}")
        if not candidate.exists() and candidate not in used:
            return candidate
        n += 1


def apply_moves(
    plan: list[tuple[Path, Path]],
    apply: bool,
    log_path: Path | None = None,
) -> ApplyResult:
    if not apply:
        return ApplyResult(moved=0, planned=len(plan))

    moved = 0
    lines: list[str] = []
    for src, dest in plan:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest = _unique_against(dest, set())
        src.rename(dest)
        moved += 1
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lines.append(f"{stamp}\t{src}\t->\t{dest}\n")

    if log_path is not None and lines:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.writelines(lines)

    return ApplyResult(moved=moved, planned=len(plan))


def default_downloads() -> Path:
    return Path.home() / "Downloads"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sort files in Downloads into Type/YYYY-MM folders. Preview by default."
    )
    parser.add_argument(
        "--dir",
        type=Path,
        default=default_downloads(),
        help="Folder to tidy (default: ~/Downloads)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Move files. Without this flag, only print the plan.",
    )
    parser.add_argument(
        "--log",
        type=Path,
        default=None,
        help="Append move log here (default: <dir>/tidy-downloads.log when applying)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = args.dir.expanduser().resolve()
    if not root.is_dir():
        print(f"Not a folder: {root}", file=sys.stderr)
        return 1

    plan = plan_moves(root)
    if not plan:
        print(f"Nothing to tidy in {root}")
        return 0

    print(f"{'MOVE' if args.apply else 'PREVIEW'} ({len(plan)} file(s)) in {root}\n")
    for src, dest in plan:
        print(f"  {src.name}")
        print(f"    -> {dest.relative_to(root)}")

    log_path = args.log
    if args.apply and log_path is None:
        log_path = root / "tidy-downloads.log"

    result = apply_moves(plan, apply=args.apply, log_path=log_path)
    if args.apply:
        print(f"\nMoved {result.moved} file(s). Log: {log_path}")
    else:
        print("\nNo files moved. Re-run with --apply to perform these moves.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
