"""Bounded, offline, aggregate-only audit of one ConvoKit WikiConv ZIP.

No extraction, network access, corpus code execution, prose/origin judgments or fit.
Only one level of history containers is supported; unfamiliar shapes fail closed.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import io
import json
import math
import os
import re
import stat
import struct
import sys
import zipfile
import zlib

MAX_ARCHIVE_BYTES = 64 * 1024
MAX_UNCOMPRESSED_BYTES = 2 * 1024 * 1024
MAX_MEMBERS = 16
MAX_COMPRESSION_RATIO = 200
MAX_LINEAGE_VIEWS = 50
MEMBERS = frozenset({"speakers.json", "conversations.json", "utterances.jsonl",
                     "corpus.json", "index.json"})
ROLES = ("original", "modification", "deletion", "restoration")
PAGE_TYPES = ("wikipedia_talk", "user_talk", "talk", "help_talk")


class AuditError(Exception):
    """Messages are fixed codes, never interpolated source data or paths."""


def require(condition, code="unsupported_schema"):
    if not condition:
        raise AuditError(code)


def _object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate_json_key")
        result[key] = value
    return result


def _nonfinite(_):
    raise AuditError("nonfinite_json_number")


def _finite_float(value):
    number = float(value)
    require(math.isfinite(number), "nonfinite_json_number")
    return number


def parse_json(blob):
    return json.loads(blob, object_pairs_hook=_object, parse_constant=_nonfinite,
                      parse_float=_finite_float)


def mapping(value):
    require(isinstance(value, dict))
    return value


def identifier(value, *, optional=False):
    require((optional and value is None) or (isinstance(value, str) and bool(value)))
    return value


def aliased(record, first, second, default=None):
    if first in record and second in record:
        require(json.dumps(record[first], sort_keys=True) == json.dumps(record[second], sort_keys=True),
                "conflicting_field_aliases")
    return record[first] if first in record else record.get(second, default)


def metadata(record):
    return mapping(aliased(record, "meta", "meta_dict", {}))


def speaker_key(record):
    value = record.get("speaker")
    if isinstance(value, dict):
        value = value.get("id")  # speaker_id is NOT assumed equivalent to id.
    return identifier(value, optional=True)


def normalize(record, role):
    mapping(record)
    meta = metadata(record)
    header = meta.get("is_section_header")
    require(header is None or type(header) is bool)
    stamp = record.get("timestamp")
    require(type(stamp) in (int, float) and math.isfinite(stamp))
    require(isinstance(record.get("text"), str))
    # Keep all source values in memory only. Nothing from this mapping is serialized.
    return {
        "id": identifier(record.get("id")), "speaker": speaker_key(record),
        "conversation": identifier(aliased(record, "conversation_id", "root")),
        "reply": identifier(aliased(record, "reply-to", "reply_to"), optional=True),
        "parent": identifier(meta.get("parent_id"), optional=True),
        "header": header, "timestamp": stamp, "text": record["text"], "role": role,
        "type_present": "type" in record or "type" in meta,
        "type_nonnull": record.get("type") is not None or meta.get("type") is not None,
    }


def member_bytes(blob, entry, remaining):
    """Validate the actual raw stream; ZipExtFile trusts declared output lengths."""
    offset = entry.header_offset
    require(0 <= offset <= len(blob) - 30, "invalid_local_header")
    fields = struct.unpack_from("<4s5H3I2H", blob, offset)
    signature, _, flags, method, _, _, crc, compressed, expanded, name_len, extra_len = fields
    require(signature == b"PK\x03\x04", "invalid_local_header")
    require(flags == entry.flag_bits and method == entry.compress_type, "local_header_mismatch")
    if not flags & 8:  # Bit 3 allows a data descriptor instead of local lengths/CRC.
        require((crc, compressed, expanded) == (entry.CRC, entry.compress_size, entry.file_size),
                "local_header_mismatch")
    name_end = offset + 30 + name_len
    start = name_end + extra_len
    end = start + entry.compress_size
    require(offset + 30 <= name_end <= start <= end <= len(blob), "invalid_member_region")
    local_name = blob[offset + 30:name_end].decode("utf-8" if flags & 0x800 else "cp437")
    require(local_name == entry.orig_filename, "local_header_mismatch")
    raw = blob[start:end]
    if method == zipfile.ZIP_STORED:
        require(len(raw) <= remaining, "uncompressed_size_limit")
        data = raw
    else:
        decoder = zlib.decompressobj(-15)
        data = decoder.decompress(raw, remaining + 1)
        require(len(data) <= remaining, "uncompressed_size_limit")
        require(decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail,
                "invalid_deflate_stream")
    require(len(data) == entry.file_size, "member_size_mismatch")
    require(len(data) <= max(len(raw), 1) * MAX_COMPRESSION_RATIO, "compression_ratio_limit")
    require(zlib.crc32(data) == entry.CRC, "crc_mismatch")
    return data, (offset, end)


def load_archive(path, expected_sha256=None):
    # Read at most the compressed limit + 1, even if the file grows after stat.
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0))
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        require(stat.S_ISREG(info.st_mode), "input_not_regular_file")
        require(info.st_size <= MAX_ARCHIVE_BYTES, "archive_size_limit")
        blob = stream.read(MAX_ARCHIVE_BYTES + 1)
    require(len(blob) <= MAX_ARCHIVE_BYTES, "archive_size_limit")
    require(blob.startswith(b"PK\x03\x04"), "not_supported_zip")
    digest = hashlib.sha256(blob).hexdigest()
    if expected_sha256 is not None:
        require(re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is not None,
                "invalid_expected_hash")
        require(digest == expected_sha256, "hash_mismatch")
    payload = {}
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        infos = archive.infolist()
        require(len(infos) <= MAX_MEMBERS, "member_count_limit")
        names = [entry.filename for entry in infos]
        require(len(names) == len(set(names)), "duplicate_zip_member")
        # Exact flat whitelist rejects traversal, absolute paths, renamed members,
        # directory entries, NUL-truncated names and executable additions.
        require(set(names) == MEMBERS, "unsupported_zip_members")
        declared_total = 0
        for entry in infos:
            require(entry.orig_filename == entry.filename, "unsafe_member_name")
            kind = stat.S_IFMT(entry.external_attr >> 16)
            require(kind in (0, stat.S_IFREG) and not entry.is_dir(), "unsafe_member_type")
            require(not entry.flag_bits & 1, "encrypted_member")
            require(entry.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED),
                    "unsupported_compression")
            require(entry.file_size <= MAX_UNCOMPRESSED_BYTES, "uncompressed_size_limit")
            declared_total += entry.file_size
            require(declared_total <= MAX_UNCOMPRESSED_BYTES, "uncompressed_size_limit")
            require(entry.file_size <= max(entry.compress_size, 1) * MAX_COMPRESSION_RATIO,
                    "compression_ratio_limit")
        actual_total, regions = 0, []
        for entry in infos:
            data, region = member_bytes(blob, entry, MAX_UNCOMPRESSED_BYTES - actual_total)
            require(all(region[1] <= old[0] or old[1] <= region[0] for old in regions),
                    "overlapping_member_regions")
            regions.append(region)
            actual_total += len(data)
            payload[entry.filename] = data.decode("utf-8")
    records = [parse_json(line) for line in payload["utterances.jsonl"].split("\n")
               if line.strip()]
    other = {name: mapping(parse_json(payload[name])) for name in MEMBERS
             if name != "utterances.jsonl"}
    return records, other, {"sha256": digest, "compressed_bytes": len(blob),
                           "uncompressed_bytes": actual_total, "member_count": len(infos)}


def field_forms(records):
    """Only predefined field labels; source keys and values are never emitted."""
    return {
        "reply_hyphen": sum("reply-to" in r for r in records),
        "reply_underscore": sum("reply_to" in r for r in records),
        "conversation_id": sum("conversation_id" in r for r in records),
        "root": sum("root" in r for r in records),
        "meta": sum("meta" in r for r in records),
        "meta_dict": sum("meta_dict" in r for r in records),
        "speaker_string": sum(isinstance(r.get("speaker"), str) for r in records),
        "speaker_object": sum(isinstance(r.get("speaker"), dict) for r in records),
        "speaker_unknown": sum(speaker_key(r) is None for r in records),
    }


def reference_counts(views, field, targets):
    refs = [view for view in views if view[field] is not None]
    return {
        "nonnull": len(refs),
        "missing_target": sum(view[field] not in targets for view in refs),
        "target_in_other_conversation_only": sum(
            view[field] in targets and view["conversation"] not in targets[view[field]]
            for view in refs),
        "target_id_in_multiple_conversations": sum(
            len(targets.get(view[field], ())) > 1 for view in refs),
    }


def audit(path, expected_sha256=None):
    raw_top, data, archive = load_archive(path, expected_sha256)
    top = [normalize(record, "top_level") for record in raw_top]
    require(len({view["id"] for view in top}) == len(top), "duplicate_top_level_id")
    top.sort(key=lambda view: (view["timestamp"], view["id"]))
    raw_by_id = {record["id"]: record for record in raw_top}
    histories, originals, raw_nested = {}, {}, []
    missing_history_fields = Counter()
    for view in top:
        meta = metadata(raw_by_id[view["id"]])
        related = []
        for role in ROLES:
            if role not in meta:
                missing_history_fields[role] += 1
            value = meta.get(role)
            if role == "original":
                require(value is None or isinstance(value, dict))
                entries = [] if value is None else [value]
            else:
                require(value is None or isinstance(value, list))
                entries = [] if value is None else value
            for record in entries:
                nested = normalize(record, role)
                nm = metadata(record)
                for key in ROLES:
                    inner = nm.get(key)
                    if key == "original":
                        require(inner is None, "nested_history_depth")
                    else:
                        require(inner is None or isinstance(inner, list))
                        require(not inner, "nested_history_depth")
                if role == "original":
                    originals[view["id"]] = nested
                related.append(nested)
                raw_nested.append(record)
        histories[view["id"]] = related
    nested = [view for group in histories.values() for view in group]
    views = top + nested
    targets, top_targets = {}, {}
    for view in views:
        targets.setdefault(view["id"], set()).add(view["conversation"])
    for view in top:
        top_targets.setdefault(view["id"], set()).add(view["conversation"])
    conversations = data["conversations.json"]
    speakers = data["speakers.json"]
    for key in conversations:
        identifier(key)
        metadata(mapping(conversations[key]))
    for key in speakers:
        identifier(key)
        mapping(speakers[key])
    version = data["index.json"].get("version")
    require(version is None or (type(version) is int and version >= 0))
    nonheaders = [view for view in top if view["header"] is False]
    def different(view):
        original = originals.get(view["id"])
        return (original is not None and original["speaker"] is not None
                and view["speaker"] is not None and original["speaker"] != view["speaker"])
    different_nonheaders = [view for view in nonheaders if different(view)]
    roles = Counter(view["role"] for view in views)
    page_counts = Counter()
    for record in conversations.values():
        value = metadata(record).get("page_type")
        bucket = value if isinstance(value, str) and value in PAGE_TYPES else "other_or_unknown"
        page_counts[bucket] += 1
    sizes = Counter(view["conversation"] for view in top)
    criteria = (
        ("modification_history", lambda v: any(h["role"] == "modification" for h in histories[v["id"]])),
        ("top_original_speaker_key_difference", different),
        ("missing_top_reply_target", lambda v: v["reply"] is not None and v["reply"] not in top_targets),
    )
    selected, used = [], set()
    for rank, (criterion, matches) in enumerate(criteria, 1):
        candidates = [view for view in nonheaders if matches(view)]
        candidate = next((v for v in candidates if v["conversation"] not in used), None)
        row = {"alias": f"L{rank}", "criterion": criterion,
               "candidate_conversations": len({v["conversation"] for v in candidates})}
        if candidate is None:
            row["status"] = "no_unselected_candidate"
        else:
            conversation = candidate["conversation"]
            used.add(conversation)
            members = [v for v in top if v["conversation"] == conversation]
            related = [v for v in views if v["conversation"] == conversation]
            row["status"] = "within_bound" if len(related) <= MAX_LINEAGE_VIEWS else "exceeds_view_bound"
            row["top_level_records"] = len(members)
            row["serialized_views"] = len(related)
            if row["status"] == "within_bound":
                row.update({
                    "nonheader_records": sum(v["header"] is False for v in members),
                    "distinct_event_ids": len({v["id"] for v in related}),
                    "history_view_counts": {role: sum(v["role"] == role for v in related) for role in ROLES},
                    "reply_references": reference_counts(related, "reply", targets),
                    "parent_references": reference_counts(related, "parent", targets),
                    "top_original_speaker_key_differences": sum(different(v) for v in members),
                })
        selected.append(row)
    return {
        "audit_schema_version": "1.0.0", "scope": "mechanical_structure_only",
        "archive": archive, "index_version_observed": version,
        "top_level_records": len(top),
        "section_headers_true": sum(v["header"] is True for v in top),
        "section_headers_false": len(nonheaders),
        "section_header_unknown": sum(v["header"] is None for v in top),
        "empty_top_level_texts": sum(not v["text"].strip() for v in top),
        "conversation_metadata_records": len(conversations), "speaker_metadata_records": len(speakers),
        "conversation_size_histogram": {str(n): count for n, count in sorted(Counter(sizes.values()).items())},
        "conversation_page_type_counts": {key: page_counts[key] for key in (*PAGE_TYPES, "other_or_unknown")},
        "missing_top_conversation_metadata": sum(v["conversation"] not in conversations for v in top),
        "missing_top_speaker_metadata": sum(v["speaker"] is not None and v["speaker"] not in speakers for v in top),
        "unknown_top_speaker_keys": sum(v["speaker"] is None for v in top),
        "missing_nested_speaker_metadata": sum(v["speaker"] is not None and v["speaker"] not in speakers for v in nested),
        "conversation_roots_absent_top": sum(key not in top_targets for key in conversations),
        "conversation_roots_absent_all_views": sum(key not in targets for key in conversations),
        "top_reply_against_top": reference_counts(top, "reply", top_targets),
        "top_reply_against_all_views": reference_counts(top, "reply", targets),
        "nested_reply_against_all_views": reference_counts(nested, "reply", targets),
        "history_view_counts": {role: roles[role] for role in ("top_level", *ROLES)},
        "missing_history_container_fields": {role: missing_history_fields[role] for role in ROLES},
        "history_views_with_different_conversation_from_container": sum(
            h["conversation"] != v["conversation"] for v in top for h in histories[v["id"]]),
        "serialized_views": len(views), "distinct_event_ids": len(targets),
        "explicit_type_key_absent_views": sum(not v["type_present"] for v in views),
        "explicit_type_value_null_or_absent_views": sum(not v["type_nonnull"] for v in views),
        "nonheader_top_original_speaker_key_differences": len(different_nonheaders),
        "same_text_among_nonheader_key_differences": sum(v["text"] == originals[v["id"]]["text"] for v in different_nonheaders),
        "field_forms": {"top_level": field_forms(raw_top), "nested_history": field_forms(raw_nested)},
        "selected_lineages": selected,
    }


class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        raise AuditError("invalid_arguments")


def main(argv=None):
    parser = SafeParser(description=__doc__)
    parser.add_argument("archive", help="local ZIP path; never downloaded or extracted")
    parser.add_argument("--expected-sha256", help="optional lowercase SHA-256 pin")
    try:
        args = parser.parse_args(argv)
        result = audit(args.archive, args.expected_sha256)
    except AuditError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2
    except (OSError, ValueError, TypeError, KeyError, OverflowError, RecursionError,
            RuntimeError, NotImplementedError, zipfile.BadZipFile, zlib.error, EOFError):
        # Parser/library exceptions may contain input bytes or local paths.
        print('{"error": "invalid_or_unreadable_input"}', file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
