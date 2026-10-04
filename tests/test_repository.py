"""Check the single-skill delivery and the historical evidence it consumes."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile
import unittest

from style_compiler.profiles import compile_profiles

ROOT = Path(__file__).resolve().parents[1]


class DeliveryTests(unittest.TestCase):
    def test_exactly_one_skill(self):
        skills = list(ROOT.rglob("SKILL.md"))
        self.assertEqual(skills, [ROOT / "SKILL.md"])
        self.assertFalse(skills[0].is_symlink())
        self.assertFalse((ROOT / "skills").exists())

    def test_committed_cards_match_rebuild(self):
        actual = json.loads((ROOT / "build.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as folder:
            rebuilt = compile_profiles(ROOT / "research", Path(folder))
        self.assertEqual(actual, rebuilt)
        for name, digest in actual["outputs"].items():
            self.assertEqual(hashlib.sha256((ROOT / name).read_bytes()).hexdigest(), digest)

    def test_minimal_install_has_every_skill_reference_without_runtime(self):
        with tempfile.TemporaryDirectory() as folder:
            installed = Path(folder) / "mathematician-humanizer"
            installed.mkdir()
            shutil.copyfile(ROOT / "SKILL.md", installed / "SKILL.md")
            for name in ("references", "agents"):
                shutil.copytree(ROOT / name, installed / name)
            for path in installed.rglob("*.md"):
                self.assert_local_links(path)
            self.assertFalse((installed / "src").exists())
            self.assertFalse((installed / "research").exists())
            self.assertTrue((installed / "references/upstream-LICENSE.txt").exists())

    def test_skill_identity_and_version_match_maintenance_files(self):
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertRegex(skill, r"\A---\nname: mathematician-humanizer\ndescription: \|")
        version = re.search(r'(?m)^  version: "(\d+\.\d+\.\d+)"$', skill).group(1)
        self.assertIn("## " + version, (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"))
        self.assertIn("$mathematician-humanizer", (ROOT / "agents/openai.yaml").read_text(encoding="utf-8"))

    def assert_local_links(self, path):
        for match in re.finditer(r"\[[^\]]*\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
            target = match.group(1)
            if target.startswith(("https://", "http://", "#")):
                continue
            with self.subTest(file=path, target=target):
                self.assertTrue((path.parent / target.split("#")[0]).exists())

    def test_historical_mathematician_receipts_bind_the_actual_example_bytes(self):
        for path in (ROOT / "examples/mathematician").glob("*.txt"):
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            review = json.loads(path.with_suffix(".review.json").read_text(encoding="utf-8"))
            suffix = ".measurement.json" if path.name.startswith("english") else ".zh-measurement.json"
            measurement = json.loads(path.with_suffix(suffix).read_text(encoding="utf-8"))
            with self.subTest(example=path.name):
                self.assertEqual(review["text_sha256"], digest)
                self.assertEqual(measurement["text_sha256"], digest)

    def test_markdown_local_links_exist(self):
        paths = [ROOT / "README.md", ROOT / "SKILL.md", *(ROOT / "docs").glob("*.md"),
                 *(ROOT / "references").rglob("*.md"),
                 *(ROOT / "examples").rglob("*.md")]
        for path in paths:
            self.assert_local_links(path)
