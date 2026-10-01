"""Freeze the deterministic subset before prediction, without inspecting outcomes."""
import argparse,json
from pathlib import Path
from research.parser_error.evaluate import ROOT,SOURCE_SHA,sha,read_records,select_records


def freeze_bytes(raw,preregister,version="1.1.0"):
    if version not in ('legacy','1.1.0'):raise ValueError('unsupported_selection_version')
    if sha(raw)!=SOURCE_SHA:raise ValueError('corpus_hash_mismatch')
    chosen=select_records(read_records(raw))
    manifest=[]
    for x in chosen:
        text=x['meta'].get('text')
        if version=='legacy' and text is None:raise ValueError('legacy_missing_text')
        item={'sent_id':x['meta']['sent_id'],'byte_offset':x['byte_offset'],'block_bytes':x['block_bytes'],
          'text_sha256':sha(text.encode()) if text is not None else None,
          'stratum':'news' if x['meta']['sent_id'][0]=='n' else 'wiki'}
        if version!='legacy':item['source_text_status']='missing' if text is None else ('empty' if text=='' else 'present')
        manifest.append(item)
    result={'selection':manifest,'preregister_sha256':sha(preregister)}
    if version!='legacy':result['schema_version']='pud-selection/1.1.0'
    return json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2).encode()


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--private-dir',type=Path,required=True);ap.add_argument('--verify-existing',action='store_true');args=ap.parse_args()
    if args.private_dir.resolve().is_relative_to(ROOT):raise ValueError('raw_data_must_stay_outside_repository')
    path=args.private_dir/'selection.private.json'
    version='1.1.0'
    if args.verify_existing:
        existing=json.loads(path.read_bytes())
        schema=existing.get('schema_version')
        if schema not in (None,'pud-selection/1.1.0'):raise ValueError('unsupported_selection_version')
        version='legacy' if schema is None else '1.1.0'
    b=freeze_bytes((args.private_dir/'zh_pud-ud-test.conllu').read_bytes(),(ROOT/'research/parser_error/preregister.public.json').read_bytes(),version=version)
    if args.verify_existing:
        if path.read_bytes()!=b:raise ValueError('existing_selection_changed')
    else:
        with path.open('xb') as f:f.write(b)
    print(json.dumps({'selection_manifest_sha256':sha(b),'selected_records':64,'existing_verified':args.verify_existing}))

if __name__=='__main__':main()
