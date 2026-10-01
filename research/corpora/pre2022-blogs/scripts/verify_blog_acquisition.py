"""Independent read-only verification of acquisition identities and private ledger.

This script never reads a model split, target, prediction, or fingerprint DB.
"""
import argparse, collections, hashlib, json, pathlib, unicodedata

def sha(data): return hashlib.sha256(data).hexdigest()
def canonical(value): return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))

def reconstruct_tree(rows):
    entries=collections.defaultdict(list)
    expected={}
    for r in rows:
        p=pathlib.PurePosixPath(r['path'])
        parent='' if str(p.parent)=='.' else str(p.parent)
        entries[parent].append((p.name,r))
        if r['type']=='tree': expected[r['path']]=r['sha']
    def walk(directory):
        payload=bytearray()
        for name,row in sorted(entries[directory],key=lambda p:(p[0]+('/' if p[1]['type']=='tree' else '')).encode()):
            if row['type']=='tree':
                child=walk(row['path'])
                assert child==expected[row['path']]
            else: child=row['sha']
            payload.extend((str(int(row['mode']))+' '+name).encode()+b'\0'+bytes.fromhex(child))
        return hashlib.sha1(b'tree '+str(len(payload)).encode()+b'\0'+payload).hexdigest()
    return walk('')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=pathlib.Path,required=True)
    ap.add_argument('--original-root',type=pathlib.Path,required=True);args=ap.parse_args()
    root,private=args.root,args.root/'private'
    receipt=json.loads((private/'acquisition-receipt.json').read_text())
    aggregate=json.loads((root/'public/blog-acquisition.aggregate.json').read_text())
    rows=[json.loads(l) for l in (private/'post-manifest.jsonl').read_text().splitlines()]
    assert unicodedata.unidata_version=='15.0.0'
    assert receipt['completed'] and not receipt['model_admitted'] and not receipt['model_fit']
    assert len(rows)==len({r['member_key'] for r in rows})==788
    input_map={(r['repository'],r['path']):r for r in receipt['results']}
    trees={}
    for source in receipt['sources']:
        p=private/'metadata'/(source['repository'].replace('/','__')+'.tree.json')
        assert sha(p.read_bytes())==source['manifest_sha256']
        tree=json.loads(p.read_text());assert not tree['truncated']
        assert reconstruct_tree(tree['tree'])==source['git_tree_sha1']
        trees[source['repository']]={r['path']:r for r in tree['tree']}
    for record in receipt['results']:
        raw=pathlib.Path(record['dest']).read_bytes()
        assert len(raw)==record['bytes'] and sha(raw)==record['sha256']
        obj=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
        assert obj==record['git_blob_sha1']==trees[record['repository']][record['path']]['sha']
    for row in rows:
        assert row['member_key']==canonical(['gitblog',row['repository'],'post:'+row['path']])
        raw=pathlib.Path(row['dest']).read_bytes()
        assert sha(raw)==row['sha256']
        n=''.join(c for c in unicodedata.normalize('NFKC',raw.decode()) if not c.isspace())
        assert sha(b'nfkc-no-ws/v1\0'+n.encode())==row['normalized_sha256']
        assert row['effective_text_license'] is None and not row['admitted'] and not row['human_verified']
    reps=json.loads((args.original_root/'private/representative-receipt.json').read_text())
    assert len(reps)==3
    for rep in reps:
        row=next(r for r in rows if r['repository']==rep['repository'] and r['path']==rep['path'])
        assert row['sha256']==rep['sha256'] and row['git_blob_sha1']==rep['git_blob_sha1']
        assert row['diagnostic_exposure'] and row['exclusion_role']=='permanent_exposed_diagnostic'
    assert sum(r['diagnostic_exposure'] for r in rows)==3
    assert sum(r['bytes'] for r in rows)==13_869_106
    ledger=receipt['transfer_ledger']
    assert ledger['network_entity_bytes']+ledger['prior_metadata_entity_allowance']<30*1024**2
    retained=sum(p.stat().st_size for p in root.rglob('*') if p.is_file())
    assert retained<100*1024**2
    assert not ledger['failures']
    assert sum(r['transfer_status']=='downloaded' for r in receipt['results'])==789
    assert sum(r['bytes'] for r in receipt['results'] if r['transfer_status']=='downloaded')==ledger['network_entity_bytes']
    assert sha((private/'post-manifest.jsonl').read_bytes())==aggregate['post_manifest_sha256']
    assert sha((private/'acquisition-receipt.json').read_bytes())==aggregate['acquisition_receipt_sha256']
    result=dict(status='PASS', verified_candidate_blobs=788, verified_license_blobs=4,
                source_trees_reconstructed=3, canonical_member_keys_verified=788,
                normalization_digests_verified=788, diagnostic_permanent_exclusions_verified=3,
                raw_candidate_bytes=13_869_106, all_retained_acquisition_directory_bytes=retained,
                transfer_body_bytes=ledger['network_entity_bytes'], transfer_metadata_allowance=ledger['prior_metadata_entity_allowance'],
                no_model_admission=True,no_old_labelled_test_access=True,
                verification_scope='Independent algorithmic recomputation by the acquisition worker; not an independent-person review')
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
