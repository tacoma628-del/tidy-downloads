import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import maintain as m


def touch(path: Path, age_days: float = 0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x")
    ts = time.time() - age_days * 86400
    os.utime(path, (ts, ts))


class MaintainTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_only_old_screenshots_are_found(self) -> None:
        touch(self.root / "Screenshot 2026-01-01 at 9.00.png", age_days=60)
        touch(self.root / "Screenshot 2026-09-20 at 9.00.png", age_days=2)
        touch(self.root / "Budget.xlsx", age_days=90)
        found = m.find_old_screenshots(self.root, 30)
        self.assertEqual([p.name for p in found], ["Screenshot 2026-01-01 at 9.00.png"])

    def test_preview_does_not_move_screenshots(self) -> None:
        touch(self.root / "desk/Screenshot a.png", age_days=60)
        trash = self.root / "trash"
        trash.mkdir()
        m.task_old_screenshots(False, folder=self.root / "desk", trash=trash)
        self.assertTrue((self.root / "desk/Screenshot a.png").exists())
        self.assertEqual(list(trash.iterdir()), [])

    def test_apply_moves_to_trash_without_overwrite(self) -> None:
        touch(self.root / "desk/Screenshot a.png", age_days=60)
        trash = self.root / "trash"
        touch(trash / "Screenshot a.png")
        m.task_old_screenshots(True, folder=self.root / "desk", trash=trash)
        self.assertFalse((self.root / "desk/Screenshot a.png").exists())
        self.assertTrue((trash / "Screenshot a-2.png").exists())

    def test_junk_dirs_found_but_not_inside_them(self) -> None:
        junk = self.root / "proj/node_modules"
        touch(junk / "pkg/node_modules/x.js")
        old = time.time() - 60 * 86400
        os.utime(junk, (old, old))
        found = [p for p, _ in m.find_junk_dirs(self.root, 30)]
        self.assertEqual(found, [junk])

    def test_report_overwrites(self) -> None:
        report = self.root / "r.md"
        report.write_text("old stuff")
        text = m.build_report([("A", ["line"])], apply=False)
        report.write_text(text)
        self.assertNotIn("old stuff", report.read_text())
        self.assertIn("## A", report.read_text())


if __name__ == "__main__":
    unittest.main()
