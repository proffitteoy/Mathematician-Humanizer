"""Acquire only approved pinned UTF-8 text blobs; never execute source content.

The corpus, per-file locators, author metadata and exposure labels are private.
The output is acquisition-only and is not a model admission or a split.
"""
import argparse, concurrent.futures, datetime, hashlib, json, pathlib, re
import shutil, threading, time, urllib.error, urllib.parse, urllib.request

SPECS = [
    ('harttle-land', 'harttle/harttle.github.io', ['README.md']),
    ('wu-kan', 'wu-kan/wu-kan.github.io', ['_config.yml']),
    ('ddadaal', 'ddadaal/ddadaal.me', ['src/components/Footer/Brief.tsx', 'src/i18n/cn.ts']),
]
MAX_NETWORK = 30 * 1024 * 1024
MAX_EXPANDED = 100 * 1024 * 1024
# Allowance covers the preliminary README probe and three connector metadata responses.
# HTTP/TLS overhead is not directly observable; this allowance is conservative for
# metadata entity bodies, not a claim of exact wire-byte measurement.
PRIOR_NETWORK_ALLOWANCE = 64 * 1024

def digest(data):
    return hashlib.sha256(data).hexdigest()

def git_blob(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()

def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, ensure_ascii=False, indent=2) + '\n'
    path.with_suffix(path.suffix + '.tmp').write_text(data)
    path.with_suffix(path.suffix + '.tmp').replace(path)

def tree_root_sha1(manifest):
    from collections import defaultdict
    if manifest.get('truncated'):
        raise ValueError('truncated_manifest')
    children, expected = defaultdict(list), {}
    for row in manifest['tree']:
        parts = row['path'].rsplit('/', 1)
        directory, name = parts if len(parts) == 2 else ('', parts[0])
        children[directory].append((name, row))
        if row['type'] == 'tree':
            expected[row['path']] = row['sha']
    calculated = {}
    for directory, rows in children.items():
        key = lambda x: (x[0] + ('/' if x[1]['type'] == 'tree' else '')).encode('utf-8')
        payload = b''.join(str(int(r['mode'])).encode() + b' ' + name.encode('utf-8') + b'\0' + bytes.fromhex(r['sha']) for name, r in sorted(rows, key=key))
        calculated[directory] = hashlib.sha1(b'tree ' + str(len(payload)).encode() + b'\0' + payload).hexdigest()
    if any(calculated.get(k) != v for k, v in expected.items()):
        raise ValueError('subtree_identity_mismatch')
    return calculated['']

def candidates(sid, rows):
    if sid == 'ddadaal':
        return [r for r in rows if r['type'] == 'blob' and re.fullmatch(r'contents/\d{8}[^/]+/cn\.md', r['path'])]
    return [r for r in rows if r['type'] == 'blob' and r['path'].startswith('_posts/')]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--source-root', type=pathlib.Path, required=True)
    ap.add_argument('--output-root', type=pathlib.Path, required=True)
    ap.add_argument('--workers', type=int, default=8)
    args = ap.parse_args()
    if not 1 <= args.workers <= 8:
        raise ValueError('workers_must_be_1_to_8')
    src, out = args.source_root, args.output_root
    private = out / 'private'
    private.mkdir(parents=True, exist_ok=True)
    ledger_path = private / 'transfer-ledger.json'
    if ledger_path.exists():
        ledger = json.loads(ledger_path.read_text())
    else:
        ledger = dict(network_entity_bytes=0, prior_metadata_entity_allowance=PRIOR_NETWORK_ALLOWANCE,
                      max_network_entity_bytes=MAX_NETWORK, max_expanded_bytes=MAX_EXPANDED,
                      attempts=0, failures=[], completed=0, reused=0)
    lock = threading.Lock()
    catalogue = json.loads((src / 'public/catalogue.json').read_text())
    representatives = json.loads((src / 'private/representative-receipt.json').read_text())
    reps = {(x['repository'], x['path']): x for x in representatives}
    jobs, sources = [], []
    for sid, repo, notice_paths in SPECS:
        cat = next(s for s in catalogue['sources'] if s['source_id'] == sid)
        prefix = repo.replace('/', '__')
        tree_path = src / 'private/metadata' / (prefix + '.tree.json')
        tree_bytes = tree_path.read_bytes()
        if digest(tree_bytes) != cat['version']['manifest_sha256']:
            raise ValueError('catalogue_manifest_hash_mismatch')
        tree = json.loads(tree_bytes)
        root = tree_root_sha1(tree)
        commit_path = private / 'metadata' / (prefix + '.commit.json')
        commit = json.loads(commit_path.read_text())
        if commit['sha'] != cat['version']['git_commit'] or commit['tree']['sha'] != root or root != cat['version']['git_tree_sha1']:
            raise ValueError('commit_tree_association_mismatch')
        if commit['committer']['date'] >= catalogue['cutoff_exclusive']:
            raise ValueError('nonhistorical_commit')
        (private / 'metadata').mkdir(exist_ok=True)
        shutil.copyfile(tree_path, private / 'metadata' / tree_path.name)
        selected = candidates(sid, tree['tree'])
        if len(selected) != cat['counts']['candidate_files'] or sum(r['size'] for r in selected) != cat['size']['candidate_source_bytes']:
            raise ValueError('candidate_frame_mismatch')
        notices = [next(r for r in tree['tree'] if r['path'] == p) for p in notice_paths]
        for purpose, entries in [('candidate_text', selected), ('historical_license_evidence', notices)]:
            for row in entries:
                path = pathlib.PurePosixPath(row['path'])
                if path.is_absolute() or '..' in path.parts or row['type'] != 'blob' or row['mode'] != '100644':
                    raise ValueError('unsafe_or_nonregular_blob')
                if purpose == 'candidate_text' and path.suffix.lower() not in ('.md', '.markdown', '.rmd'):
                    raise ValueError('non_text_candidate')
                dest = private / ('raw' if purpose == 'candidate_text' else 'license-raw') / sid / row['path']
                url = 'https://raw.githubusercontent.com/' + repo + '/' + commit['sha'] + '/' + urllib.parse.quote(row['path'], safe='/')
                jobs.append(dict(source_id=sid, repository=repo, commit=commit['sha'], git_tree_sha1=root,
                                 path=row['path'], expected_bytes=row['size'], git_blob_sha1=row['sha'],
                                 text_license=cat['rights']['text_license'], purpose=purpose, source_url=url,
                                 dest=str(dest), representative=reps.get((repo, row['path']))))
        sources.append(dict(source_id=sid, repository=repo, commit=commit['sha'], git_tree_sha1=root,
                            manifest_sha256=digest(tree_bytes), commit_response_sha256=digest(commit_path.read_bytes()),
                            candidate_files=len(selected), candidate_bytes=sum(r['size'] for r in selected),
                            text_license=cat['rights']['text_license']))
    if sum(j['expected_bytes'] for j in jobs) > MAX_EXPANDED:
        raise ValueError('expanded_budget_preflight_failure')
    dump(private / 'acquisition-plan.json', dict(sources=sources, jobs=jobs,
        model_admitted=False, content_execution=False, raw_corpus_publication=False))

    def fetch(job):
        dest = pathlib.Path(job['dest'])
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            data = dest.read_bytes()
            status = 'verified_existing'
        elif job['representative']:
            data = (src / 'private/representatives' / job['representative']['file']).read_bytes()
            status = 'reused_exposed_diagnostic'
        else:
            data, status = None, 'downloaded'
            for attempt in range(3):
                with lock:
                    ledger['attempts'] += 1
                    if ledger['network_entity_bytes'] + PRIOR_NETWORK_ALLOWANCE + job['expected_bytes'] > MAX_NETWORK:
                        raise ValueError('network_budget_preflight_failure')
                try:
                    req = urllib.request.Request(job['source_url'], headers={
                        'User-Agent': 'StyleCorpusResearch/0.2 (bounded historical text verification)',
                        'Accept-Encoding': 'identity'})
                    parts, received = [], 0
                    with urllib.request.urlopen(req, timeout=60) as response:
                        if urllib.parse.urlparse(response.url).hostname != 'raw.githubusercontent.com':
                            raise ValueError('unexpected_redirect_host')
                        if response.headers.get('Content-Encoding', 'identity') != 'identity':
                            raise ValueError('unexpected_content_encoding')
                        length = response.headers.get('Content-Length')
                        if length is not None and int(length) != job['expected_bytes']:
                            raise ValueError('unexpected_content_length')
                        while True:
                            chunk = response.read(min(65536, job['expected_bytes'] + 1 - received))
                            if not chunk:
                                break
                            received += len(chunk)
                            with lock:
                                ledger['network_entity_bytes'] += len(chunk)
                                if ledger['network_entity_bytes'] + PRIOR_NETWORK_ALLOWANCE > MAX_NETWORK:
                                    raise ValueError('network_hard_cap_exceeded')
                            if received > job['expected_bytes']:
                                raise ValueError('oversized_blob')
                            parts.append(chunk)
                    data = b''.join(parts)
                    break
                except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
                    with lock:
                        ledger['failures'].append(dict(source_id=job['source_id'], path=job['path'], attempt=attempt+1, error=str(error)))
                        dump(ledger_path, ledger)
                    if attempt == 2:
                        raise
                    time.sleep(2 * (attempt+1))
        if len(data) != job['expected_bytes'] or git_blob(data) != job['git_blob_sha1']:
            raise ValueError('blob_identity_mismatch:' + job['source_id'])
        data.decode('utf-8', errors='strict')
        if not dest.exists():
            with dest.open('xb') as f:
                f.write(data)
        result = {k:v for k,v in job.items() if k not in ('representative', 'expected_bytes')}
        result.update(bytes=len(data), sha256=digest(data), git_blob_verified=True, transfer_status=status,
            diagnostic_exposure=bool(job['representative']), model_admitted=False,
            retrieved_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
        with lock:
            ledger['completed'] += 1
            ledger['reused'] += int(status != 'downloaded')
            dump(ledger_path, ledger)
        return result

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(fetch, j): j for j in jobs}
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())
            if len(results) % 50 == 0 or len(results) == len(jobs):
                print(json.dumps(dict(verified_blobs=len(results), total=len(jobs), network_entity_bytes=ledger['network_entity_bytes'])), flush=True)
                dump(private / 'acquisition-receipt.partial.json', sorted(results, key=lambda r:(r['source_id'],r['path'])))
    results.sort(key=lambda r:(r['source_id'],r['path']))
    receipt = dict(schema_version='style-historical-blog-acquisition/1.0', completed=True,
                   sources=sources, results=results, transfer_ledger=ledger,
                   acquired_candidate_bytes=sum(r['bytes'] for r in results if r['purpose']=='candidate_text'),
                   total_retained_source_bytes=sum(r['bytes'] for r in results),
                   model_admitted=False, model_fit=False, new_split_created=False,
                   old_labelled_test_text_read=False, personal_author_stage_accessed=False,
                   temporal_claim='Maintainer Git history and official commit-tree association; unsigned commit dates are not independent timestamps',
                   assistance_status='unknown', human_verified=False)
    dump(private / 'acquisition-receipt.json', receipt)
    print(json.dumps(dict(completed=True, verified_blobs=len(results), acquired_candidate_bytes=receipt['acquired_candidate_bytes'], network_entity_bytes=ledger['network_entity_bytes'])), flush=True)

if __name__ == '__main__':
    main()
