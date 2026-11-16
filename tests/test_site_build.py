import importlib.util
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch


@unittest.skipUnless(shutil.which("git"), "Pinned source export requires Git")
class PinnedSiteSourceTests(unittest.TestCase):
    def test_export_reads_fixed_git_bytes_despite_worktree_line_ending_conversion(self):
        root = Path(__file__).resolve().parents[1]
        spec = importlib.util.spec_from_file_location("humanizer_site_build", root / "site/build.py")
        build = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(build)
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            subprocess.run(["git", "init", "-q", str(folder)], check=True, capture_output=True)
            path = folder / "license.txt"
            original = b"MIT License\nCopyright notice.\n"
            path.write_bytes(original)
            subprocess.run(["git", "-c", "core.autocrlf=false", "add", "license.txt"], cwd=folder, check=True, capture_output=True)
            tree = subprocess.run(["git", "write-tree"], cwd=folder, check=True, capture_output=True, text=True).stdout.strip()
            path.write_bytes(original.replace(b"\n", b"\r\n"))
            with patch.object(build, "ROOT", folder):
                exported = build.committed_bytes(tree, "license.txt")
            self.assertEqual(exported, original)
            self.assertNotEqual(exported, path.read_bytes())
