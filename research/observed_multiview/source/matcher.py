"""Bounded, offline exclusion comparison. This module never admits a source.

Read frozen SQLite signatures only; package-local integer gram IDs are translated
via full SHA256. Candidate distinct-gram counts retain ALL unseen digests.
No plaintext, model/POS/targets, network, or prior raw source access is needed.
"""
from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import resource
import sqlite3
import time
import unicodedata
import zlib

ALGORITHM = 'exposure-copy-signatures/1.0.0'
MATCHER_VERSION = 'cross-view-exclusion-matcher/1.0.0'
UNICODE_VERSION = '15.0.0'
OLD_DATABASE_SHA256 = '0ca3ca3eec71b88498ed70990804a7dc72d33dc736a0174edd3fdce5e258c3f5'
MIN_SHARED = 40
CONTAINMENT_NUMERATOR = 4
CONTAINMENT_DENOMINATOR = 5
MAX_RAW_BYTES = 2 * 1024**2
MAX_VIEWS = 1024
MAX_TOTAL_GRAMS = 2_000_000
MAX_HITS = 100_000
MAX_BINDINGS = 400_000
MAX_TEXTS = 150_000
MAX_PACKAGE_GRAMS = 8_000_000
MAX_RSS_BYTES = 3 * 1024**3
MAX_SECONDS = 1800

class CompatibilityError(ValueError):
    pass

class BoundExceeded(CompatibilityError):
    pass

def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()

def filehash(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024**2), b''):
            h.update(chunk)
    return h.hexdigest()

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def normalize(text):
    if unicodedata.unidata_version != UNICODE_VERSION:
        raise CompatibilityError('unicode_version_mismatch')
    return ''.join(c for c in unicodedata.normalize('NFKC', text) if not c.isspace())

def norm_hash(normalized):
    return hashlib.sha256(b'nfkc-no-ws/v1\0' + normalized.encode('utf-8')).digest()

def gram_hash(gram):
    return hashlib.sha256(b'char5-nfkc-no-ws/v1\0' + gram.encode('utf-8')).digest()

def distinct_grams(normalized):
    return frozenset(gram_hash(normalized[i:i+5]) for i in range(max(0, len(normalized)-4)))

def pack_ids(ids):
    data = bytearray()
    old = 0
    for number in sorted(set(ids)):
        if type(number) is not int or number <= 0:
            raise CompatibilityError('invalid_gram_id')
        delta = number-old
        old = number
        while delta >= 128:
            data.append((delta & 127) | 128)
            delta >>= 7
        data.append(delta)
    return zlib.compress(bytes(data), 6)

def unpack_ids(blob, expected_count, maximum_id=MAX_PACKAGE_GRAMS):
    """Bounded strict decoder: canonical positive varints, no compressed tails."""
    if type(expected_count) is not int or not 0 <= expected_count <= MAX_PACKAGE_GRAMS:
        raise CompatibilityError('invalid_gram_count')
    limit = expected_count * 5
    dec = zlib.decompressobj()
    raw = dec.decompress(blob, limit+1)
    if len(raw) > limit or not dec.eof or dec.unconsumed_tail or dec.unused_data:
        raise CompatibilityError('invalid_or_oversize_compressed_ids')
    result = []
    value = shift = previous = 0
    start = 0
    for offset, byte in enumerate(raw):
        value |= (byte & 127) << shift
        if byte & 128:
            shift += 7
            if shift >= 35:
                raise CompatibilityError('oversize_varint')
        else:
            if value <= 0 or (offset > start and byte == 0):
                raise CompatibilityError('noncanonical_or_nonpositive_delta')
            previous += value
            if previous > maximum_id:
                raise CompatibilityError('gram_id_outside_dictionary')
            result.append(previous)
            value = shift = 0
            start = offset+1
    if shift or len(result) != expected_count:
        raise CompatibilityError('gram_count_or_varint_mismatch')
    return result

def near_copy(shared, candidate_total, reference_total):
    """Exact integer threshold, complete denominators, never mapped-hit counts."""
    denominator = min(candidate_total, reference_total)
    return (shared >= MIN_SHARED and denominator > 0 and
            shared * CONTAINMENT_DENOMINATOR >= denominator * CONTAINMENT_NUMERATOR)

def long_blocks(text):
    """Same v1 blank-line and punctuation-lines normalized long-block contract."""
    blocks = [('physical_blankline_block', i, value)
              for i, value in enumerate(re.split(r'(?:\r?\n[\t ]*){2,}', text))]
    terminals = frozenset('。！？!?．')
    closers = frozenset('”’」』）》】〕〗〙〛"\'')
    units = []
    for match in re.finditer(r'[^\r\n]+', text):
        start, end = match.start(), match.end()
        while start < end and text[start].isspace(): start += 1
        while end > start and text[end-1].isspace(): end -= 1
        if not any(unicodedata.category(c)[0] in {'L', 'N'} for c in text[start:end]): continue
        cursor = pos = start
        while pos < end:
            char = text[pos]
            terminal = char in terminals
            if char == '.':
                decimal = pos and pos+1 < end and text[pos-1].isdigit() and text[pos+1].isdigit()
                prefix = re.search(r'([A-Za-z]+)$', text[:pos])
                initial = prefix is not None and len(prefix.group(1)) == 1
                terminal = not decimal and not initial and (pos+1 == end or text[pos+1].isspace() or text[pos+1] in closers)
            if terminal:
                boundary = pos+1
                while boundary < end and (text[boundary] in terminals or text[boundary] in closers or text[boundary] == '.'):
                    boundary += 1
                value = text[cursor:boundary].strip()
                if any(unicodedata.category(c)[0] in {'L', 'N'} for c in value): units.append(value)
                cursor = pos = boundary
            else:
                pos += 1
        value = text[cursor:end].strip()
        if any(unicodedata.category(c)[0] in {'L', 'N'} for c in value): units.append(value)
    blocks.extend(('punctuation_line_unit', i, value) for i, value in enumerate(units))
    return [(kind, i, norm_hash(n), len(n)) for kind, i, value in blocks if len(n := normalize(value)) >= 64]

@dataclass(frozen=True)
class Signature:
    key: str
    role: str
    raw_sha256: str
    normalized_sha256: bytes
    normalized_codepoints: int
    grams: frozenset
    blocks: tuple

def signature(text, key, role):
    if not isinstance(text, str) or len(text.encode('utf-8')) > MAX_RAW_BYTES:
        raise BoundExceeded('source_view_bytes_cap')
    n = normalize(text)
    return Signature(key, role, sha(text.encode()), norm_hash(n), len(n), distinct_grams(n), tuple(long_blocks(text)))

class SignaturePackage:
    """Read-only SQLite, exact artifact identity verified before use."""
    def __init__(self, path, expected_sha256, name, *, expected_algorithm=ALGORITHM):
        self.path = Path(path)
        self.name = name
        if not re.fullmatch(r'[0-9a-f]{64}', expected_sha256 or '') or filehash(self.path) != expected_sha256:
            raise CompatibilityError('package_hash_mismatch')
        self.sha256 = expected_sha256
        self.db = sqlite3.connect(self.path.resolve().as_uri() + '?mode=ro&immutable=1', uri=True)
        self.db.execute('PRAGMA query_only=ON')
        self.db.execute('PRAGMA cache_size=-16384')
        self.control = dict(self.db.execute('SELECT key,value FROM control'))
        if self.control.get('status') != 'complete' or self.control.get('algorithm') != expected_algorithm:
            self.close()
            raise CompatibilityError('package_contract_incomplete')
        if self.control.get('unicode_version', UNICODE_VERSION) != UNICODE_VERSION:
            self.close()
            raise CompatibilityError('package_unicode_mismatch')
        self.text_count = self.db.execute('SELECT count(*) FROM texts').fetchone()[0]
        self.gram_count, self.max_gram_id = self.db.execute('SELECT count(*),COALESCE(max(id),0) FROM grams').fetchone()
        if self.text_count > MAX_TEXTS or self.gram_count > MAX_PACKAGE_GRAMS or self.gram_count != self.max_gram_id:
            self.close()
            raise CompatibilityError('package_count_bound_or_id_gap')

    def close(self):
        if getattr(self, 'db', None) is not None:
            self.db.close()
            self.db = None

    def map_digests(self, digests):
        """Return digest -> THIS package's ID, retaining external full counts."""
        result = {}
        digests = list(digests)
        for start in range(0, len(digests), 400):
            chunk = digests[start:start+400]
            rows = self.db.execute('SELECT sha256,id FROM grams WHERE sha256 IN (' + ','.join('?' for _ in chunk) + ')', chunk)
            result.update(rows)
        return result

    def compare(self, signatures, *, resource_callback=None, comparison_budget=None):
        started = time.monotonic()
        signatures = list(signatures)
        if len(signatures) > MAX_VIEWS or sum(len(s.grams) for s in signatures) > MAX_TOTAL_GRAMS:
            raise BoundExceeded('candidate_views_or_grams_cap')
        all_digests = set().union(*(s.grams for s in signatures)) if signatures else set()
        local = self.map_digests(all_digests)
        inverse = defaultdict(list)
        raw_exact = defaultdict(set)
        norm_exact = defaultdict(set)
        block_exact = defaultdict(set)
        for i, sig in enumerate(signatures):
            if sig.normalized_codepoints:
                raw_exact[sig.raw_sha256].add(i)
                norm_exact[sig.normalized_sha256].add(i)
            if sig.normalized_codepoints >= 64: block_exact[sig.normalized_sha256].add(i)
            for _, _, digest, _ in sig.blocks: block_exact[digest].add(i)
            if len(sig.grams) >= MIN_SHARED:
                for digest in sig.grams:
                    if digest in local: inverse[local[digest]].append(i)
        stats = {'shared_gram_pair_increments': 0, 'exact_comparison_increments': 0, 'reference_gram_memberships_decoded': 0,
                 'reference_texts_scanned': 0}
        def checkpoint():
            if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024 > MAX_RSS_BYTES or time.monotonic()-started > MAX_SECONDS:
                raise BoundExceeded('matching_resource_cap')
            if resource_callback is not None: resource_callback(dict(stats))
        def increment(number, shared=False):
            stats['shared_gram_pair_increments' if shared else 'exact_comparison_increments'] += number
            if comparison_budget is not None:
                comparison_budget['used'] = comparison_budget.get('used', 0) + number
                if comparison_budget['used'] > comparison_budget.get('cap', 300_000_000):
                    raise BoundExceeded('aggregate_comparison_increment_cap')
        hits = {}
        def record(i, tid, reason, shared=None, reference_count=None):
            if shared is None: increment(1)
            key = (i, tid)
            if key not in hits:
                if len(hits) >= MAX_HITS: raise BoundExceeded('hit_count_cap')
                hits[key] = {'candidate_view': signatures[i].key, 'candidate_role': signatures[i].role,
                             'package': self.name, 'package_sha256': self.sha256, 'reference_text_id': tid,
                             'reasons': [], 'candidate_full_gram_count': len(signatures[i].grams)}
            hit = hits[key]
            if reason not in hit['reasons']: hit['reasons'].append(reason)
            if shared is not None:
                hit.update(shared_distinct_grams=shared, reference_full_gram_count=reference_count,
                           containment=shared/min(len(signatures[i].grams), reference_count))
        scanned = 0
        for tid, raw, norm, npoints, count, packed in self.db.execute('SELECT id,raw_sha256,normalized_sha256,normalized_codepoints,gram_count,gram_ids_delta_zlib FROM texts'):
            scanned += 1
            stats['reference_texts_scanned'] = scanned
            for i in raw_exact.get(raw, ()): record(i, tid, 'raw_exact')
            for i in norm_exact.get(norm, ()):
                if npoints: record(i, tid, 'normalized_full_exact')
            if npoints >= 64:
                for i in block_exact.get(norm, ()): record(i, tid, 'candidate_long_block_to_reference_full_exact')
            if count >= MIN_SHARED and inverse:
                counts = defaultdict(int)
                stats['reference_gram_memberships_decoded'] += count
                for offset, gid in enumerate(unpack_ids(packed, count, self.max_gram_id)):
                    postings = inverse.get(gid, ())
                    increment(len(postings), shared=True)
                    for i in postings: counts[i] += 1
                    if offset and offset % 4096 == 0: checkpoint()
                for i, shared in counts.items():
                    if near_copy(shared, len(signatures[i].grams), count): record(i, tid, 'near_copy_full_distinct_grams', shared, count)
            if scanned % 500 == 0: checkpoint()
        for block_number, (tid, digest) in enumerate(self.db.execute('SELECT text_id,normalized_sha256 FROM blocks')):
            for i in block_exact.get(digest, ()): record(i, tid, 'long_block_exact')
            if block_number % 500 == 0: checkpoint()
        reference_ids = sorted({tid for _, tid in hits})
        bindings = []
        for start in range(0, len(reference_ids), 400):
            part = reference_ids[start:start+400]
            if not part: continue
            for row in self.db.execute('SELECT text_id,source_id,member_key,exposure_role,source_view_role,source_object_sha256,locator_json FROM bindings WHERE text_id IN (' + ','.join('?' for _ in part) + ')', part):
                if len(bindings) >= MAX_BINDINGS: raise BoundExceeded('binding_count_cap')
                bindings.append(dict(zip(('reference_text_id','source_id','member_key','exposure_role','source_view_role','source_object_sha256','locator_json'), row)))
                if len(bindings) % 500 == 0: checkpoint()
        checkpoint()
        return {'package': self.name, 'package_sha256': self.sha256, 'reference_texts_scanned': scanned,
                'reference_texts_expected': self.text_count, 'complete_signature_scan': scanned == self.text_count,
                'candidate_views': len(signatures), 'candidate_full_gram_counts': [len(s.grams) for s in signatures],
                'candidate_mapped_gram_counts': [sum(g in local for g in s.grams) for s in signatures],
                'comparison_stats': stats, 'hits': list(hits.values()), 'bindings': bindings}

def record_signatures(raw_text, projection, expected_raw_sha256):
    """Check offsets/hash/char maps; caller separately certifies projector semantics.

    source_map[i] binds output character i to [raw_start, raw_end, operation,
    expansion_index]. Raw spans include omitted syntax. No across-barrier joining.
    """
    if not isinstance(raw_text, str) or len(raw_text.encode()) > MAX_RAW_BYTES:
        raise CompatibilityError('missing_or_oversize_raw_source_view')
    raw_hash = sha(raw_text.encode())
    if raw_hash != expected_raw_sha256:
        raise CompatibilityError('raw_source_hash_mismatch')
    result = [signature(raw_text, 'raw_source', 'full_raw_source_view')]
    total_grams = len(result[0].grams)
    def add_signature(text, key, role):
        nonlocal total_grams
        if len(result) >= MAX_VIEWS: raise BoundExceeded('candidate_views_or_grams_cap')
        value = signature(text, key, role)
        total_grams += len(value.grams)
        if total_grams > MAX_TOTAL_GRAMS: raise BoundExceeded('candidate_views_or_grams_cap')
        result.append(value)
    if not isinstance(projection, dict) or projection.get('source_sha256') != raw_hash:
        raise CompatibilityError('projection_source_hash_mismatch')
    if not isinstance(projection.get('profile'), str) or not projection['profile']:
        raise CompatibilityError('projection_profile_missing')
    segments = projection.get('segments')
    if not isinstance(segments, list) or not segments:
        raise CompatibilityError('missing_projected_segments')
    for index, segment in enumerate(segments):
        text = segment.get('text')
        spans = segment.get('source_spans')
        mapping = segment.get('source_map')
        if not isinstance(text, str) or not text or not isinstance(spans, list) or not spans or not isinstance(mapping, list) or len(mapping) != len(text):
            raise CompatibilityError('incomplete_segment_mapping')
        previous_end = -1
        for pair in spans:
            if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                raise CompatibilityError('invalid_source_span')
            start, end = pair
            if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(raw_text) or start < previous_end:
                raise CompatibilityError('invalid_or_unordered_source_span')
            previous_end = end
        for item in mapping:
            if not isinstance(item, (list, tuple)) or len(item) != 4:
                raise CompatibilityError('invalid_character_map')
            start, end, operation, output_index = item
            if (type(start) is not int or type(end) is not int or not 0 <= start < end <= len(raw_text) or
                not isinstance(operation, str) or not operation or type(output_index) is not int or output_index < 0 or
                not any(lo <= start < end <= hi for lo, hi in spans)):
                raise CompatibilityError('character_map_outside_source_spans')
        add_signature(text, f'projected_segment:{index}', 'projected_segment')
        for number, (start, end) in enumerate(spans):
            add_signature(raw_text[start:end], f'raw_span:{index}:{number}', 'mapped_contiguous_raw_source_span')
    if len(result) > MAX_VIEWS or sum(len(s.grams) for s in result) > MAX_TOTAL_GRAMS:
        raise BoundExceeded('candidate_views_or_grams_cap')
    return result

def match_record(raw_text, projection, *, packages, expected_raw_sha256, require_package_names=None, resource_callback=None, comparison_budget=None):
    """Fail-closed exclusion-only receipt. No match is NOT independent admission.

    Returns private per-source memberships; caller must keep the entire result
    private and propagate all hit bindings to its dependency graph.
    """
    receipt = {'schema_version': MATCHER_VERSION, 'purpose': 'exclusion_only',
               'status': 'quarantine', 'signature_scan_complete': False, 'complete_declared_view_comparisons': False,
               'cross_projection_coverage_certified': False, 'admission_authorized': False,
               'cross_view_claim': 'bounded_source_view_comparison_only_not_universal_clean_prose_coverage',
               'coverage_gaps': ['unknown_external_lineage_and_semantic_rewriting_not_detected',
                                 'old_raw_sources_not_reprojected',
                                 'projection_semantic_correctness_requires_independent_projector_review'],
               'packages': []}
    try:
        packages = list(packages)
        if not packages: raise CompatibilityError('no_exclusion_packages')
        names = [p.name for p in packages]
        if len(names) != len(set(names)): raise CompatibilityError('duplicate_package_names')
        if require_package_names is not None and set(names) != set(require_package_names):
            raise CompatibilityError('required_exclusion_package_missing')
        signatures = record_signatures(raw_text, projection, expected_raw_sha256)
        for package in packages:
            receipt['packages'].append(package.compare(signatures, resource_callback=resource_callback, comparison_budget=comparison_budget))
        receipt['signature_scan_complete'] = all(p['complete_signature_scan'] for p in receipt['packages'])
        receipt['complete_declared_view_comparisons'] = receipt['signature_scan_complete']
        receipt['status'] = ('excluded_known_exposure_match' if any(p['hits'] for p in receipt['packages'])
                             else 'quarantine_unmatched_cross_projection_coverage')
        receipt['view_counts'] = {role: sum(s.role == role for s in signatures) for role in sorted({s.role for s in signatures})}
        receipt['source_sha256'] = expected_raw_sha256
        receipt['projection_profile'] = projection['profile']
    except (CompatibilityError, sqlite3.Error, OSError, ValueError, KeyError, TypeError, RuntimeError) as error:
        receipt['blocker'] = str(error)
    return receipt

def match_records(records, *, packages, require_package_names=None, resource_callback=None, comparison_budget=None):
    """Batch interface: one old-text scan per bounded batch, not per record.

    records is a list of {record_key, raw_text, projection, raw_sha256} mappings.
    Invalid records quarantine individually. Exceeding the aggregate batch bound
    quarantines this batch: the caller may explicitly use smaller batches; no
    source is silently dropped. Per-record returns remain private.
    """
    from dataclasses import replace
    records = list(records)
    packages = list(packages)
    output = []
    combined = []
    indexes = {}
    names = [p.name for p in packages]
    package_error = None
    if not packages or len(names) != len(set(names)):
        package_error = 'missing_or_duplicate_exclusion_packages'
    if require_package_names is not None and set(names) != set(require_package_names):
        package_error = 'required_exclusion_package_missing'
    for number, record in enumerate(records):
        result = {'record_key': record.get('record_key'), 'schema_version': MATCHER_VERSION,
                  'purpose': 'exclusion_only', 'status': 'quarantine',
                  'signature_scan_complete': False, 'complete_declared_view_comparisons': False,
               'cross_projection_coverage_certified': False, 'admission_authorized': False,
                  'cross_view_claim': 'bounded_source_view_comparison_only_not_universal_clean_prose_coverage',
                  'coverage_gaps': ['unknown_external_lineage_and_semantic_rewriting_not_detected',
                                    'old_raw_sources_not_reprojected',
                                    'projection_semantic_correctness_requires_independent_projector_review'],
                  'packages': []}
        output.append(result)
        try:
            if package_error: raise CompatibilityError(package_error)
            sigs = record_signatures(record['raw_text'], record['projection'], record['raw_sha256'])
            keys = set()
            for sig in sigs:
                key = f'record:{number}/{sig.key}'
                combined.append(replace(sig, key=key)); keys.add(key)
            indexes[number] = keys
            result['source_sha256'] = record['raw_sha256']
            result['projection_profile'] = record['projection']['profile']
            result['view_counts'] = {role: sum(s.role == role for s in sigs) for role in sorted({s.role for s in sigs})}
        except (CompatibilityError, ValueError, KeyError, TypeError) as error:
            result['blocker'] = str(error)
    if not combined: return output
    try:
        if len(combined) > MAX_VIEWS or sum(len(s.grams) for s in combined) > MAX_TOTAL_GRAMS:
            raise BoundExceeded('batch_views_or_grams_cap_reduce_batch_size')
        for package in packages:
            matched = package.compare(combined, resource_callback=resource_callback, comparison_budget=comparison_budget)
            for number, keys in indexes.items():
                result = output[number]
                hits = [h for h in matched['hits'] if h['candidate_view'] in keys]
                tids = {h['reference_text_id'] for h in hits}
                result['packages'].append({'package': matched['package'], 'package_sha256': matched['package_sha256'],
                    'complete_signature_scan': matched['complete_signature_scan'],
                    'reference_texts_scanned': matched['reference_texts_scanned'],
                    'reference_texts_expected': matched['reference_texts_expected'],
                    'hits': hits, 'bindings': [b for b in matched['bindings'] if b['reference_text_id'] in tids]})
        for number in indexes:
            result = output[number]
            result['signature_scan_complete'] = all(p['complete_signature_scan'] for p in result['packages'])
            result['complete_declared_view_comparisons'] = result['signature_scan_complete']
            result['status'] = ('excluded_known_exposure_match' if any(p['hits'] for p in result['packages'])
                                else 'quarantine_unmatched_cross_projection_coverage')
    except (CompatibilityError, sqlite3.Error, OSError, ValueError, KeyError, TypeError, RuntimeError) as error:
        for number in indexes:
            output[number]['blocker'] = str(error)
    return output

SCHEMA = '''
PRAGMA journal_mode=DELETE; PRAGMA synchronous=FULL; PRAGMA cache_size=-16384;
CREATE TABLE control(key TEXT PRIMARY KEY,value TEXT);
CREATE TABLE grams(id INTEGER PRIMARY KEY,sha256 BLOB UNIQUE NOT NULL);
CREATE TABLE texts(id INTEGER PRIMARY KEY,raw_sha256 TEXT UNIQUE NOT NULL,utf8_bytes INTEGER,codepoints INTEGER,normalized_sha256 BLOB,normalized_codepoints INTEGER,gram_count INTEGER,gram_ids_delta_zlib BLOB);
CREATE TABLE blocks(text_id INTEGER,kind TEXT,ordinal INTEGER,normalized_sha256 BLOB,normalized_codepoints INTEGER,PRIMARY KEY(text_id,kind,ordinal));
CREATE TABLE bindings(id INTEGER PRIMARY KEY,source_id TEXT,member_key TEXT,exposure_role TEXT,source_view_role TEXT,source_object_sha256 TEXT,text_id INTEGER,locator_json TEXT);
'''

class SignatureWriter:
    """New package only. No mutation of a frozen package; no plaintext persisted.

    A disk-based indexed digest lookup avoids a duplicate large Python dictionary.
    Caller freezes input identities/roles and enforces TOTAL derivatives with guard.
    This callable does not acquire/read any source or authorize a new source run.
    """
    def __init__(self, path, *, guard=None):
        import os
        self.path = Path(path)
        descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(descriptor)
        self.db = sqlite3.connect(self.path)
        self.db.executescript(SCHEMA)
        self.guard = guard
        self.gram_count = self.text_count = self.binding_count = 0

    def add(self, text, *, source_id, member_key, exposure_role, source_view_role, source_object_sha256, locator):
        sig = signature(text, 'new', source_view_role)
        found = self.db.execute('SELECT id FROM texts WHERE raw_sha256=?', (sig.raw_sha256,)).fetchone()
        if found:
            tid = found[0]
        else:
            self.text_count += 1; tid = self.text_count
            if self.text_count > MAX_TEXTS: raise BoundExceeded('new_package_text_cap')
            ids = []
            digests = sorted(sig.grams)
            for start in range(0, len(digests), 400):
                part = digests[start:start+400]
                found = dict(self.db.execute('SELECT sha256,id FROM grams WHERE sha256 IN ('+','.join('?' for _ in part)+')', part))
                for digest in part:
                    gid = found.get(digest)
                    if gid is None:
                        self.gram_count += 1; gid = self.gram_count
                        if gid > MAX_PACKAGE_GRAMS: raise BoundExceeded('new_package_gram_cap')
                        self.db.execute('INSERT INTO grams VALUES(?,?)',(gid,digest))
                    ids.append(gid)
            self.db.execute('INSERT INTO texts VALUES(?,?,?,?,?,?,?,?)',(tid,sig.raw_sha256,len(text.encode()),len(text),sig.normalized_sha256,sig.normalized_codepoints,len(sig.grams),pack_ids(ids)))
            self.db.executemany('INSERT INTO blocks VALUES(?,?,?,?,?)',[(tid,*block) for block in sig.blocks])
        self.binding_count += 1
        if self.binding_count > MAX_BINDINGS: raise BoundExceeded('new_package_binding_cap')
        self.db.execute('INSERT INTO bindings VALUES(?,?,?,?,?,?,?,?)',(self.binding_count,source_id,member_key,exposure_role,source_view_role,source_object_sha256,tid,canonical(locator).decode()))
        self.db.commit()
        if self.guard: self.guard({'new_package_bytes':self.path.stat().st_size,'new_package_texts':self.text_count,'new_package_grams':self.gram_count,'new_package_bindings':self.binding_count})
        return tid

    def finish(self):
        self.db.executemany('INSERT INTO control VALUES(?,?)',[('status','complete'),('algorithm',ALGORITHM),('unicode_version',UNICODE_VERSION),('matcher_version',MATCHER_VERSION)])
        self.db.execute('CREATE INDEX bindings_by_text ON bindings(text_id)')
        self.db.commit()
        if self.guard: self.guard({'new_package_bytes':self.path.stat().st_size})
        self.db.close(); self.db = None
        return {'path':str(self.path),'bytes':self.path.stat().st_size,'sha256':filehash(self.path),
                'text_count':self.text_count,'gram_count':self.gram_count,'binding_count':self.binding_count}

    def close_failed(self):
        if self.db is not None: self.db.close(); self.db = None

def exclusion_edges(receipt, candidate_member_key, *, drop_self=True):
    """All matching old members become graph edges. Do not compare component names.

    For a candidate reference package the same routine returns candidate-pair edges;
    canonical (sorted member-pair, package) deduplication is the graph caller's job.
    """
    edges = []
    for package in receipt.get('packages', []):
        by_text = defaultdict(list)
        for binding in package['bindings']: by_text[binding['reference_text_id']].append(binding)
        for hit in package['hits']:
            for binding in by_text[hit['reference_text_id']]:
                if drop_self and candidate_member_key == binding['member_key']: continue
                edges.append({'left_member_key':candidate_member_key,'right_member_key':binding['member_key'],
                              'edge_type':'copy_signature_match','package':package['package'],
                              'package_sha256':package['package_sha256'],'candidate_view':hit['candidate_view'],
                              'reference_text_id':hit['reference_text_id'],'reference_exposure_role':binding['exposure_role'],
                              'reference_source_view_role':binding['source_view_role'], 'reasons':hit['reasons'],
                              'candidate_source_sha256':receipt.get('source_sha256'),
                              'reference_source_object_sha256':binding['source_object_sha256']})
    return edges
