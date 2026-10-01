"""Offline, bounded structural census of one already-authorized annual ZIP.

Outputs aggregate JSON only. A caller-selected SQLite file stores private source
IDs and structural relations, never publication-ready identities or gold labels.
No network, corpus code execution, model calls, linguistic features, or fitting.
"""
from __future__ import annotations

import argparse
from collections import Counter
import codecs
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import random
import re
import sqlite3
import stat
import struct
import sys
import zipfile
import zlib

from wikiconv_zip_audit import (AuditError, MEMBERS, PAGE_TYPES, ROLES, SafeParser,
                              identifier, mapping, metadata, normalize,
                              parse_json, require)

ARCHIVE_LIMIT = 81_000_000
EXPANDED_LIMIT = 1024**3
RECORD_LIMIT = 16 * 1024**2
DATABASE_LIMIT = 2 * 1024**3
CHUNK = 64 * 1024
SCANNER_VERSION = "wikiconv-annual-structural/0.1.0"


class Archive:
    """Validate actual DEFLATE output, rather than trusting declared ZIP sizes."""

    def __init__(self, path, expected_sha256, expected_bytes=None,
                 expected_expanded=None):
        require(re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is not None,
                "invalid_expected_hash")
        self.path = path
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0))
        try:
            require(stat.S_ISREG(os.fstat(descriptor).st_mode), "input_not_regular_file")
        except Exception:
            os.close(descriptor)
            raise
        self.stream = os.fdopen(descriptor, "rb")
        try:
            st = os.fstat(self.stream.fileno())
            require(stat.S_ISREG(st.st_mode), "input_not_regular_file")
            require(st.st_size <= ARCHIVE_LIMIT, "archive_size_limit")
            require(expected_bytes is None or st.st_size == expected_bytes,
                    "archive_size_mismatch")
            digest, count = hashlib.sha256(), 0
            while blob := self.stream.read(CHUNK):
                count += len(blob)
                require(count <= ARCHIVE_LIMIT, "archive_size_limit")
                digest.update(blob)
            require(digest.hexdigest() == expected_sha256, "hash_mismatch")
            self.sha256, self.compressed_bytes = digest.hexdigest(), count
            self.stream.seek(0)
            self.zip = zipfile.ZipFile(self.stream)
            entries = self.zip.infolist()
            require(len(entries) == 5, "unsupported_zip_members")
            names = [x.filename for x in entries]
            require(len(set(names)) == 5 and set(names) == MEMBERS,
                    "unsupported_zip_members")
            self.entries, self.regions = {}, {}
            declared = 0
            for e in entries:
                require(e.orig_filename == e.filename, "unsafe_member_name")
                require(stat.S_IFMT(e.external_attr >> 16) in (0, stat.S_IFREG)
                        and not e.is_dir(), "unsafe_member_type")
                # The verified archive has no data descriptors or encryption.
                require(e.flag_bits in (0, 0x800), "unsupported_zip_flags")
                require(e.compress_type in (0, 8), "unsupported_compression")
                require(e.file_size <= EXPANDED_LIMIT, "uncompressed_size_limit")
                require(e.file_size <= max(e.compress_size, 1) * 200,
                        "compression_ratio_limit")
                declared += e.file_size
                self.stream.seek(e.header_offset)
                header = self.stream.read(30)
                require(len(header) == 30, "invalid_local_header")
                h = struct.unpack("<4s5H3I2H", header)
                sig, _, flags, method, _, _, crc, comp, size, nl, xl = h
                require(sig == b"PK\x03\x04" and (flags, method, crc, comp, size)
                        == (e.flag_bits, e.compress_type, e.CRC,
                            e.compress_size, e.file_size), "local_header_mismatch")
                local_name = self.stream.read(nl).decode("utf-8" if flags & 0x800 else "cp437")
                require(local_name == e.orig_filename, "local_header_mismatch")
                start = e.header_offset + 30 + nl + xl
                end = start + e.compress_size
                require(0 <= e.header_offset < start <= end <= self.zip.start_dir,
                        "invalid_member_region")
                require(all(end <= a or e.header_offset >= b
                            for a, b, _ in self.regions.values()),
                        "overlapping_member_regions")
                self.regions[e.filename] = (e.header_offset, end, start)
                self.entries[e.filename] = e
            require(declared <= EXPANDED_LIMIT, "uncompressed_size_limit")
            require(expected_expanded is None or declared == expected_expanded,
                    "declared_expanded_mismatch")
            self.declared_total, self.actual_total = declared, 0
            self.verified = {}
        except Exception:
            self.stream.close()
            raise

    def chunks(self, name):
        require(name not in self.verified, "member_already_consumed")
        e = self.entries[name]
        start = self.regions[name][2]
        self.stream.seek(start)
        decoder = zlib.decompressobj(-15) if e.compress_type == 8 else None
        remaining, expanded, crc = e.compress_size, 0, 0
        while remaining:
            raw = self.stream.read(min(CHUNK, remaining))
            require(bool(raw), "truncated_member")
            remaining -= len(raw)
            pending = raw
            while pending:
                if decoder is None:
                    data, pending = pending, b""
                else:
                    data = decoder.decompress(pending, CHUNK)
                    pending = decoder.unconsumed_tail
                    require(not decoder.unused_data, "trailing_deflate_data")
                expanded += len(data)
                self.actual_total += len(data)
                require(expanded <= e.file_size, "member_size_mismatch")
                require(self.actual_total <= EXPANDED_LIMIT, "uncompressed_size_limit")
                crc = zlib.crc32(data, crc)
                if data:
                    yield data
        if decoder is not None:
            require(decoder.eof and not decoder.unused_data
                    and not decoder.unconsumed_tail, "invalid_deflate_stream")
        require(expanded == e.file_size, "member_size_mismatch")
        require(crc == e.CRC, "crc_mismatch")
        self.verified[name] = expanded

    def small_json(self, name):
        require(self.entries[name].file_size <= RECORD_LIMIT, "record_size_limit")
        return mapping(parse_json(b"".join(self.chunks(name))))

    def close(self):
        self.zip.close()
        self.stream.close()


def jsonl_records(chunks, limit=RECORD_LIMIT):
    pending, line_number, offset = bytearray(), 0, 0
    for chunk in chunks:
        pending.extend(chunk)
        while True:
            newline = pending.find(b"\n")
            if newline < 0:
                require(len(pending) <= limit, "record_size_limit")
                break
            require(newline <= limit, "record_size_limit")
            line = bytes(pending[:newline])
            del pending[:newline + 1]
            line_number += 1
            if line.strip():
                yield line_number, offset, mapping(parse_json(line))
            offset += newline + 1
    if pending:
        require(len(pending) <= limit, "record_size_limit")
        if pending.strip():
            yield line_number + 1, offset, mapping(parse_json(pending))


def object_items(chunks, limit=RECORD_LIMIT):
    """Incremental top-level JSON mapping; values and duplicate keys are checked."""
    utf8 = codecs.getincrementaldecoder("utf-8")()
    def texts():
        for chunk in chunks:
            yield utf8.decode(chunk)
        yield utf8.decode(b"", final=True)
    iterator, buffer, ended = iter(texts()), "", False

    def refill():
        nonlocal buffer, ended
        try:
            buffer += next(iterator)
        except StopIteration:
            ended = True

    def space():
        nonlocal buffer
        while True:
            buffer = buffer.lstrip()
            if buffer or ended:
                return
            refill()

    def char(expected):
        nonlocal buffer
        space()
        require(buffer.startswith(expected), "invalid_metadata_json")
        buffer = buffer[1:]

    decoder = json.JSONDecoder()
    def value():
        nonlocal buffer
        space()
        while True:
            require(len(buffer) <= limit + CHUNK, "record_size_limit")
            try:
                _, end = decoder.raw_decode(buffer)
                require(end <= limit, "record_size_limit")
                result = parse_json(buffer[:end])
                buffer = buffer[end:]
                return result
            except json.JSONDecodeError:
                require(not ended, "invalid_metadata_json")
                refill()

    char("{")
    space()
    if not buffer.startswith("}"):
        while True:
            key = identifier(value())
            char(":")
            yield key, mapping(value())
            space()
            if buffer.startswith("}"):
                break
            char(",")
    char("}")
    space()
    require(ended and not buffer, "trailing_metadata_content")


def views(record):
    def normalized(item, role):
        result = normalize(item, role)
        result["ancestor"] = identifier(metadata(item).get("ancestor_id"), optional=True)
        return result
    yield normalized(record, "top_level")
    meta = metadata(record)
    for role in ROLES:
        value = meta.get(role)
        if role == "original":
            require(value is None or isinstance(value, dict))
            group = [] if value is None else [value]
        else:
            require(value is None or isinstance(value, list))
            group = [] if value is None else value
        for nested in group:
            nm = metadata(mapping(nested))
            for inner_role in ROLES:
                inner = nm.get(inner_role)
                require(inner is None or (inner_role != "original" and inner == []),
                        "nested_history_depth")
            yield normalized(nested, role)


def scalar(db, sql):
    return db.execute(sql).fetchone()[0]


def census(path, private_database, *, expected_sha256, expected_bytes=None,
           expected_expanded=None):
    require(not Path(private_database).exists(), "database_already_exists")
    archive = Archive(path, expected_sha256, expected_bytes, expected_expanded)
    db = sqlite3.connect(private_database)
    try:
        db.executescript("""
          PRAGMA journal_mode=DELETE;
          CREATE TABLE control(key TEXT PRIMARY KEY, value TEXT);
          INSERT INTO control VALUES('status','incomplete');
          CREATE TABLE conversations(id TEXT PRIMARY KEY, page_type TEXT);
          CREATE TABLE speakers(id TEXT PRIMARY KEY);
          CREATE TABLE views(seq INTEGER PRIMARY KEY, rownum INTEGER, byte_offset INTEGER,
            role TEXT, id TEXT, conversation TEXT, reply TEXT, parent TEXT, ancestor TEXT,
            speaker TEXT, header INTEGER, timestamp REAL, chars INTEGER,
            nonempty INTEGER, text_sha256 TEXT, type_present INTEGER, type_nonnull INTEGER);
        """)
        index = archive.small_json("index.json")
        version = index.get("version")
        require(type(version) is int and version >= 0, "unsupported_index_version")
        archive.small_json("corpus.json")
        for key, record in object_items(archive.chunks("speakers.json")):
            db.execute("INSERT INTO speakers VALUES(?)", (key,))
        for key, record in object_items(archive.chunks("conversations.json")):
            value = metadata(record).get("page_type")
            bucket = value if isinstance(value, str) and value in PAGE_TYPES else "other_or_unknown"
            db.execute("INSERT INTO conversations VALUES(?,?)", (key, bucket))
        db.commit()
        forms = Counter()
        for rownum, offset, record in jsonl_records(archive.chunks("utterances.jsonl")):
            forms["reply_hyphen"] += "reply-to" in record
            forms["reply_underscore"] += "reply_to" in record
            forms["speaker_string"] += isinstance(record.get("speaker"), str)
            forms["speaker_object"] += isinstance(record.get("speaker"), dict)
            for v in views(record):
                db.execute("INSERT INTO views VALUES(NULL,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                    rownum, offset, v["role"], v["id"], v["conversation"], v["reply"],
                    v["parent"], v["ancestor"], v["speaker"], v["header"], v["timestamp"],
                    len(v["text"]), bool(v["text"].strip()),
                    hashlib.sha256(v["text"].encode("utf-8")).hexdigest(),
                    v["type_present"], v["type_nonnull"]))
            if rownum % 10000 == 0:
                db.commit()
                require(scalar(db, "PRAGMA page_count") * scalar(db, "PRAGMA page_size")
                        <= DATABASE_LIMIT, "database_size_limit")
        require(set(archive.verified) == MEMBERS and archive.actual_total == archive.declared_total,
                "archive_not_fully_verified")
        db.executescript("""
          CREATE INDEX view_id ON views(id);
          CREATE INDEX view_conv ON views(conversation);
          CREATE INDEX view_row ON views(rownum);
          CREATE INDEX view_role ON views(role);
          CREATE TABLE targets AS SELECT DISTINCT id,conversation FROM views;
          CREATE UNIQUE INDEX target_lookup ON targets(id,conversation);
          CREATE INDEX target_id ON targets(id);
          CREATE TABLE frame AS
          SELECT v.conversation AS id,
            SUM(v.role='top_level') AS top_records,
            SUM(v.role='top_level' AND v.header=0 AND v.nonempty=1) AS nonheader_records,
            COUNT(DISTINCT CASE WHEN v.role='top_level' AND v.header=0 AND v.nonempty=1
                    THEN v.speaker END) AS nonheader_speaker_keys,
            SUM(v.header IS NULL) AS unknown_headers,
            SUM(v.reply IS NOT NULL AND NOT EXISTS(SELECT 1 FROM targets t
                WHERE t.id=v.reply AND t.conversation=v.conversation)) AS unresolved_replies,
            SUM(v.parent IS NOT NULL AND NOT EXISTS(SELECT 1 FROM targets t
                WHERE t.id=v.parent AND t.conversation=v.conversation)) AS unresolved_parents,
            SUM(v.ancestor IS NOT NULL AND NOT EXISTS(SELECT 1 FROM targets t
                WHERE t.id=v.ancestor AND t.conversation=v.conversation)) AS unresolved_ancestors,
            SUM(EXISTS(SELECT 1 FROM targets t WHERE t.id=v.id
                AND t.conversation<>v.conversation)) AS conflicting_id_conversations,
            EXISTS(SELECT 1 FROM targets t WHERE t.id=v.conversation
                    AND t.conversation=v.conversation) AS root_in_source,
            EXISTS(SELECT 1 FROM conversations c WHERE c.id=v.conversation) AS metadata_present
          FROM views v GROUP BY v.conversation;
          CREATE UNIQUE INDEX frame_id ON frame(id);
          ALTER TABLE frame ADD COLUMN eligible INTEGER DEFAULT 0;
          UPDATE frame SET eligible=(nonheader_records>=2 AND nonheader_speaker_keys>=2
            AND unknown_headers=0 AND unresolved_replies=0 AND unresolved_parents=0
            AND unresolved_ancestors=0 AND conflicting_id_conversations=0
            AND root_in_source=1 AND metadata_present=1);
        """)
        top = "FROM views WHERE role='top_level'"
        duplicates = scalar(db, "SELECT COUNT(*) FROM (SELECT id " + top + " GROUP BY id HAVING COUNT(*)>1)")
        require(duplicates == 0, "duplicate_top_level_id")
        def refs(field, only_top):
            where = "v.role='top_level' AND " if only_top else ""
            q = f"FROM views v WHERE {where}v.{field} IS NOT NULL"
            return {"nonnull": scalar(db, "SELECT COUNT(*) " + q),
                    "missing_target": scalar(db, "SELECT COUNT(*) " + q +
                      f" AND NOT EXISTS(SELECT 1 FROM targets t WHERE t.id=v.{field})"),
                    "not_resolved_in_same_conversation": scalar(db, "SELECT COUNT(*) " + q +
                      f" AND NOT EXISTS(SELECT 1 FROM targets t WHERE t.id=v.{field} AND t.conversation=v.conversation)")}
        timestamp_range = db.execute("SELECT MIN(timestamp),MAX(timestamp) " + top).fetchone()
        years = dict(db.execute("SELECT strftime('%Y',timestamp,'unixepoch'),COUNT(*) " + top +
                                " GROUP BY 1"))
        result = {
            "schema_version": SCANNER_VERSION, "status": "structural_census_complete",
            "source": {"sha256": archive.sha256, "compressed_bytes": archive.compressed_bytes,
                "declared_expanded_bytes": archive.declared_total,
                "actual_expanded_bytes": archive.actual_total,
                "member_count": 5, "all_raw_sizes_and_crcs_verified": True,
                "index_version": version},
            "counts": {"top_records": scalar(db, "SELECT COUNT(*) " + top),
                "top_section_headers": scalar(db, "SELECT COUNT(*) " + top + " AND header=1"),
                "top_explicit_nonheaders": scalar(db, "SELECT COUNT(*) " + top + " AND header=0"),
                "top_nonempty_nonheaders": scalar(db, "SELECT COUNT(*) " + top + " AND header=0 AND nonempty=1"),
                "top_empty_text": scalar(db, "SELECT COUNT(*) " + top + " AND nonempty=0"),
                "top_missing_speaker_keys": scalar(db, "SELECT COUNT(*) " + top + " AND speaker IS NULL"),
                "top_unknown_header_status": scalar(db, "SELECT COUNT(*) " + top + " AND header IS NULL"),
                "conversation_metadata": scalar(db, "SELECT COUNT(*) FROM conversations"),
                "speaker_metadata": scalar(db, "SELECT COUNT(*) FROM speakers"),
                "observed_conversation_ids": scalar(db, "SELECT COUNT(*) FROM frame"),
                "all_serialized_views": scalar(db, "SELECT COUNT(*) FROM views"),
                "distinct_view_ids": scalar(db, "SELECT COUNT(DISTINCT id) FROM views"),
                "view_ids_in_multiple_conversations": scalar(db, "SELECT COUNT(*) FROM (SELECT id FROM targets GROUP BY id HAVING COUNT(*)>1)"),
                "view_ids_with_multiple_text_hashes": scalar(db, "SELECT COUNT(*) FROM (SELECT id FROM views GROUP BY id HAVING COUNT(DISTINCT text_sha256)>1)"),
                "views_missing_speaker_metadata": scalar(db, "SELECT COUNT(*) FROM views v WHERE speaker IS NOT NULL AND NOT EXISTS(SELECT 1 FROM speakers s WHERE s.id=v.speaker)"),
                "top_original_speaker_key_difference": scalar(db, "SELECT COUNT(*) FROM views t JOIN views o ON t.rownum=o.rownum WHERE t.role='top_level' AND o.role='original' AND t.speaker IS NOT NULL AND o.speaker IS NOT NULL AND t.speaker<>o.speaker"),
                "explicit_type_field": scalar(db, "SELECT SUM(type_present) FROM views"),
                "nonnull_type_field": scalar(db, "SELECT SUM(type_nonnull) FROM views")},
            "roles": dict(db.execute("SELECT role,COUNT(*) FROM views GROUP BY role")),
            "field_forms_top": dict(forms),
            "page_type_metadata": dict(db.execute("SELECT page_type,COUNT(*) FROM conversations GROUP BY page_type")),
            "top_timestamp_years": years,
            "top_timestamp_date_range_utc": [datetime.fromtimestamp(t, timezone.utc).date().isoformat() for t in timestamp_range],
            "references": {scope: {f: refs(f, scope == "top") for f in ["reply", "parent", "ancestor"]}
                           for scope in ["top", "all_views"]},
            "frame": {"unit": "conversation ID represented in this annual source view",
                "version": "annual-view-structural-frame/0.1.0",
                "eligible": scalar(db, "SELECT COUNT(*) FROM frame WHERE eligible=1"),
                "criteria": ["at_least_two_nonempty_explicit_nonheader_top_records",
                    "at_least_two_distinct_nonnull_speaker_keys_in_these_records",
                    "known_header_status_for_all_serialized_views",
                    "all_nonnull_reply_parent_ancestor_links_resolve_in_same_conversation_in_source",
                    "no_serialized_source_id_is_assigned_to_multiple_conversations",
                    "conversation_root_id_present_in_source", "conversation_metadata_present"],
                "complete_historical_context": False, "first_authorship_verified": False,
                "Chinese_language_validated": False},
            "H_G_admitted": 0, "linguistic_gold": False, "model_fit": False,
            "raw_text_or_identifiers_in_public_output": False,
        }
        db.commit()
        require(scalar(db, "PRAGMA page_count") * scalar(db, "PRAGMA page_size")
                <= DATABASE_LIMIT, "database_size_limit")
        db.execute("UPDATE control SET value='structural_census_complete' WHERE key='status'")
        db.execute("INSERT INTO control VALUES('archive_sha256',?)", (archive.sha256,))
        db.execute("INSERT INTO control VALUES('scanner_version',?)", (SCANNER_VERSION,))
        require(scalar(db, "PRAGMA page_count") * scalar(db, "PRAGMA page_size")
                <= DATABASE_LIMIT, "database_size_limit")
        db.commit()
        return result
    finally:
        db.close()
        archive.close()


def sample_frame(private_database, seed, count=24):
    """Uniform reservoir design, conditional on a declared PRNG seed and frame."""
    require(re.fullmatch(r"[0-9a-f]{64}", seed) is not None, "invalid_seed")
    require(type(count) is int and 1 <= count <= 24, "invalid_sample_count")
    db = sqlite3.connect(private_database)
    try:
        require(db.execute("SELECT value FROM control WHERE key='status'").fetchone()
                == ("structural_census_complete",), "census_incomplete")
        require(not scalar(db, "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='sample'"),
                "sample_already_exists")
        rng, chosen, total = random.Random(int(seed, 16)), [], 0
        for (key,) in db.execute("SELECT id FROM frame WHERE eligible=1 ORDER BY id"):
            total += 1
            if total <= count:
                chosen.append(key)
            else:
                position = rng.randrange(total)
                if position < count:
                    chosen[position] = key
        require(total > 0, "empty_sampling_frame")
        db.execute("CREATE TABLE sample(id TEXT PRIMARY KEY)")
        db.executemany("INSERT INTO sample VALUES(?)", [(key,) for key in chosen])
        db.execute("INSERT INTO control VALUES('sampling_seed',?)", (seed,))
        db.commit()
        return {"frame_version": "annual-view-structural-frame/0.1.0",
                "eligible_conversations": total, "sampled_conversations": len(chosen),
                "inclusion_probability": {"numerator": len(chosen), "denominator": total},
                "seed_hex": seed, "algorithm": "Algorithm R reservoir over lexicographically sorted source conversation IDs; Python random.Random.randrange",
                "probability_interpretation": "simple random sampling without replacement under the pseudorandom-number design; deterministic after seed is fixed",
                "population": "structurally eligible conversation groups within the single annual source view",
                "historical_completeness_or_human_origin_claim": False,
                "private_identifiers_in_output": False}
    finally:
        db.close()


def coverage(private_database):
    """Read-only source-key coverage, never verified author/register labels."""
    db = sqlite3.connect(Path(private_database).resolve().as_uri() + "?mode=ro", uri=True)
    try:
        require(db.execute("SELECT value FROM control WHERE key='status'").fetchone()
                == ("structural_census_complete",), "census_incomplete")
        require(scalar(db, "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='sample'") == 1,
                "sample_not_frozen")
        where = "v.role='top_level' AND v.header=0 AND v.nonempty=1 AND v.speaker IS NOT NULL"
        result = {
            "top_nonempty_nonheader_distinct_speaker_keys": scalar(db,
                "SELECT COUNT(DISTINCT speaker) FROM views v WHERE " + where),
            "speaker_keys_in_two_or_more_source_conversations": scalar(db,
                "SELECT COUNT(*) FROM (SELECT speaker FROM views v WHERE " + where +
                " GROUP BY speaker HAVING COUNT(DISTINCT conversation)>=2)"),
            "speaker_keys_in_two_or_more_known_page_type_buckets": scalar(db,
                "SELECT COUNT(*) FROM (SELECT v.speaker FROM views v JOIN conversations c ON v.conversation=c.id WHERE " + where +
                " AND c.page_type<>'other_or_unknown' GROUP BY v.speaker HAVING COUNT(DISTINCT c.page_type)>=2)"),
            "sample_top_records": scalar(db,
                "SELECT COUNT(*) FROM views v JOIN sample s ON s.id=v.conversation WHERE role='top_level'"),
            "sample_explicit_nonheaders": scalar(db,
                "SELECT COUNT(*) FROM views v JOIN sample s ON s.id=v.conversation WHERE role='top_level' AND header=0"),
            "sample_nonempty_nonheader_distinct_speaker_keys": scalar(db,
                "SELECT COUNT(DISTINCT speaker) FROM views v JOIN sample s ON s.id=v.conversation WHERE " + where),
            "sample_speaker_keys_in_two_or_more_conversations": scalar(db,
                "SELECT COUNT(*) FROM (SELECT speaker FROM views v JOIN sample s ON s.id=v.conversation WHERE " + where +
                " GROUP BY speaker HAVING COUNT(DISTINCT conversation)>=2)"),
            "sample_speaker_keys_in_two_or_more_known_page_type_buckets": scalar(db,
                "SELECT COUNT(*) FROM (SELECT v.speaker FROM views v JOIN sample s ON s.id=v.conversation JOIN conversations c ON c.id=v.conversation WHERE " + where +
                " AND c.page_type<>'other_or_unknown' GROUP BY v.speaker HAVING COUNT(DISTINCT c.page_type)>=2)"),
            "nonheader_top_original_speaker_key_difference": scalar(db,
                "SELECT COUNT(*) FROM views t JOIN views o ON t.rownum=o.rownum WHERE t.role='top_level' AND t.header=0 AND o.role='original' AND t.speaker IS NOT NULL AND o.speaker IS NOT NULL AND t.speaker<>o.speaker"),
            "interpretation": "Source keys and page-type buckets only; neither verified human producers nor semantic registers; no contrastive labels admitted",
        }
        return result
    finally:
        db.close()


def main(argv=None):
    parser = SafeParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    scan = sub.add_parser("census")
    scan.add_argument("archive")
    scan.add_argument("private_database")
    scan.add_argument("--expected-sha256", required=True)
    scan.add_argument("--expected-bytes", type=int)
    scan.add_argument("--expected-expanded", type=int)
    sample = sub.add_parser("sample")
    sample.add_argument("private_database")
    sample.add_argument("--seed", required=True)
    cover = sub.add_parser("coverage")
    cover.add_argument("private_database")
    try:
        args = parser.parse_args(argv)
        if args.action == "census":
            result = census(args.archive, args.private_database,
                expected_sha256=args.expected_sha256, expected_bytes=args.expected_bytes,
                expected_expanded=args.expected_expanded)
        elif args.action == "sample":
            result = sample_frame(args.private_database, args.seed)
        else:
            result = coverage(args.private_database)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except AuditError as exc:
        print(json.dumps({"status": "quarantined", "error_code": str(exc)}))
    except (OSError, ValueError, TypeError, KeyError, UnicodeError, zipfile.BadZipFile,
            zlib.error, sqlite3.Error, RecursionError, OverflowError, struct.error,
            EOFError, RuntimeError, NotImplementedError):
        print(json.dumps({"status": "quarantined", "error_code": "unsupported_or_invalid_input"}))
    return 1


if __name__ == "__main__":
    sys.exit(main())
