"""Synthetic data only: validates ingestion boundaries, never corpus truth."""
import hashlib
import contextlib
import io
import json
import os
from pathlib import Path
import sqlite3
import struct
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import wikiconv_annual_census as annual
from wikiconv_annual_census import (Archive, AuditError, census, coverage, jsonl_records,
                                  object_items, sample_frame, views)


def record(key, speaker, reply, header=False):
    return {"id": key, "conversation_id": "root", "text": "synthetic fixture",
            "speaker": speaker, "reply-to": reply, "timestamp": 1483228800.,
            "meta": {"is_section_header": header, "parent_id": None,
                     "ancestor_id": "root", "original": None,
                     "modification": [], "deletion": [], "restoration": []}}


def fixture(path, *, missing=False, extra=False):
    rows = [record("root", "a", None, True), record("first", "a", "root"),
            record("second", "b", "missing" if missing else "first")]
    data = {"index.json": json.dumps({"version": 1}), "corpus.json": "{}",
            "speakers.json": json.dumps({"a": {}, "b": {}}),
            "conversations.json": json.dumps({"root": {"meta": {"page_type": "talk"}}}),
            "utterances.jsonl": "\n".join(json.dumps(r) for r in rows)}
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, text in data.items():
            archive.writestr(name, text)
        if extra:
            archive.writestr("../unwanted.py", "unexecuted")
    return hashlib.sha256(path.read_bytes()).hexdigest()


class AnnualCensusTests(unittest.TestCase):
    def test_streamed_mapping_utf8_and_duplicates(self):
        b='{"甲":{"value":"乙"},"other":{}}'.encode()
        self.assertEqual(list(object_items([b[i:i+2] for i in range(0,len(b),2)])),
                         [("甲", {"value": "乙"}), ("other", {})])
        with self.assertRaises(AuditError):
            list(object_items([b'{"x":{"duplicate":1,"duplicate":2}}']))

    def test_line_record_limit_and_nonfinite(self):
        with self.assertRaisesRegex(AuditError, "record_size_limit"):
            list(jsonl_records([b'{"text":"too long"}\n'], limit=5))
        with self.assertRaisesRegex(AuditError, "nonfinite_json_number"):
            list(jsonl_records([b'{"value":NaN}\n']))

    def test_nested_history_does_not_silently_flatten(self):
        top = record("first", "a", "root")
        original = record("prior", "a", "root")
        original["meta"]["original"] = record("hidden", "a", "root")
        top["meta"]["original"] = original
        with self.assertRaisesRegex(AuditError, "nested_history_depth"):
            list(views(top))

    def test_census_and_frozen_sample_are_separate(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, dbpath = Path(tmp)/"fixture.zip", Path(tmp)/"private.sqlite"
            sha = fixture(path)
            result = census(path, dbpath, expected_sha256=sha)
            self.assertEqual(result["counts"]["top_records"],3)
            self.assertEqual(result["frame"]["eligible"],1)
            self.assertTrue(result["source"]["all_raw_sizes_and_crcs_verified"])
            self.assertFalse(result["frame"]["complete_historical_context"])
            self.assertNotIn("synthetic fixture",json.dumps(result))
            sampled = sample_frame(dbpath, "ab"*32)
            self.assertEqual(sampled["inclusion_probability"],{"numerator":1,"denominator":1})
            self.assertEqual(coverage(dbpath)["sample_nonempty_nonheader_distinct_speaker_keys"],2)
            with self.assertRaisesRegex(AuditError,"sample_already_exists"):
                sample_frame(dbpath,"ab"*32)

    def test_missing_context_excluded_without_becoming_bad_origin(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, dbpath = Path(tmp)/"fixture.zip", Path(tmp)/"private.sqlite"
            sha = fixture(path, missing=True)
            result = census(path, dbpath, expected_sha256=sha)
            self.assertEqual(result["frame"]["eligible"],0)
            self.assertEqual(result["references"]["top"]["reply"]["missing_target"],1)
            self.assertEqual(result["H_G_admitted"],0)

    def test_database_limit_failure_cannot_enable_sampling(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, dbpath = Path(tmp)/"fixture.zip", Path(tmp)/"private.sqlite"
            sha = fixture(path)
            with patch.object(annual, "DATABASE_LIMIT", 1):
                with self.assertRaisesRegex(AuditError, "database_size_limit"):
                    census(path, dbpath, expected_sha256=sha)
            with self.assertRaisesRegex(AuditError, "census_incomplete"):
                sample_frame(dbpath, "ab"*32)

    def test_cli_error_does_not_echo_private_arguments(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            status = annual.main(["census", "PRIVATE_CANARY_ARCHIVE", "PRIVATE_CANARY_DB",
                                  "--expected-sha256", "PRIVATE_CANARY_HASH", "--unknown"])
        self.assertEqual(status, 1)
        self.assertNotIn("PRIVATE_CANARY", output.getvalue())
        self.assertIn("invalid_arguments", output.getvalue())

    @unittest.skipUnless(hasattr(os, "mkfifo"), "POSIX only")
    def test_nonregular_archive_does_not_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/"fixture.fifo"
            os.mkfifo(path)
            with self.assertRaisesRegex(AuditError, "input_not_regular_file"):
                Archive(path, "0"*64)

    def test_whitelist_and_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"fixture.zip"
            sha=fixture(path,extra=True)
            with self.assertRaisesRegex(AuditError,"unsupported_zip_members"):
                Archive(path,sha)
            sha=fixture(path)
            with self.assertRaisesRegex(AuditError,"hash_mismatch"):
                Archive(path,"0"*64)

    def test_crc_checked_on_actual_stream(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"fixture.zip";fixture(path)
            data=bytearray(path.read_bytes())
            # Corrupt both declared CRCs consistently; output data stays valid.
            local=data.index(b'PK\x03\x04');central=data.index(b'PK\x01\x02')
            for offset in [local+14,central+16]:
                crc=struct.unpack_from('<I',data,offset)[0]
                struct.pack_into('<I',data,offset,crc^1)
            path.write_bytes(data)
            a=Archive(path,hashlib.sha256(data).hexdigest())
            try:
                with self.assertRaisesRegex(AuditError,"crc_mismatch"):
                    list(a.chunks('index.json'))
            finally:a.close()

    def test_declared_smaller_output_cannot_hide_extra_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"fixture.zip";fixture(path)
            data=bytearray(path.read_bytes())
            local=data.index(b'PK\x03\x04');central=data.index(b'PK\x01\x02')
            for offset in [local+22,central+24]:struct.pack_into('<I',data,offset,1)
            path.write_bytes(data)
            a=Archive(path,hashlib.sha256(data).hexdigest())
            try:
                with self.assertRaisesRegex(AuditError,"member_size_mismatch"):
                    list(a.chunks('index.json'))
            finally:a.close()


if __name__ == '__main__':
    unittest.main()
