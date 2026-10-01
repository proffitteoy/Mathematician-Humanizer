"""Read-only final copy-gate preflight: hashes sealed bytes, no natural matching."""
import hashlib,importlib.machinery,json,pathlib,sys
P=pathlib.Path('/workspace/shared/style-scale10-calibration-gate-v01/public');V=P.parent/'private';SP=pathlib.Path('/workspace/shared/style-scale10-source-v01/public');SV=SP.parent/'private';O=pathlib.Path('/workspace/shared/style-scale10-copy-gate-review-v01/public')
def h(p):
 d=hashlib.sha256()
 with pathlib.Path(p).open('rb')as f:
  for b in iter(lambda:f.read(1048576),b''):d.update(b)
 return d.hexdigest()
def j(p):return json.loads(pathlib.Path(p).read_text())
mp=V/'calibration-gate.manifest.proposal.private.json';sha='1d403ebea3f3913ef5761e5d9f6161c9232fe2498d7965c88d15dd73250e17ac';assert h(mp)==sha;m=j(mp)
assert h(P/'FILE_HASHES.json')=='9b4bee70f49f9072e88c6e3c61cf998cd5d5280672f15eee6b674d6e9f95bc56'
for name,b in j(P/'FILE_HASHES.json').items():assert (P/name).stat().st_size==b['bytes'] and h(P/name)==b['sha256']
assert h(P/'calibration_gate.py')=='373b3f1e30f2db915c9d6a4ad8583cb65415a1f3e7bb4b52df0c4787405cea4f'
assert h(P/'verify_gate.py')=='7c2a0f1de974414440fa63d29877421c40bbefdb2e41e7d1dbd79caf63036e4b'
bs=m['code_bindings']+m['indirect_bindings']+m['input_bindings']+list(m['artifact_bindings'].values())+m['cache_bindings']+m['prior_budget_bindings']+[m['runtime']['executable']]+m['comparison_history']['bindings']
for b in bs:
 p=pathlib.Path(b['path']);assert p.stat().st_size==b['bytes'] and h(p)==b['sha256'],str(p)
assert {b['path']for b in m['code_bindings']}=={str(p)for root in (P,SP)for p in root.glob('*.py')}
seal=j(SV/'calibration.outputs.sealed.private.json');assert h(SV/'calibration.outputs.sealed.private.json')=='26f40568753bece5e26197fc696c371d728efbea3ed4ce111ab0c296bb371b51'
assert {(b['path'],b['bytes'],b['sha256'])for b in m['cache_bindings']}=={(b['path'],b['bytes'],b['sha256'])for b in seal['files']}
assert len(m['cache_bindings'])==m['record_count']==96 and m['source_codepoints']==144703
assert m['shared_reserve_bytes']==83886080 and m['shared_baseline']==843782930 and m['comparison_history']['used']==251617 and m['comparison_history']['cap']==300000000 and m['comparison_history']['scope']=='global_natural_source_phase_including_signature_readback'
assert not m['replacement_allowed'] and not m['candidate_frame_creation_allowed'] and not m['source_admission_authorized']
assert m['audit_storage_scope']['allowance_bytes']==4194304
importlib.machinery.SourceFileLoader.get_code=lambda self,fullname:compile(self.get_data(self.path),self.path,'exec',dont_inherit=True)
sys.path.insert(0,str(P));import calibration_gate as g
assert m['audit_storage_scope']==g.AUDIT_SCOPE and m['comparison_history']==g.comparison_history()
assert m['prior_budget_bindings']==g.runner.prior_budget_bindings() and m['prior_elapsed_seconds']==g.runner.prior_wall_seconds()
assert not g.MARKER.exists();guard=g.Guard(prior_seconds=m['prior_elapsed_seconds']);guard.check();used=guard.used();audit=g.audit_private_usage()
res={'schema_version':'independent-copy-gate-manifest-review/1','manifest_sha256':sha,'bound_file_entries_verified':len(bs),'code_files':len(m['code_bindings']),'sealed_cache_files':96,'natural_cache_decompressions':0,'natural_signature_comparisons':0,'shared_comparison_prior':251617,'shared_comparison_cap':300000000,'shared_prior_wall_seconds':m['prior_elapsed_seconds'],'charged_private_bytes_at_review':used,'shared_exact96_growth_including_audit_reserve':used-843782930,'audit_actual_bytes':audit,'audit_reserved_bytes':4194304,'audit_allowance_inside_80MiB_and_1GiB':True,'author_tests':43,'independent_fault_tests':7,'source_admission_approved':False,'root_GO_created':False}
(O/'manifest-checks.aggregate.json').write_text(json.dumps(res,indent=2)+'\n');print(json.dumps(res,indent=2))
