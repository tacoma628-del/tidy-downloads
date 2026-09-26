import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tidy_downloads as td


def touch(path: Path, mtime: datetime | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x")
    if mtime is not None:
        ts = mtime.timestamp()
        os.utime(path, (ts, ts))


class PlanMovesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.when = datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_pdf_goes_to_type_then_month(self) -> None:
        src = self.root / "invoice.pdf"
        touch(src, self.when)
        plan = td.plan_moves(self.root)
        self.assertEqual(plan, [(src, self.root / "PDFs" / "2026-08" / "invoice.pdf")])

    def test_png_and_zip_use_their_type_folders(self) -> None:
        png = self.root / "shot.png"
        zipf = self.root / "bundle.zip"
        touch(png, self.when)
        touch(zipf, self.when)
        dests = {src.name: dest for src, dest in td.plan_moves(self.root)}
        self.assertEqual(dests["shot.png"], self.root / "Images" / "2026-08" / "shot.png")
        self.assertEqual(dests["bundle.zip"], self.root / "Archives" / "2026-08" / "bundle.zip")

    def test_skips_incomplete_hidden_log_and_directories(self) -> None:
        touch(self.root / "done.pdf", self.when)
        touch(self.root / "chrome.crdownload", self.when)
        touch(self.root / "safari.download", self.when)
        touch(self.root / "file.part", self.when)
        touch(self.root / ".secret.pdf", self.when)
        touch(self.root / td.LOG_NAME, self.when)
        (self.root / "keep-folder").mkdir()
        (self.root / "PDFs").mkdir()
        names = {src.name for src, _ in td.plan_moves(self.root)}
        self.assertEqual(names, {"done.pdf"})

    def test_collision_gets_numeric_suffix(self) -> None:
        existing = self.root / "PDFs" / "2026-08" / "report.pdf"
        touch(existing, self.when)
        incoming = self.root / "report.pdf"
        touch(incoming, self.when)
        plan = td.plan_moves(self.root)
        self.assertEqual(plan, [(incoming, self.root / "PDFs" / "2026-08" / "report-2.pdf")])


class ApplyMovesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.when = datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_preview_does_not_move_files(self) -> None:
        src = self.root / "a.pdf"
        touch(src, self.when)
        plan = td.plan_moves(self.root)
        result = td.apply_moves(plan, apply=False, log_path=self.root / "tidy.log")
        self.assertTrue(src.exists())
        self.assertFalse((self.root / "PDFs" / "2026-08" / "a.pdf").exists())
        self.assertEqual(result.moved, 0)
        self.assertFalse((self.root / "tidy.log").exists())

    def test_apply_moves_and_logs(self) -> None:
        src = self.root / "a.pdf"
        touch(src, self.when)
        plan = td.plan_moves(self.root)
        log_path = self.root / "tidy.log"
        result = td.apply_moves(plan, apply=True, log_path=log_path)
        dest = self.root / "PDFs" / "2026-08" / "a.pdf"
        self.assertFalse(src.exists())
        self.assertTrue(dest.exists())
        self.assertEqual(result.moved, 1)
        log = log_path.read_text(encoding="utf-8")
        self.assertIn(str(src), log)
        self.assertIn(str(dest), log)


if __name__ == "__main__":
    unittest.main()
