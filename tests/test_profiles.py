import copy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from style_compiler.profiles import compile_profiles, general_card

ROOT = Path(__file__).resolve().parents[1]


class ProfileTests(unittest.TestCase):
    def test_rebuild_is_deterministic_and_binds_sources(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder)
            first = compile_profiles(ROOT / "research", target)
            second = compile_profiles(ROOT / "research", target)
            self.assertEqual(first, second)
            self.assertEqual(first["supported_surface_observations"], ["F013", "F014", "F015", "F024", "F025"])
            for path, digest in first["outputs"].items():
                self.assertEqual(hashlib.sha256((target / path).read_bytes()).hexdigest(), digest)
            self.assertEqual({path.split("/")[0] for path in first["outputs"]}, {"references"})
            self.assertFalse(first["new_corpus_measurement"])

    def test_changed_source_rejected_before_any_output(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            shutil.copytree(ROOT / "research", folder / "research")
            path = folder / "research/general/paired-surface.json"
            path.write_bytes(path.read_bytes() + b" ")
            with self.assertRaisesRegex(ValueError, "changed"):
                compile_profiles(folder / "research", folder / "skills")
            self.assertFalse((folder / "skills").exists())

    def test_development_failure_is_not_compiled_as_supported(self):
        paired = json.loads((ROOT / "research/general/paired-surface.json").read_text(encoding="utf-8"))
        joint = json.loads((ROOT / "research/general/joint-reference.json").read_text(encoding="utf-8"))
        altered = copy.deepcopy(paired)
        next(row for row in altered["development_audit"]["features"] if row["feature_id"] == "F013")["inspection_supported"] = False
        _, supported = general_card(altered, joint)
        self.assertNotIn("F013", supported)

    def test_forged_replicated_direction_rejected(self):
        paired = json.loads((ROOT / "research/general/paired-surface.json").read_text(encoding="utf-8"))
        joint = json.loads((ROOT / "research/general/joint-reference.json").read_text(encoding="utf-8"))
        next(row for row in paired["development_audit"]["features"] if row["feature_id"] == "F013")["dev"]["human_minus_ai"] = -1
        with self.assertRaisesRegex(ValueError, "inconsistent"):
            general_card(paired, joint)
