"""Synthetic fixtures only: software/safety tests, never linguistic evidence."""
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import struct
import tempfile
import unittest
import warnings
import zipfile
import zlib

import wikiconv_zip_audit as audit

CANARY = "SYNTHETIC_PRIVATE_CANARY_NOT_CORPUS_DATA"


def record(key, conversation, *, header=False, speaker="synthetic-speaker", timestamp=1):
    return {"id": key, "conversation_id": conversation, "speaker": speaker,
            "reply-to": None, "timestamp": timestamp, "text": CANARY,
            "meta": {"is_section_header": header, "original": None,
                     "modification": [], "deletion": [], "restoration": []}}


def historical(item):
    item = deepcopy(item)
    item["root"] = item.pop("conversation_id")
    item["reply_to"] = item.pop("reply-to")
    item["meta_dict"] = item.pop("meta")
    for role in audit.ROLES:
        item["meta_dict"].pop(role, None)
    item["speaker"] = {"id": item["speaker"], "speaker_id": "synthetic-external-key"}
    return item


def fixture():
    root = record("synthetic-root", "synthetic-root", header=True)
    comment = record("synthetic-comment", "synthetic-root", timestamp=2)
    comment["reply-to"] = root["id"]
    original = record("synthetic-original", root["id"], timestamp=1)
    original["reply-to"] = root["id"]
    comment["meta"]["original"] = historical(original)
    comment["meta"]["modification"] = [historical(comment)]
    return [root, comment]


def payload(records=None):
    records = fixture() if records is None else records
    return {
        "utterances.jsonl": "\n".join(json.dumps(item) for item in records),
        "speakers.json": json.dumps({"synthetic-speaker": {"meta": {"name": CANARY}}}),
        "conversations.json": json.dumps({"synthetic-root": {"meta": {"page_type": CANARY}}}),
        "corpus.json": "{}", "index.json": '{"version": 1}',
    }


def zip_bytes(parts, *, compression=zipfile.ZIP_DEFLATED):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=compression) as archive:
        for name, content in parts.items():
            archive.writestr(name, content)
    return stream.getvalue()


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="synthetic-audit-")
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / (CANARY + ".zip")

    def write(self, parts=None, raw=None):
        self.path.write_bytes(raw if raw is not None else zip_bytes(parts or payload()))
        return self.path

    def invoke(self, args=None):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = audit.main(args if args is not None else [str(self.path)])
        for output in (out.getvalue(), err.getvalue()):
            self.assertNotIn(CANARY, output)
            self.assertNotIn(self.tmp.name, output)
            self.assertNotIn("synthetic-speaker", output)
            self.assertNotIn("synthetic-comment", output)
        return code, out.getvalue(), err.getvalue()

    def rejected(self, parts=None, raw=None, error=None):
        self.write(parts, raw)
        code, out, err = self.invoke()
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        parsed = json.loads(err)
        self.assertEqual(set(parsed), {"error"})
        if error:
            self.assertEqual(parsed["error"], error)

    def test_synthetic_counts_mapping_and_no_leak(self):
        self.write()
        code, out, err = self.invoke()
        self.assertEqual((code, err), (0, ""))
        result = json.loads(out)
        self.assertEqual(result["top_level_records"], 2)
        self.assertEqual(result["section_headers_true"], 1)
        self.assertEqual(result["serialized_views"], 4)
        self.assertEqual(result["distinct_event_ids"], 3)
        self.assertEqual(result["field_forms"]["nested_history"]["reply_underscore"], 2)
        self.assertEqual(result["field_forms"]["nested_history"]["speaker_object"], 2)
        self.assertEqual(result["nonheader_top_original_speaker_key_differences"], 0)
        self.assertEqual(result["conversation_page_type_counts"]["other_or_unknown"], 1)
        self.assertNotIn("excluded", out)
        self.assertNotIn("H_G", out)

    def test_hash_pin(self):
        self.write()
        digest = hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.assertEqual(self.invoke([str(self.path), "--expected-sha256", digest])[0], 0)
        self.assertEqual(self.invoke([str(self.path), "--expected-sha256", "0" * 64])[0], 2)
        self.assertEqual(self.invoke([str(self.path), "--expected-sha256", CANARY])[0], 2)

    def test_header_unknown_and_missing_history_not_zero_evidence(self):
        item = record("synthetic-root", "synthetic-root")
        item["meta"] = {}
        result = audit.audit(self.write(payload([item])))
        self.assertEqual(result["section_header_unknown"], 1)
        self.assertEqual(result["section_headers_false"], 0)
        self.assertEqual(result["missing_history_container_fields"]["modification"], 1)

    def test_conflicting_aliases(self):
        for first, second, value in (("reply-to", "reply_to", "synthetic-other"),
                                     ("conversation_id", "root", "synthetic-other"),
                                     ("meta", "meta_dict", {})):
            with self.subTest(field=first):
                records = fixture()
                records[0][second] = value
                self.rejected(payload(records), error="conflicting_field_aliases")

    def test_equal_aliases_supported(self):
        records = fixture()
        records[0]["reply_to"] = records[0]["reply-to"]
        records[0]["root"] = records[0]["conversation_id"]
        result = audit.audit(self.write(payload(records)))
        self.assertEqual(result["field_forms"]["top_level"]["reply_underscore"], 1)

    def test_key_difference_without_authorship_claim(self):
        records = fixture()
        records[1]["meta"]["original"]["speaker"]["id"] = "synthetic-other"
        result = audit.audit(self.write(payload(records)))
        self.assertEqual(result["nonheader_top_original_speaker_key_differences"], 1)
        self.assertEqual(result["same_text_among_nonheader_key_differences"], 1)
        self.assertEqual(result["selected_lineages"][1]["status"], "no_unselected_candidate")

    def test_unknown_speaker_not_key_difference(self):
        records = fixture()
        records[1]["meta"]["original"]["speaker"] = {}
        result = audit.audit(self.write(payload(records)))
        self.assertEqual(result["nonheader_top_original_speaker_key_differences"], 0)
        self.assertEqual(result["field_forms"]["nested_history"]["speaker_unknown"], 1)

    def test_duplicate_top_rejected_nested_duplicate_allowed(self):
        records = fixture()
        self.rejected(payload(records + [records[0]]), error="duplicate_top_level_id")
        result = audit.audit(self.write(payload(records)))
        self.assertEqual(result["serialized_views"] - result["distinct_event_ids"], 1)

    def test_unsupported_types(self):
        for field, value in (("id", True), ("timestamp", True), ("text", None),
                             ("speaker", [CANARY]), ("conversation_id", 4)):
            with self.subTest(field=field):
                records = fixture()
                records[0][field] = value
                self.rejected(payload(records), error="unsupported_schema")

    def test_unknown_header_value_rejected(self):
        records = fixture()
        records[0]["meta"]["is_section_header"] = "false"
        self.rejected(payload(records), error="unsupported_schema")

    def test_duplicate_json_key_nonfinite_and_malformed_json(self):
        for value in ('{"version":1,"version":2}', '{"version":NaN}',
                      '{"version":true}', '{"version":' + CANARY + '}', '[]'):
            with self.subTest(value=value):
                parts = payload()
                parts["index.json"] = value
                self.rejected(parts)

    def test_nested_history_depth_rejected(self):
        records = fixture()
        records[1]["meta"]["original"]["meta_dict"]["original"] = {"id": CANARY}
        self.rejected(payload(records), error="nested_history_depth")

    def test_deterministic_selection_independent_of_serialization_order(self):
        records = fixture()
        extra = record("synthetic-later", "synthetic-second-root", timestamp=4)
        extra["reply-to"] = "synthetic-missing"
        records.append(extra)
        first = audit.audit(self.write(payload(records)))
        second = audit.audit(self.write(payload(list(reversed(records)))))
        del first["archive"], second["archive"]
        self.assertEqual(first, second)
        self.assertEqual(first["selected_lineages"][2]["top_level_records"], 1)

    def test_reference_missing_cross_conversation_and_ambiguous_ids(self):
        records = fixture()
        records[1]["meta"]["original"]["root"] = "synthetic-other-root"
        extra = record("synthetic-extra", "synthetic-third-root")
        extra["reply-to"] = "synthetic-comment"
        records.append(extra)
        result = audit.audit(self.write(payload(records)))
        self.assertEqual(result["top_reply_against_all_views"]["target_in_other_conversation_only"], 1)
        self.assertEqual(result["history_views_with_different_conversation_from_container"], 1)
        records[1]["meta"]["original"]["id"] = "synthetic-comment"
        result = audit.audit(self.write(payload(records)))
        self.assertEqual(result["top_reply_against_all_views"]["target_id_in_multiple_conversations"], 1)

    def test_explicit_type_absent_vs_null(self):
        records = fixture()
        records[0]["type"] = None
        result = audit.audit(self.write(payload(records)))
        self.assertEqual(result["explicit_type_key_absent_views"], 3)
        self.assertEqual(result["explicit_type_value_null_or_absent_views"], 4)

    def test_lineage_over_limit_reported_not_resampled(self):
        records = fixture()
        records += [record(f"synthetic-extra-{n}", "synthetic-root", timestamp=n+3) for n in range(48)]
        result = audit.audit(self.write(payload(records)))
        selected = result["selected_lineages"][0]
        self.assertEqual(selected["status"], "exceeds_view_bound")
        self.assertNotIn("reply_references", selected)

    def test_nonzip_and_compressed_limit(self):
        self.rejected(raw=(CANARY + " not a ZIP").encode(), error="not_supported_zip")
        self.rejected(raw=b"X" * (audit.MAX_ARCHIVE_BYTES + 1), error="archive_size_limit")

    def test_unsafe_names_unknown_members_and_missing_members(self):
        for name in ("../" + CANARY, "/" + CANARY, CANARY + ".py", "dir/"):
            parts = payload()
            parts[name] = CANARY
            self.rejected(parts, error="unsupported_zip_members")
        parts = payload()
        del parts["index.json"]
        self.rejected(parts, error="unsupported_zip_members")

    def test_symlink_member(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            for name, content in payload().items():
                info = zipfile.ZipInfo(name)
                info.create_system = 3
                info.external_attr = (stat.S_IFLNK | 0o777) << 16
                archive.writestr(info, content)
        self.rejected(raw=stream.getvalue(), error="unsafe_member_type")

    def test_duplicate_zip_member_and_member_limit(self):
        stream = io.BytesIO(zip_bytes(payload()))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(stream, "a") as archive:
                archive.writestr("index.json", "{}")
        self.rejected(raw=stream.getvalue(), error="duplicate_zip_member")
        self.rejected({f"synthetic-{i}": "{}" for i in range(17)}, error="member_count_limit")

    def test_decompression_and_ratio_limits(self):
        parts = payload()
        parts["corpus.json"] = " " * (audit.MAX_UNCOMPRESSED_BYTES + 1)
        self.rejected(parts, error="uncompressed_size_limit")
        parts["corpus.json"] = " " * 100000
        self.rejected(parts, error="compression_ratio_limit")

    def test_encryption_compression_crc_and_bad_utf8(self):
        for offset, value, expected in ((8, 1, "encrypted_member"),
                                        (10, 99, "unsupported_compression")):
            blob = bytearray(zip_bytes(payload(), compression=zipfile.ZIP_STORED))
            central = blob.index(b"PK\x01\x02")
            struct.pack_into("<H", blob, central + offset, value)
            self.rejected(raw=bytes(blob), error=expected)
        parts = payload()
        parts["corpus.json"] = b"\xff"
        self.rejected(parts)
        blob = bytearray(zip_bytes(payload(), compression=zipfile.ZIP_STORED))
        central = blob.index(b"PK\x01\x02")
        struct.pack_into("<I", blob, central + 16, 0)  # Incorrect CRC, no input text in error.
        self.rejected(raw=bytes(blob))

    def test_forged_short_uncompressed_size_does_not_hide_expansion(self):
        for suffix, expected in ((" " * (3 * 1024 * 1024), "uncompressed_size_limit"),
                                 ("synthetic hidden non-JSON bytes", "member_size_mismatch")):
            with self.subTest(expected=expected):
                parts = payload()
                parts["corpus.json"] = "{}" + suffix
                blob = bytearray(zip_bytes(parts))
                with zipfile.ZipFile(io.BytesIO(blob)) as archive:
                    local = archive.getinfo("corpus.json").header_offset
                short_crc = zlib.crc32(b"{}")
                struct.pack_into("<I", blob, local + 14, short_crc)
                struct.pack_into("<I", blob, local + 22, 2)
                central = blob.index(b"PK\x01\x02")
                while blob[central:central+4] == b"PK\x01\x02":
                    name_len, extra_len, comment_len = struct.unpack_from("<HHH", blob, central+28)
                    name = blob[central+46:central+46+name_len]
                    if name == b"corpus.json":
                        struct.pack_into("<I", blob, central+16, short_crc)
                        struct.pack_into("<I", blob, central+24, 2)
                    central += 46 + name_len + extra_len + comment_len
                self.rejected(raw=bytes(blob), error=expected)

    def test_falsey_invalid_nested_histories_rejected(self):
        for key, value in (("original", 0), ("original", {}), ("modification", {})):
            with self.subTest(key=key, value=value):
                records = fixture()
                records[1]["meta"]["original"]["meta_dict"][key] = value
                self.rejected(payload(records))

    def test_overflow_float_in_unused_metadata_rejected(self):
        parts = payload()
        parts["corpus.json"] = '{"synthetic_value":1e999}'
        self.rejected(parts, error="nonfinite_json_number")

    def test_literal_unicode_line_separator_is_text_not_record_boundary(self):
        records = fixture()
        records[0]["text"] = "synthetic left\u2028synthetic right\u0085synthetic end"
        parts = payload(records)
        parts["utterances.jsonl"] = "\n".join(json.dumps(r, ensure_ascii=False) for r in records)
        result = audit.audit(self.write(parts))
        self.assertEqual(result["top_level_records"], 2)

    @unittest.skipUnless(hasattr(os, "mkfifo") and hasattr(os, "O_NONBLOCK"), "POSIX FIFO test")
    def test_nonregular_input_rejected_without_blocking(self):
        os.mkfifo(self.path)
        self.assertEqual(self.invoke()[0], 2)

    def test_cli_errors_never_echo_arguments(self):
        for args in ([str(self.path)], ["--unknown", CANARY], []):
            self.assertEqual(self.invoke(args)[0], 2)


if __name__ == "__main__":
    unittest.main()
