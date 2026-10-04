import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class CliTests(unittest.TestCase):
    def run_cli(self, *args):
        root = Path(__file__).resolve().parents[1]
        return subprocess.run([sys.executable, "-m", "style_compiler", *map(str, args)],
            env=os.environ | {"PYTHONPATH": str(root / "src"), "PYTHONIOENCODING": "gbk"},
            capture_output=True, encoding="utf-8", check=False)

    def test_plain_file_preserves_bytes_hash_and_offsets(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "source.txt"
            raw = "\ufeff甲。\r\n乙乙。".encode()
            path.write_bytes(raw)
            run = self.run_cli("analyze", path)
            self.assertEqual(run.returncode, 0, run.stderr)
            result = json.loads(run.stdout)
            self.assertEqual(result["surface"]["text_sha256"], hashlib.sha256(raw).hexdigest())
            self.assertEqual(result["surface"]["sentences"][1]["start"], 5)
            self.assertEqual(result["linguistic"]["status"], "unavailable")

    def test_protected_formula_drift_exits_two(self):
        with tempfile.TemporaryDirectory() as folder:
            original, final = Path(folder) / "a.txt", Path(folder) / "b.txt"
            original.write_text("若 $x>0$，结论成立。", encoding="utf-8")
            final.write_text("若 $x>=0$，结论成立。", encoding="utf-8")
            run = self.run_cli("check", original, final)
            self.assertEqual(run.returncode, 2, run.stderr)
            self.assertTrue(json.loads(run.stdout)["blockers"])

    def test_no_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            source, out = Path(folder) / "source.txt", Path(folder) / "out.json"
            source.write_text("甲。", encoding="utf-8")
            out.write_bytes(b"keep")
            self.assertEqual(self.run_cli("analyze", source, "-o", out).returncode, 2)
            self.assertEqual(out.read_bytes(), b"keep")

    def test_compile_targets_one_skill_and_preserves_its_body(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "mathematician-humanizer"
            target.mkdir()
            body = target / "SKILL.md"
            body.write_bytes(b"keep skill body")
            run = self.run_cli("compile", "--research", root / "research", "--skill", target)
            self.assertEqual(run.returncode, 0, run.stderr)
            result = json.loads(run.stdout)
            for path in result["outputs"]:
                self.assertTrue((target / path).is_file())
            self.assertEqual(body.read_bytes(), b"keep skill body")
            self.assertFalse((target / "mathematician-humanizer").exists())

    def test_missing_model_or_invalid_input_has_clean_error(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "input.txt"
            path.write_text("甲。", encoding="utf-8")
            calls = [("analyze", path, "--models", Path(folder) / "missing"), ("summarize", path)]
            for args in calls:
                run = self.run_cli(*args)
                self.assertEqual(run.returncode, 2)
                self.assertNotIn("Traceback", run.stderr)
                self.assertFalse((Path(folder) / "missing").exists())
