#!/usr/bin/env python3
"""Weekly rollup of Promethean Updates memos into the Obsidian world-state digest.

Runs locally (via launchd) because the Obsidian vault is an iCloud-synced path
only reachable from this Mac -- the daily video-check runs as a cloud routine
and can only write into the tidy-downloads git repo.

Idempotent: tracks which video IDs have already been folded into the digest
in .weekly_synced_ids.txt, so re-running (or a missed week) never duplicates
an entry.
"""
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

REPO = Path("/Users/davidpalmeri/Developer/tidy-downloads")
MEMOS_DIR = REPO / "memos" / "promethean-updates"
INDEX_TSV = MEMOS_DIR / ".index.tsv"
SYNCED_IDS = MEMOS_DIR / ".weekly_synced_ids.txt"
VAULT = Path.home() / "Library/Mobile Documents/com~apple~CloudDocs/Obsidian Vault"
DIGEST_MD = VAULT / "wiki" / "world-state-digest" / "promethean-updates-weekly.md"


def log(msg: str) -> None:
    print(f"[{date.today().isoformat()}] {msg}", file=sys.stderr)


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(REPO), *args],
        capture_output=True,
        text=True,
    )


def extract_summary(memo_path: Path) -> list[str]:
    if not memo_path.exists():
        return []
    text = memo_path.read_text(encoding="utf-8")
    match = re.search(r"## Summary\s*\n(.*?)(?:\n##|\Z)", text, re.S)
    if not match:
        return []
    bullets = [line.strip() for line in match.group(1).splitlines() if line.strip()]
    return bullets


def main() -> int:
    pull = git("pull", "--ff-only")
    if pull.returncode != 0:
        log(f"git pull failed, aborting: {pull.stderr.strip()}")
        return 1

    if not INDEX_TSV.exists():
        log("no .index.tsv yet -- daily cloud routine hasn't produced any memos, nothing to do")
        return 0

    synced_ids = set()
    if SYNCED_IDS.exists():
        synced_ids = {line.strip() for line in SYNCED_IDS.read_text().splitlines() if line.strip()}

    rows = []
    for line in INDEX_TSV.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) != 4:
            log(f"skipping malformed index row: {line!r}")
            continue
        video_id, published, filename, title = parts
        if video_id not in synced_ids:
            rows.append((video_id, published, filename, title))

    if not rows:
        log("no new memos since last weekly sync, nothing to do")
        return 0

    rows.sort(key=lambda r: r[1])  # oldest first within the week

    lines = [f"## Week of {date.today().isoformat()}", ""]
    for video_id, published, filename, title in rows:
        url = f"https://www.youtube.com/watch?v={video_id}"
        lines.append(f"### [{title}]({url}) — {published}")
        bullets = extract_summary(MEMOS_DIR / filename)
        if bullets:
            lines.extend(bullets)
        else:
            lines.append(f"- (summary unavailable, see memo: memos/promethean-updates/{filename})")
        lines.append("")
    lines.append("---")
    lines.append("")

    DIGEST_MD.parent.mkdir(parents=True, exist_ok=True)
    with DIGEST_MD.open("a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    with SYNCED_IDS.open("a", encoding="utf-8") as f:
        for video_id, *_ in rows:
            f.write(video_id + "\n")

    add = git("add", str(SYNCED_IDS.relative_to(REPO)))
    commit = git("commit", "-m", f"Sync {len(rows)} Promethean Updates memo(s) to weekly digest")
    push = git("push")
    if commit.returncode != 0 and "nothing to commit" not in commit.stdout:
        log(f"git commit issue: {commit.stderr.strip()}")
    elif push.returncode != 0:
        log(f"git push failed: {push.stderr.strip()}")

    log(f"appended {len(rows)} entr{'y' if len(rows) == 1 else 'ies'} to {DIGEST_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
