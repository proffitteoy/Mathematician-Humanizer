"""Freeze the deterministic subset before prediction, without inspecting outcomes."""
import argparse,json
from pathlib import Path
from research.parser_error.evaluate import ROOT,SOURCE_SHA,sha,read_records,select_records


def freeze_bytes(raw,preregister):
    if sha(raw)!=SOURCE_SHA:raise ValueError('corpus_hash_mismatch')
    chosen=select_records(read_records(raw))
    manifest=[]
    for x in chosen:
        manifest.append({'sent_id':x['meta']['sent_id'],'byte_offset':x['byte_offset'],'block_bytes':x['block_bytes'],
          'text_sha256':sha(x['meta']['text'].encode()),'stratum':'news' if x['meta']['sent_id'][0]=='n' else 'wiki'})
    return json.dumps({'selection':manifest,'preregister_sha256':sha(preregister)},ensure_ascii=False,sort_keys=True,indent=2).encode()


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--private-dir',type=Path,required=True);ap.add_argument('--verify-existing',action='store_true');args=ap.parse_args()
    if args.private_dir.resolve().is_relative_to(ROOT):raise ValueError('raw_data_must_stay_outside_repository')
    b=freeze_bytes((args.private_dir/'zh_pud-ud-test.conllu').read_bytes(),(ROOT/'research/parser_error/preregister.public.json').read_bytes())
    path=args.private_dir/'selection.private.json'
    if args.verify_existing:
        if path.read_bytes()!=b:raise ValueError('existing_selection_changed')
    else:
        with path.open('xb') as f:f.write(b)
    print(json.dumps({'selection_manifest_sha256':sha(b),'selected_records':64,'existing_verified':args.verify_existing}))

if __name__=='__main__':main()
