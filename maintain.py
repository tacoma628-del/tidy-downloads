#!/usr/bin/env python3
"""One-button Mac maintenance: tidy, clean, and report.

Preview is the default. Pass --apply to make changes. Never hard-deletes:
files go to the Trash, and anything risky is report-only.

Each run overwrites a single report in the Obsidian vault (no dated clutter).
Toggle tasks in TASKS below.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import os
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
HOME = Path.home()

VAULT = HOME / "Library/Mobile Documents/com~apple~CloudDocs/Obsidian Vault"
REPORT_PATH = VAULT / "output" / "Mac Maintenance Report.md"

DEVELOPER = HOME / "Developer"
BIG_DRIVE = Path("/Volumes/2TB Extreme Pro 2")
SCREENSHOT_DIR = HOME / "Desktop"
SCREENSHOT_PREFIXES = ("Screenshot ", "Screen Shot ", "Screen Recording ")
OLD_DAYS = 30

# Flip any to False to skip that task.
TASKS = {
    "old_screenshots": True,
    "downloads": True,
    "photos": True,
    "homebrew": True,
    "brew_autoremove": True,
    "dev_junk": True,
    "disk": True,
    "git": True,
}

JUNK_DIR_NAMES = {"__pycache__", ".venv", "venv", "node_modules", ".pytest_cache"}


def run(cmd: list[str], timeout: int = 900, cwd: Path | None = None) -> tuple[int, str]:
    """Run a command with no stdin (so nothing can hang on a prompt)."""
    try:
        env = {**os.environ, "HOMEBREW_NO_ENV_HINTS": "1", "HOMEBREW_NO_AUTO_UPDATE": "1"}
        proc = subprocess.run(
            cmd, cwd=cwd, stdin=subprocess.DEVNULL, capture_output=True,
            text=True, timeout=timeout, env=env,
        )
        return proc.returncode, (proc.stdout + proc.stderr).strip()
    except subprocess.TimeoutExpired:
        return 124, f"timed out after {timeout}s"
    except FileNotFoundError:
        return 127, f"not found: {cmd[0]}"


def human(nbytes: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if nbytes < 1024:
            return f"{nbytes:.1f} {unit}"
        nbytes /= 1024
    return f"{nbytes:.1f} PB"


def dir_size(path: Path) -> int:
    total = 0
    for p in path.rglob("*"):
        try:
            if p.is_file() and not p.is_symlink():
                total += p.stat().st_size
        except OSError:
            pass
    return total


def unique_path(dest: Path) -> Path:
    if not dest.exists():
        return dest
    n = 2
    while True:
        candidate = dest.with_name(f"{dest.stem}-{n}{dest.suffix}")
        if not candidate.exists():
            return candidate
        n += 1


# ---------- tasks: each returns a list of markdown lines ----------

def find_old_screenshots(folder: Path, days: int, now: float | None = None) -> list[Path]:
    now = now or time.time()
    cutoff = now - days * 86400
    if not folder.is_dir():
        return []
    return sorted(
        p for p in folder.iterdir()
        if p.is_file() and p.name.startswith(SCREENSHOT_PREFIXES) and p.stat().st_mtime < cutoff
    )


def task_old_screenshots(apply: bool, folder: Path = SCREENSHOT_DIR,
                         trash: Path = HOME / ".Trash") -> list[str]:
    old = find_old_screenshots(folder, OLD_DAYS)
    if not old:
        return [f"No screenshots older than {OLD_DAYS} days on the Desktop."]
    verb = "Moved to Trash" if apply else "Would move to Trash"
    lines = [f"{verb}: {len(old)} screenshot(s) older than {OLD_DAYS} days."]
    for p in old:
        if apply:
            shutil.move(str(p), str(unique_path(trash / p.name)))
        lines.append(f"- {p.name}")
    return lines


def task_script(script: str, apply: bool) -> list[str]:
    cmd = [sys.executable, str(HERE / script)] + (["--apply"] if apply else [])
    code, out = run(cmd)
    if code != 0:
        return [f"⚠️ exit {code}: {out.splitlines()[-1] if out else ''}"]
    keys = ("PREVIEW", "MOVE", "Moved", "Nothing", "DUPLICATES")
    summary = [l.strip() for l in out.splitlines() if l.startswith(keys)]
    return [f"- {l}" for l in summary] or ["(no output)"]


def task_homebrew(apply: bool) -> list[str]:
    lines = []
    steps = [["brew", "update"], ["brew", "upgrade"], ["brew", "cleanup", "-s"]] if apply \
        else [["brew", "outdated"], ["brew", "cleanup", "-s", "--dry-run"]]
    for cmd in steps:
        code, out = run(cmd)
        if code != 0:
            last = out.splitlines()[-1] if out else ""
            lines.append(f"- `{' '.join(cmd)}`: ⚠️ exit {code} — {last}")
        elif cmd[1] == "outdated":
            n = len([l for l in out.splitlines() if l.strip()])
            lines.append(f"- {n} package(s) outdated (upgraded on --apply)")
        else:
            freed = [l for l in out.splitlines() if "free" in l.lower()]
            lines.append(f"- `{' '.join(cmd)}`: ok{' — ' + freed[-1] if freed else ''}")
    code, out = run(["brew", "doctor"])
    lines.append("- `brew doctor`: " + ("ready to brew" if code == 0 else "⚠️ has warnings (run `brew doctor`)"))
    return lines


def task_brew_autoremove(apply: bool) -> list[str]:
    code, out = run(["brew", "autoremove", "--dry-run"])
    pkgs = [l.strip() for l in out.splitlines() if l.strip() and not l.startswith("==>")]
    if not pkgs:
        return ["Nothing to autoremove."]
    return [f"**Review:** {len(pkgs)} package(s) look unused. Not removed — confirm first:"] + \
        [f"- {p}" for p in pkgs]


def find_junk_dirs(root: Path, days: int, now: float | None = None) -> list[tuple[Path, int]]:
    now = now or time.time()
    cutoff = now - days * 86400
    found = []
    if not root.is_dir():
        return found
    stack = [root]
    while stack:
        d = stack.pop()
        try:
            children = [c for c in d.iterdir() if c.is_dir() and not c.is_symlink()]
        except OSError:
            continue
        for c in children:
            if c.name in JUNK_DIR_NAMES:
                if c.stat().st_mtime < cutoff:
                    found.append((c, dir_size(c)))
            elif c.name != ".git":
                stack.append(c)
    return sorted(found, key=lambda x: -x[1])


def task_dev_junk(apply: bool) -> list[str]:
    junk = find_junk_dirs(DEVELOPER, OLD_DAYS)
    if not junk:
        return [f"No stale build/env folders (untouched {OLD_DAYS}+ days)."]
    total = sum(s for _, s in junk)
    lines = [f"{len(junk)} stale folder(s), {human(total)} total. Report only:"]
    lines += [f"- {human(s)} — `{p.relative_to(DEVELOPER)}`" for p, s in junk[:15]]
    return lines


def biggest_children(root: Path, n: int = 10) -> list[tuple[str, int]]:
    code, out = run(["du", "-sk", *[str(c) for c in root.iterdir() if not c.name.startswith(".")]],
                    timeout=600)
    rows = []
    for line in out.splitlines():
        parts = line.split("\t", 1)
        if len(parts) == 2 and parts[0].isdigit():
            rows.append((Path(parts[1]).name, int(parts[0]) * 1024))
    return sorted(rows, key=lambda x: -x[1])[:n]


def task_disk(apply: bool) -> list[str]:
    lines = ["| Volume | Free | Used |", "|---|---|---|"]
    for vol in [Path("/")] + sorted(Path("/Volumes").iterdir()):
        if vol.name.startswith(("com.apple", ".")) or vol.name == "Macintosh HD":
            continue
        try:
            u = shutil.disk_usage(vol)
        except OSError:
            continue
        lines.append(f"| {vol.name or 'Macintosh HD'} | {human(u.free)} | {u.used * 100 // u.total}% |")
    for label, root in (("Home folder", HOME), (BIG_DRIVE.name, BIG_DRIVE)):
        if root.is_dir():
            lines += ["", f"**Biggest in {label}:**"]
            lines += [f"- {human(s)} — {name}" for name, s in biggest_children(root)]
    return lines


def task_git(apply: bool) -> list[str]:
    lines = []
    for repo in sorted(p.parent for p in DEVELOPER.glob("*/.git")):
        _, dirty = run(["git", "status", "--porcelain"], cwd=repo, timeout=60)
        code, ahead = run(["git", "rev-list", "--count", "@{u}..HEAD"], cwd=repo, timeout=60)
        notes = []
        if dirty:
            notes.append(f"{len(dirty.splitlines())} uncommitted")
        if code != 0:
            notes.append("no upstream")
        elif ahead.strip() not in ("", "0"):
            notes.append(f"{ahead.strip()} unpushed")
        if notes:
            lines.append(f"- **{repo.name}**: {', '.join(notes)}")
    return lines or ["All repos clean and pushed."]


TASK_FUNCS = {
    "old_screenshots": ("Old screenshots", task_old_screenshots),
    "downloads": ("Downloads", lambda a: task_script("tidy_downloads.py", a)),
    "photos": ("Loose photos", lambda a: task_script("tidy_photos.py", a)),
    "homebrew": ("Homebrew", task_homebrew),
    "brew_autoremove": ("Homebrew unused packages", task_brew_autoremove),
    "dev_junk": ("Dev junk in ~/Developer", task_dev_junk),
    "disk": ("Disk space", task_disk),
    "git": ("Git repos", task_git),
}


def build_report(sections: list[tuple[str, list[str]]], apply: bool) -> str:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    mode = "Applied" if apply else "Preview only (nothing changed)"
    out = [f"# Mac Maintenance Report", "", f"Last run: {stamp} · {mode}", ""]
    for title, lines in sections:
        out += [f"## {title}", "", *lines, ""]
    return "\n".join(out)


def notify(message: str) -> None:
    run(["osascript", "-e", f'display notification "{message}" with title "Mac maintenance"'], timeout=10)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Mac maintenance. Preview by default.")
    parser.add_argument("--apply", action="store_true", help="Make changes.")
    parser.add_argument("--only", nargs="+", choices=TASK_FUNCS, help="Run just these tasks.")
    parser.add_argument("--report", type=Path, default=REPORT_PATH, help="Report file (overwritten).")
    args = parser.parse_args(argv)

    chosen = args.only or [k for k, on in TASKS.items() if on]
    sections = []
    for key in chosen:
        title, fn = TASK_FUNCS[key]
        print(f"→ {title}...", flush=True)
        try:
            lines = fn(args.apply)
        except Exception as exc:  # one failing task shouldn't stop the rest
            lines = [f"⚠️ failed: {exc}"]
        sections.append((title, lines))

    report = build_report(sections, args.apply)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(report)
    print("\n" + report)
    print(f"Report written to: {args.report}")
    notify("Done. Report updated in Obsidian.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
