"""Subprocess smoke tests, entirely on synthetic fixtures in temporary folders."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from helpers import document


class CliTests(unittest.TestCase):
    def run_cli(self, *args):
        root = Path(__file__).resolve().parents[1]
        env = os.environ | {'PYTHONPATH': str(root / 'src')}
        return subprocess.run([sys.executable, '-m', 'style_compiler', *map(str, args)],
                              capture_output=True, text=True, env=env, check=False)

    def test_synthetic_extract_plan_apply_roundtrip(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            source, plan, output = (folder / name for name in ('source.json', 'plan.json', 'output.json'))
            d = document()
            source.write_text(json.dumps(d.to_dict()), encoding='utf-8')
            measured = self.run_cli('extract', source)
            self.assertEqual(measured.returncode, 0, measured.stderr)
            self.assertTrue(json.loads(measured.stdout)['provenance']['is_synthetic'])
            proposed = self.run_cli('plan', source, '--max-sentences', 1, '-o', plan)
            self.assertEqual(proposed.returncode, 0, proposed.stderr)
            denied = self.run_cli('apply', source, '--plan', plan, '-o', output)
            self.assertEqual(denied.returncode, 2)
            self.assertFalse(output.exists())
            applied = self.run_cli('apply', source, '--plan', plan, '--semantic-review-approved', '-o', output)
            self.assertEqual(applied.returncode, 0, applied.stderr)
            self.assertEqual(json.loads(output.read_text())['text'].replace('\n', ''), d.text)

    def test_malformed_document_no_traceback(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'bad.json'
            path.write_text('[]')
            result = self.run_cli('extract', path)
            self.assertEqual(result.returncode, 2)
            self.assertNotIn('Traceback', result.stderr)

    def test_malformed_partition_no_traceback(self):
        with tempfile.TemporaryDirectory() as folder:
            source, part = Path(folder) / 'docs.jsonl', Path(folder) / 'partition.json'
            source.write_text(json.dumps(document().to_dict()) + '\n')
            part.write_text('{}')
            result = self.run_cli('fit', source, '--partition', part, '--cohort', 'H_G')
            self.assertEqual(result.returncode, 2)
            self.assertNotIn('Traceback', result.stderr)
