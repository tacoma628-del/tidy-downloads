#!/usr/bin/env python3
"""Tidy loose photo/video files scattered across Finder folders into a single
chronological archive: <dest>/YYYY-MM/.

Same philosophy as tidy_downloads.py: preview by default, --apply moves,
never deletes or overwrites. Files that are byte-for-byte duplicates of a
file already planned (or already sitting in <dest>) are left in place and
reported separately -- nothing is ever deleted automatically.

Date-taken comes from Spotlight's EXIF-derived kMDItemContentCreationDate
(no extra dependencies needed), falling back to the file's mtime.
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

PHOTO_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".heif",
    ".tif", ".tiff", ".bmp",
    ".mov", ".mp4", ".m4v", ".avi", ".mkv", ".webm",
}

INCOMPLETE_SUFFIXES = (".crdownload", ".download", ".part", ".partial", ".tmp")

DEFAULT_SOURCES = ("~/Desktop", "~/Documents", "~/Pictures")
DEFAULT_DEST = "~/Pictures/Organized"

CHUNK_SIZE = 1 << 20


@dataclass(frozen=True)
class Plan:
    moves: list[tuple[Path, Path]] = field(default_factory=list)
    duplicates: list[tuple[Path, Path]] = field(default_factory=list)


@dataclass(frozen=True)
class ApplyResult:
    moved: int
    planned: int


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def date_taken(path: Path) -> datetime:
    try:
        out = subprocess.run(
            ["mdls", "-raw", "-name", "kMDItemContentCreationDate", str(path)],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip()
        if out and out != "(null)":
            return datetime.strptime(out, "%Y-%m-%d %H:%M:%S %z")
    except (subprocess.SubprocessError, ValueError):
        pass
    return datetime.fromtimestamp(path.stat().st_mtime)


def is_skippable(path: Path, dest_root: Path, exclude: list[Path]) -> bool:
    if path.name.startswith("."):
        return True
    if path.suffix.lower() in INCOMPLETE_SUFFIXES:
        return True
    if path.suffix.lower() not in PHOTO_EXTENSIONS:
        return True
    if path.stat().st_size == 0:
        return True
    if any(_is_relative_to(path, ex) for ex in exclude):
        return True
    try:
        path.relative_to(dest_root)
        return True
    except ValueError:
        return False


def _is_relative_to(path: Path, other: Path) -> bool:
    try:
        path.relative_to(other)
        return True
    except ValueError:
        return False


def is_skippable_dir(name: str) -> bool:
    return (
        name.startswith(".")
        or name.endswith(".photoslibrary")
        or name.endswith(".app")
    )


def iter_candidates(source: Path, dest_root: Path, exclude: list[Path] | None = None):
    exclude = exclude or []
    if not source.is_dir():
        return
    for root, dirnames, filenames in _walk(source):
        dirnames[:] = [
            d for d in dirnames
            if not is_skippable_dir(d)
            and not (root / d / ".git").is_dir()
            and not any(_is_relative_to(root / d, ex) for ex in exclude)
        ]
        for filename in filenames:
            path = root / filename
            if not is_skippable(path, dest_root, exclude):
                yield path


def _walk(source: Path):
    import os
    for root, dirnames, filenames in os.walk(source):
        yield Path(root), dirnames, filenames


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


def plan_moves(sources: list[Path], dest_root: Path, exclude: list[Path] | None = None) -> Plan:
    exclude = exclude or []
    seen_hashes: dict[str, Path] = {}

    # Seed with anything already organized, so re-runs and cross-folder
    # duplicates against past runs are recognized too.
    if dest_root.is_dir():
        for existing in iter_candidates(dest_root, dest_root.parent / "__never__"):
            seen_hashes[sha256_of(existing)] = existing

    candidates: list[Path] = []
    for source in sources:
        candidates.extend(iter_candidates(source, dest_root, exclude))
    candidates.sort(key=lambda p: (date_taken(p), str(p)))

    used: set[Path] = set()
    plan = Plan()
    for path in candidates:
        digest = sha256_of(path)
        if digest in seen_hashes:
            plan.duplicates.append((path, seen_hashes[digest]))
            continue
        seen_hashes[digest] = path
        month = date_taken(path).strftime("%Y-%m")
        dest = _unique_against(dest_root / month / path.name, used)
        plan.moves.append((path, dest))
        used.add(dest)
    return plan


def apply_moves(plan: Plan, apply: bool, log_path: Path | None = None) -> ApplyResult:
    if not apply:
        return ApplyResult(moved=0, planned=len(plan.moves))

    moved = 0
    lines: list[str] = []
    for src, dest in plan.moves:
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

    return ApplyResult(moved=moved, planned=len(plan.moves))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sort loose photos/videos into <dest>/YYYY-MM folders and "
        "flag duplicates. Preview by default."
    )
    parser.add_argument(
        "--sources", nargs="+", type=Path,
        default=[Path(s).expanduser() for s in DEFAULT_SOURCES],
        help=f"Folders to scan (default: {' '.join(DEFAULT_SOURCES)})",
    )
    parser.add_argument(
        "--dest", type=Path, default=Path(DEFAULT_DEST).expanduser(),
        help=f"Destination archive root (default: {DEFAULT_DEST})",
    )
    parser.add_argument(
        "--exclude", nargs="+", type=Path, default=[],
        help="Folders to skip entirely (e.g. work-related, not personal photos)",
    )
    parser.add_argument("--apply", action="store_true", help="Move files.")
    parser.add_argument("--log", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    dest_root = args.dest.expanduser().resolve()
    sources = [s.expanduser().resolve() for s in args.sources]
    exclude = [e.expanduser().resolve() for e in args.exclude]

    plan = plan_moves(sources, dest_root, exclude)

    if not plan.moves and not plan.duplicates:
        print("Nothing to tidy.")
        return 0

    print(f"{'MOVE' if args.apply else 'PREVIEW'} ({len(plan.moves)} file(s)) -> {dest_root}\n")
    for src, dest in plan.moves:
        print(f"  {src}")
        print(f"    -> {dest.relative_to(dest_root)}")

    if plan.duplicates:
        print(f"\nDUPLICATES ({len(plan.duplicates)}) -- left in place, not moved:")
        for dup, original in plan.duplicates:
            print(f"  {dup}")
            print(f"    == {original}")

    log_path = args.log
    if args.apply and log_path is None:
        log_path = dest_root / "tidy-photos.log"

    result = apply_moves(plan, apply=args.apply, log_path=log_path)
    if args.apply:
        print(f"\nMoved {result.moved} file(s). Log: {log_path}")
    else:
        print(f"\nNo files moved. Re-run with --apply to move the {result.planned} unique file(s).")
        if plan.duplicates:
            print("Duplicates are never auto-deleted -- review and delete manually if you agree.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
