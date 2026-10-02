from pathlib import Path
import hashlib,json,tarfile
R=Path(__file__).resolve().parent
ALLOWED=['README.md','RESTORATION_RECEIPT.json','source_plan.json','restored_sources.json','restore_sources.py','restore_models.py','restore_stanza_runtime.py','restore_schema_runtime.py','restore_exposure_prefixes.py','verify_synthetic_parser.py','verify_restoration.py','seal_public.py','model_download_receipt.json','stanza_runtime_receipt.json','schema_runtime_receipt.json','parser_smoke_receipt.json','current_channel_schema.json','MODEL_FREE_TESTS.log','PARSER_SMOKE.log','RESTORE_MODELS.log','RESTORE_STANZA_RUNTIME.log','RESTORE_SCHEMA_RUNTIME.log','STANZA_INSTALL.log','SCHEMA_INSTALL.log']
for name in ALLOWED:assert (R/name).is_file(),name
manifest={'purpose':'Publication-safe code, protocols and aggregate verification only','release_boundary':'No raw corpus, private record identities, raw locators, source text hashes, per-sample observations, parser outputs or caches','inventory_caveat':'49 pinned instrument/test source files form a functional recovery inventory; lost original48-file inventory identity is not certified','body_read_boundary':'Original cohort preparation/integrity scripts reread TEST/davinci bytes only for original metadata restoration; no71-channel parsing, outcome analysis, fitting or tuning','files':[{'path':name,'bytes':(R/name).stat().st_size,'sha256':hashlib.sha256((R/name).read_bytes()).hexdigest()} for name in sorted(ALLOWED)]}
(R/'PUBLIC_FILES.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
target=R.parent.parent/'pinned-measurement-restoration-public-20261002.tar.gz'
with tarfile.open(target,'w:gz') as tar:
 for name in sorted(ALLOWED+['PUBLIC_FILES.json']):tar.add(R/name,arcname='public/'+name,recursive=False)
print(json.dumps({'public_file_count':len(ALLOWED)+1,'archive':str(target),'archive_bytes':target.stat().st_size,'archive_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'manifest_sha256':hashlib.sha256((R/'PUBLIC_FILES.json').read_bytes()).hexdigest()},indent=2))
