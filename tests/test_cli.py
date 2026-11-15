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
            self.assertFalse((target / "build.json").exists())

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

    def test_compile_receipt_is_optional_and_existing_receipt_stops_before_writes(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            receipt = folder / "build-receipt.json"
            run = self.run_cli("compile", "--research", root / "research",
                               "--skill", folder / "skill", "-o", receipt)
            self.assertEqual(run.returncode, 0, run.stderr)
            data = json.loads(receipt.read_text(encoding="utf-8"))
            self.assertEqual(data["schema"], "style-cards-build/2")
            before = receipt.read_bytes()
            run = self.run_cli("compile", "--research", root / "research",
                               "--skill", folder / "blocked", "-o", receipt)
            self.assertEqual(run.returncode, 2)
            self.assertEqual(receipt.read_bytes(), before)
            self.assertFalse((folder / "blocked").exists())

    def test_paper_reconstruction_stage_and_audit_roundtrip(self):
        from math_reader.document import parse_document
        from test_math_reader import PAPER, annotations
        from test_exposition import DRAFT, review
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            source, docpath, annpath = folder / "paper.tex", folder / "paper.json", folder / "annotations.json"
            draftpath, reviewpath = folder / "draft.txt", folder / "review.json"
            source.write_bytes(PAPER.encode())
            doc = parse_document(PAPER, source=str(source))
            data = annotations(doc)
            annpath.write_text(json.dumps(data), encoding="utf-8")
            draftpath.write_text(DRAFT, encoding="utf-8")
            reviewpath.write_text(json.dumps(review(doc)), encoding="utf-8")
            run = self.run_cli("read-paper", source, "-o", docpath)
            self.assertEqual(run.returncode, 0, run.stderr)
            run = self.run_cli("reconstruct", docpath, annpath)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(json.loads(run.stdout)["prerequisite_order"], ["n1", "n2", "n4", "n6"])
            run = self.run_cli("prepare-explanation", "exposition", docpath, "--annotations", annpath)
            self.assertEqual(run.returncode, 0, run.stderr)
            run = self.run_cli("audit-exposition", docpath, annpath, draftpath, draftpath)
            self.assertEqual(run.returncode, 2, run.stderr)
            self.assertFalse(json.loads(run.stdout)["editorial_revision_allowed"])
            run = self.run_cli("audit-exposition", docpath, annpath, draftpath, draftpath, "--review", reviewpath)
            self.assertEqual(run.returncode, 0, run.stderr)

    def test_invalid_annotation_is_a_clean_error(self):
        from math_reader.document import parse_document
        from test_math_reader import PAPER, annotations
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            doc = parse_document(PAPER)
            data = annotations(doc)
            data["edges"][0]["evidence"][0]["quote"] = "invented evidence"
            for name, value in (("doc.json", doc), ("ann.json", data)):
                (folder / name).write_text(json.dumps(value), encoding="utf-8")
            run = self.run_cli("reconstruct", folder / "doc.json", folder / "ann.json")
            self.assertEqual(run.returncode, 2)
            self.assertNotIn("Traceback", run.stderr)
