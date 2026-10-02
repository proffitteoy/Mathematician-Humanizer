"""Seal a strict public allowlist; source prose remains in the authorized cache."""
import argparse
import json
from pathlib import Path
from native_adapter import sha256, content_chars

FILES = (
    'native_adapter.py', 'test_native_adapter.py', 'validate_corpus.py',
    'verify_lineage.py', 'seal_public.py', 'README.md', 'MEASUREMENT_CONTRACT.md',
    'SOURCE_METADATA.json', 'REVIEW_SELECTION.json', 'AGGREGATE_VALIDATION.json',
    'HANDCHECK_AGGREGATE.json', 'LINEAGE_AND_FROZEN_CHECK.json', 'SYNTHETIC_TESTS.log',
    'INDEPENDENT_AUDIT.json', 'PUBLICATION_ALLOWLIST.txt', 'PUBLICATION_AUDIT.json',
)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--public',required=True,type=Path)
    p.add_argument('--private-inputs',required=True,type=Path)
    p.add_argument('--private-views',required=True,type=Path)
    args=p.parse_args()
    audit=json.loads((args.public/'INDEPENDENT_AUDIT.json').read_text())
    if audit['status'] not in {'passed','passed_with_limitations','passed_with_scope_limits'}:
        raise ValueError('Independent audit is not in a passed state')
    (args.public/'PUBLICATION_ALLOWLIST.txt').write_text('\n'.join(FILES+('PUBLIC_CHECKSUMS.json',))+'\n')
    texts=[]
    for row in map(json.loads,args.private_inputs.read_text().splitlines()):
        texts.extend(u['text'] for u in row['source_units'])
    for row in map(json.loads,args.private_views.read_text().splitlines()):
        texts.extend(c['text'] for c in row['view']['out_of_body_entity_text'])
    # Public metadata URLs/hashes are authorized. Source text windows are not.
    windows={t[i:i+40] for t in texts for i in range(max(0,len(t)-39)) if content_chars(t[i:i+40])>=20}
    scanned=0
    for name in FILES:
        if name in {'PUBLICATION_AUDIT.json'}: continue
        data=(args.public/name).read_text()
        public_windows={data[i:i+40] for i in range(max(0,len(data)-39))}
        if windows & public_windows:
            raise ValueError('Source-text window found in public allowlist: '+name)
        scanned+=1
    # Real per-sample measurements/offsets are forbidden export categories.
    unexpected=[p.name for p in args.public.iterdir() if p.is_file() and p.name not in set(FILES)|{'PUBLIC_CHECKSUMS.json'}]
    if unexpected: raise ValueError('Unexpected public file(s): '+repr(unexpected))
    report={'status':'passed','public_scope':'code, synthetic tests, source metadata, aggregate validation only',
            'allowlisted_files':len(FILES)+1,'files_source_window_scanned':scanned,
            'source_text_windows_checked':len(windows),'source_window_codepoints':40,
            'source_window_minimum_LN':20,'source_text_matches':0,
            'shorter_text_review':'Human-readable source metadata and synthetic-fixture/code allowlist inspected; window scan is not a proof against every short fragment',
            'excluded_categories':['raw prose','per-document measurements','native views','body offsets','private review packets','model state'],
            'private_inputs_distributed':False,'comparison_populations_changed':False,'fit_performed':False}
    (args.public/'PUBLICATION_AUDIT.json').write_text(json.dumps(report,indent=2)+'\n')
    manifest={name:{'sha256':sha256((args.public/name).read_bytes()),'bytes':(args.public/name).stat().st_size} for name in FILES}
    (args.public/'PUBLIC_CHECKSUMS.json').write_text(json.dumps({'schema_version':'public-package-checksums/1.0.0','files':manifest,'self_excluded':True},indent=2,sort_keys=True)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__': main()
