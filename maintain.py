#!/usr/bin/env python3
"""One-button Mac maintenance: tidy, clean, and report.

Preview is the default. Pass --apply to make changes. Never hard-deletes:
files go to the Trash, and anything risky is report-only.

Each run overwrites a single report in the Obsidian vault (no dated clutter).
Toggle tasks in TASKS below. --node runs the Mac mini (exo node) checks.
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

# Repos kept off GitHub on purpose; still flagged for uncommitted work.
LOCAL_ONLY_REPOS = {"finance-dashboard", "finance-kit"}

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
    "mac_mini": True,
}

# --- Mac mini (exo inference node) ---
# The Studio copies this script to the mini over SSH and runs it with --node,
# so there is nothing to install there. Node mode never upgrades or deletes:
# a brew upgrade can break exo mid-cluster, and models take hours to re-download.
MINI_USER = "macminim5"
MINI_HOSTS = ["192.168.1.112", "Davids-Mac-Mini.local"]  # LAN first; .local can resolve to the TB bridge
MINI_SSH = ["-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
            "-o", "HostKeyAlias=davids-mac-mini.local"]
MINI_DIR = ".mac-maintenance"

NODE_TASKS = ["node_exo", "node_models", "node_ram", "node_brew", "disk"]
EXO_MODELS = HOME / ".exo" / "models"
PARTIAL_MODEL_BYTES = 1024 ** 3  # under 1 GB = unfinished download or placeholder
RAM_FLAG_MB = 300
# Processes that belong on the node; never suggested for quitting.
RAM_KEEP = ("exo", "python", "JumpConnect", "WindowServer", "kernel_task", "launchd")

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
        if vol.name.startswith(("com.apple", ".")) or vol.name in ("Macintosh HD", "Recovery"):
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
            if repo.name not in LOCAL_ONLY_REPOS:
                notes.append("no upstream")
        elif ahead.strip() not in ("", "0"):
            notes.append(f"{ahead.strip()} unpushed")
        if notes:
            lines.append(f"- **{repo.name}**: {', '.join(notes)}")
    return lines or ["All repos clean and pushed."]


# ---------- node mode (runs on the Mac mini) ----------

def find_brew() -> str:
    # SSH sessions skip the login PATH, so /opt/homebrew/bin is often missing.
    return shutil.which("brew") or "/opt/homebrew/bin/brew"


def exo_running() -> bool:
    code, _ = run(["pgrep", "-f", r"uv run exo|exo/\.venv|bin/exo"], timeout=10)
    return code == 0


def task_node_exo(apply: bool) -> list[str]:
    if exo_running():
        return ["exo is running."]
    return ["⚠️ exo is **not running** — the node is out of the cluster. "
            "Start it on the mini: `cd ~/exo && uv run exo`"]


def scan_models(root: Path, days: int, now: float | None = None) -> list[dict]:
    now = now or time.time()
    rows = []
    if not root.is_dir():
        return rows
    for d in sorted(c for c in root.iterdir() if c.is_dir() and c.name != "caches"):
        files = [f for f in d.rglob("*") if f.is_file() and not f.is_symlink()]
        size = sum(f.stat().st_size for f in files)
        last = max([d.stat().st_mtime] + [max(f.stat().st_atime, f.stat().st_mtime) for f in files])
        rows.append({
            "name": d.name.replace("--", "/"),
            "size": size,
            "last": last,
            "partial": size < PARTIAL_MODEL_BYTES,
            "stale": last < now - days * 86400,
        })
    return sorted(rows, key=lambda r: -r["size"])


def task_node_models(apply: bool, root: Path = EXO_MODELS) -> list[str]:
    rows = scan_models(root, OLD_DAYS)
    if not rows:
        return [f"No models in `{root}`."]
    full = [r for r in rows if not r["partial"]]
    partial = [r for r in rows if r["partial"]]
    lines = [f"{human(sum(r['size'] for r in rows))} in `~/.exo/models`. Report only — nothing deleted.", ""]
    for r in full:
        when = datetime.fromtimestamp(r["last"]).strftime("%Y-%m-%d")
        flag = f" — **unused {OLD_DAYS}+ days, removal candidate**" if r["stale"] else ""
        lines.append(f"- {human(r['size'])} — {r['name']} (last used {when}){flag}")
    if partial:
        lines += ["", f"**Unfinished downloads / placeholders** ({len(partial)}, "
                      f"{human(sum(r['size'] for r in partial))}) — safe to remove:"]
        lines += [f"- {human(r['size'])} — {r['name']}" for r in partial]
    return lines


def task_node_ram(apply: bool) -> list[str]:
    lines = []
    _, mp = run(["memory_pressure"], timeout=30)
    free = [l for l in mp.splitlines() if "free percentage" in l]
    if free:
        lines.append(f"- Memory free: {free[-1].split(':')[-1].strip()}")
    _, swap = run(["sysctl", "-n", "vm.swapusage"], timeout=10)
    used = swap.split("used = ")[-1].split()[0] if "used = " in swap else "?"
    lines.append(f"- Swap used: {used}" + ("" if used.startswith("0.00") else
                 " — ⚠️ something is competing with the model for RAM"))
    _, ps = run(["ps", "-axo", "rss=,comm="], timeout=10)
    hogs = []
    for line in ps.splitlines():
        rss, _, cmd = line.strip().partition(" ")
        if not rss.isdigit() or int(rss) // 1024 < RAM_FLAG_MB:
            continue
        name = Path(cmd.strip()).name
        if cmd.startswith("/System/") or any(k.lower() in cmd.lower() for k in RAM_KEEP):
            continue
        hogs.append((int(rss) * 1024, name))
    if hogs:
        lines += ["", f"**Using over {RAM_FLAG_MB} MB (not needed for the node — consider quitting):**"]
        lines += [f"- {human(b)} — {n}" for b, n in sorted(hogs, reverse=True)]
    else:
        lines.append(f"- Nothing besides exo/Jump Desktop is using over {RAM_FLAG_MB} MB.")
    code, items = run(["osascript", "-e",
                       'tell application "System Events" to get the name of every login item'], timeout=15)
    if code == 0 and items.strip():
        lines.append(f"- Login items: {items.strip()}")
    return lines


def task_node_brew(apply: bool) -> list[str]:
    brew = find_brew()
    lines = []
    if apply:
        code, out = run([brew, "update"])
        lines.append(f"- `brew update`: " + ("ok" if code == 0 else f"⚠️ exit {code}"))
    code, out = run([brew, "outdated"])
    pkgs = [l.strip() for l in out.splitlines() if l.strip()]
    lines.append(f"- {len(pkgs)} package(s) have upgrades — **not upgraded on the node**"
                 + (f": {', '.join(pkgs)}" if pkgs else ""))
    cmd = [brew, "cleanup", "-s"] + ([] if apply else ["--dry-run"])
    code, out = run(cmd)
    freed = [l for l in out.splitlines() if "free" in l.lower()]
    lines.append(f"- `brew cleanup -s`: " + (("ok" + (" — " + freed[-1] if freed else ""))
                                             if code == 0 else f"⚠️ exit {code}"))
    return lines


# ---------- Mac mini (runs on the Studio, drives the node over SSH) ----------

def mini_target() -> str | None:
    for host in MINI_HOSTS:
        code, _ = run(["ssh", *MINI_SSH, f"{MINI_USER}@{host}", "true"], timeout=20)
        if code == 0:
            return f"{MINI_USER}@{host}"
    return None


def task_mac_mini(apply: bool) -> list[str]:
    target = mini_target()
    if not target:
        return ["⚠️ Mac mini unreachable over SSH (asleep, off the network, or the IP changed)."]
    run(["ssh", *MINI_SSH, target, f"mkdir -p {MINI_DIR}"], timeout=30)
    code, out = run(["scp", "-q", *MINI_SSH, str(Path(__file__).resolve()), f"{target}:{MINI_DIR}/maintain.py"],
                    timeout=60)
    if code != 0:
        return [f"⚠️ couldn't copy the script to the mini: {out}"]
    cmd = f"/usr/bin/python3 {MINI_DIR}/maintain.py --node" + (" --apply" if apply else "")
    code, out = run(["ssh", *MINI_SSH, target, cmd], timeout=1200)
    if code != 0:
        return [f"⚠️ node run failed (exit {code}): {out.splitlines()[-1] if out else ''}"]
    # Nest the node's sections under this one.
    return [("#" + l) if l.startswith("## ") else l for l in out.splitlines()]


TASK_FUNCS = {
    "old_screenshots": ("Old screenshots", task_old_screenshots),
    "downloads": ("Downloads", lambda a: task_script("tidy_downloads.py", a)),
    "photos": ("Loose photos", lambda a: task_script("tidy_photos.py", a)),
    "homebrew": ("Homebrew", task_homebrew),
    "brew_autoremove": ("Homebrew unused packages", task_brew_autoremove),
    "dev_junk": ("Dev junk in ~/Developer", task_dev_junk),
    "disk": ("Disk space", task_disk),
    "git": ("Git repos", task_git),
    "mac_mini": ("Mac mini (exo node)", task_mac_mini),
    "node_exo": ("exo", task_node_exo),
    "node_models": ("Models", task_node_models),
    "node_ram": ("RAM", task_node_ram),
    "node_brew": ("Homebrew (no upgrades on the node)", task_node_brew),
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
    parser.add_argument("--node", action="store_true",
                        help="Mac mini node mode: print sections only, no file, no upgrades.")
    args = parser.parse_args(argv)

    chosen = args.only or (NODE_TASKS if args.node else [k for k, on in TASKS.items() if on])
    sections = []
    for key in chosen:
        title, fn = TASK_FUNCS[key]
        if not args.node:
            print(f"→ {title}...", flush=True)
        try:
            lines = fn(args.apply)
        except Exception as exc:  # one failing task shouldn't stop the rest
            lines = [f"⚠️ failed: {exc}"]
        sections.append((title, lines))

    if args.node:
        for title, lines in sections:
            print("\n".join([f"## {title}", "", *lines, ""]))
        return 0

    report = build_report(sections, args.apply)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(report)
    print("\n" + report)
    print(f"Report written to: {args.report}")
    notify("Done. Report updated in Obsidian.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
