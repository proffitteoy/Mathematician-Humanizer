from pathlib import Path
import hashlib,json
B=Path(__file__).resolve().parents[2];C=B/'m4_chinese_paired_20261002';old=Path('/tmp/zh-corpus-audit');m=json.loads((old/'combined_manifest.json').read_text());out=[]
for model in ('chatgpt','davinci'):
 e=next(x for x in m['entries'] if x['name']=='m4_qazh_'+model+'.jsonl')
 full=C/'raw'/('qazh_'+model+'.jsonl')
 with full.open('rb') as f: data=b''.join(f.readline() for _ in range(128))
 assert len(data)==e['bytes'] and hashlib.sha256(data).hexdigest()==e['sha256']
 assert len(data.splitlines())==128 and data.endswith(b'\n')
 (old/'raw'/e['name']).write_bytes(data)
 out.append({'name':e['name'],'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'original_128_line_prefix_verified':True})
(C/'public/restored_exposure_receipt.json').write_text(json.dumps({'source_commit':'93b60d334c20148e3cea61afc8aaa8c1e861901f','source_manifest_git_blob_sha1':'d6e9822dd7018edd01e3fb01ac8811f85180f29c','files':out,'new_selection':False},indent=2)+'\n')
print('Both original 128-row exposure prefixes verified against published hashes')
