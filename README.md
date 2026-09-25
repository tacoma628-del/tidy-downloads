# Tidy Downloads

Sort files sitting in your **Downloads** folder into `Type/YYYY-MM/` subfolders.

Preview is the default. Nothing moves until you pass `--apply`.

- Moves only (never deletes, never overwrites)
- Skips in-progress downloads (`.crdownload`, `.download`, `.part`, `.tmp`)
- Skips hidden files and folders already in the Downloads root
- Name collisions get a suffix (`report-2.pdf`)
- When applying, appends a line to `Downloads/tidy-downloads.log`

## How to use

Preview (safe, no changes):

```bash
python3 /Users/davidpalmeri/Developer/tidy-downloads/tidy_downloads.py
```

If the list looks right, apply it:

```bash
python3 /Users/davidpalmeri/Developer/tidy-downloads/tidy_downloads.py --apply
```

Optional: point at a different folder first (for a test run):

```bash
python3 /Users/davidpalmeri/Developer/tidy-downloads/tidy_downloads.py --dir /path/to/folder
python3 /Users/davidpalmeri/Developer/tidy-downloads/tidy_downloads.py --dir /path/to/folder --apply
```

## Layout

```
Downloads/
  PDFs/2026-08/invoice.pdf
  Images/2026-08/shot.png
  Archives/2026-08/bundle.zip
  Videos/
  Audio/
  Docs/
  Other/
```

Month comes from the file’s last-modified time (usually when it finished downloading).

## Undo a move

Each applied run appends `timestamp  old-path  ->  new-path` to `~/Downloads/tidy-downloads.log`. Move a file back with Finder, or:

```bash
mv ~/Downloads/PDFs/2026-08/invoice.pdf ~/Downloads/
```

## Mac maintenance (`maintain.py`)

One-button cleanup. Preview by default; `--apply` makes changes. Never hard-deletes.

```bash
python3 /Users/davidpalmeri/Developer/tidy-downloads/maintain.py --apply
```

Tidies Downloads and loose photos, trashes Desktop screenshots older than 30 days,
runs Homebrew update/upgrade/cleanup, and reports (only) unused brew packages, stale
dev folders, disk space, and dirty git repos. Each run overwrites
`Obsidian Vault/output/Mac Maintenance Report.md`. Toggle tasks in `TASKS` at the top
of the script, or run a subset with `--only homebrew disk`.

Wired to the **Mac maintenance** task (Manual) in the Claude desktop app: press **Run now**.
