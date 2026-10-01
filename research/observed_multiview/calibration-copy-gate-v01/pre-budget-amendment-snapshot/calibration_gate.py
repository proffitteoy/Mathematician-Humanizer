"""Source-only exact96 signature/lineage gate. A proposal is NOT execution GO.

No source acquisition, candidate freeze, NLP, targets, fits, or replacements.
Natural execution is CLI execute only after independent manifest review + root GO.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from dataclasses import replace
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import signal
import sqlite3
import sys
import time
import types

sys.dont_write_bytecode = True
ROOT = Path('/workspace/shared/style-scale10-calibration-gate-v01')
PUBLIC, PRIVATE = ROOT/'public', ROOT/'private'
SOURCE = Path('/workspace/shared/style-scale10-source-v01')
SP, SV = SOURCE/'public', SOURCE/'private'
OLD = Path('/workspace/shared/style-compiler-data/exposure-fingerprints-v01')
REVIEW_ROOT = Path('/workspace/shared/style-scale10-old-projection-review-v01/public')
CERT = REVIEW_ROOT/'BOUNDED_COMPATIBILITY_CERTIFICATE.json'
CERT_SHA = 'bcd447e5bdcefa3db6d980d100ddc44ce1c49c8a560fd8d84870ddb379685768'
FREEZE_SHA = '5eb673703d71a6f26d8f2828c99e3e4d857355714b541d38ba15fdc424a142cf'
SOURCE_CONTRACT = SV/'calibration.contract.proposal.v02.json'
SOURCE_CONTRACT_SHA = 'ea88b0398cf3d60178056b4f5ab44b7da9ec8196c7a87a2fa2c07ba20d29d1c2'
SOURCE_PINS = {
 'registry.py':'62f35bc593b047eada9d856701e36b0648f1be0fbcb3411c8b0b2afc1f1433db',
 'matcher.py':'ae9bed1b9b2bed4ec56647791bd459a9cb4787fb1c91ac8837ec97eb58d9ccb8',
 'compatibility.py':'61fd039ca983a9ef4a2de0a79beca6cac748072ce3c9b046fdeff3a16efc1e3a',
 'project_wikitext.py':'387a8a82eb4024ac2c324b841f0ebbc090818f2d81a364113881b9ae0b954da0',
 'projection_contract.py':'e508374e28bc2390da33aabd95bf6d89bac9c84181a8a6447d0407b7c88976a2',
 'source_risk_gate.py':'c5ea663a8264b0efa4dc30aa2ae00906dc49d2a2f3123adfe941156ec404a77a',
 'preparse.py':'c234f975f90a5699d3c924643a33befbad680385f45d6e475d5a4e94dcc46f3a',
 'runner.py':'f433b9e8292e6e149ed18d8afce15f7be56ab93a944c88271e89ee2b3709e70d'}
_frozen_sources={}
for _name, _sha in SOURCE_PINS.items():
    _raw=(SP/_name).read_bytes()
    if hashlib.sha256(_raw).hexdigest() != _sha:
        raise RuntimeError('frozen_source_implementation_changed')
    _frozen_sources[_name]=_raw
# Execute exactly the checked bytes. PYTHONDONTWRITEBYTECODE alone does not
# prevent reading stale/unbound .pyc caches. Never modify the frozen source tree.
for _name in ('registry','matcher','project_wikitext','projection_contract',
              'source_risk_gate','compatibility','runner'):
    _module=types.ModuleType(_name)
    _module.__file__=str(SP/(_name+'.py'));_module.__package__=''
    sys.modules[_name]=_module
    exec(compile(_frozen_sources[_name+'.py'],_module.__file__,'exec'),_module.__dict__)
sys.path.insert(0, str(SP))
from registry import (GateError, require, canonical, digest, binding, verify_binding,
                      filehash, load_json, DSU, SOURCES, RAW_OBJECTS, CAPS, validate_member)
from matcher import (Signature, signature, SignatureWriter, SignaturePackage, pack_ids,
                     unpack_ids, MAX_VIEWS, MAX_TOTAL_GRAMS, CompatibilityError, BoundExceeded)
from compatibility import (ReviewedCompatibility, expand_coverage_aliases, PACKAGE_ARTIFACTS)
from projection_contract import validate_projection
from project_wikitext import project
from source_risk_gate import gated_metadata
import runner

VERSION = 'scale10-calibration-copy-lineage/0.1.0'
BASELINE = 843782930
RESERVE = 80*1024**2
TERMINAL_RESERVE = 64*1024
RECORD_EXPANDED_CAP = 16*1024**2
BATCH_RECORDS = 8
INCREMENT_CAP = 300_000_000
MARKER = PRIVATE/'calibration-gate.ONE_TIME_STARTED.private.json'
MANIFEST = PRIVATE/'calibration-gate.manifest.proposal.private.json'
CONTROL = SV/'control.json'


def strict_json(data):
    def pairs(rows):
        result={}
        for k,v in rows:
            require(k not in result, 'duplicate_json_key'); result[k]=v
        return result
    return json.loads(data, object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(GateError('nonfinite_json')))


def tree_size(root):
    root=Path(root); total=0
    if not root.exists(): return 0
    require(not root.is_symlink(), 'private_root_symlink')
    for p in root.rglob('*'):
        require(not p.is_symlink(), 'private_tree_symlink')
        if p.is_file(): total+=p.stat().st_size
    return total


class Guard:
    """All outputs/journals/temporary files charged to the SAME exact96 reserve."""
    def __init__(self, *, roots=None, old_root=OLD, control=CONTROL, prior_seconds=0,
                 baseline=BASELINE, reserve=RESERVE, caps=None):
        self.roots=list(roots or [SV, PRIVATE]); self.old_root=Path(old_root)
        self.control=Path(control); self.prior_seconds=prior_seconds
        self.baseline=baseline; self.reserve=reserve; self.caps=dict(CAPS if caps is None else caps)
        self.start=time.monotonic(); self.cpu=time.process_time()
    def used(self):
        return max(self.caps['old_fingerprint_minimum_bytes'], tree_size(self.old_root))+sum(tree_size(p) for p in self.roots)
    def check(self, reserve=0):
        while True:
            require(self.prior_seconds+time.monotonic()-self.start<=self.caps['wall_seconds'], 'wall_time_limit')
            require(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024<=self.caps['rss_bytes'], 'rss_limit')
            used=self.used()
            require(used+reserve+TERMINAL_RESERVE<=self.caps['private_bytes'], 'all_private_derivatives_cap')
            require(used-self.baseline+reserve+TERMINAL_RESERVE<=self.reserve, 'shared_exact96_output_reserve_exceeded')
            state=load_json(self.control)
            require(set(state)=={'state'} and state['state'] in ('run','pause','stop'), 'invalid_control')
            require(state['state']!='stop', 'operator_stop')
            if state['state']=='run': return
            time.sleep(0.1)
    def write(self, path, value, *, compressed=False):
        data=canonical(value)+b'\n'
        if compressed: data=gzip.compress(data, compresslevel=6, mtime=0)
        self.check(len(data)); p=Path(path)
        with p.open('xb') as f: f.write(data); f.flush(); os.fsync(f.fileno())
        self.check()
    def resources(self):
        return {'elapsed_seconds':time.monotonic()-self.start, 'cpu_seconds':time.process_time()-self.cpu,
                'prior_stage_elapsed_seconds':self.prior_seconds,
                'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
                'all_private_bytes':self.used(), 'shared_exact96_baseline':self.baseline,
                'shared_exact96_reserve':self.reserve}


def load_bound_record(path_binding, row):
    """Only execute calls this on real cache, after marker and GO validation."""
    verify_binding(path_binding)
    with gzip.open(path_binding['path'], 'rb') as f:
        raw=f.read(RECORD_EXPANDED_CAP+1)
        require(len(raw)<=RECORD_EXPANDED_CAP and not f.read(1), 'cache_expansion_cap')
    obj=strict_json(raw)
    require(obj.get('metadata')==row, 'cache_record_identity_mismatch')
    text=obj.get('raw_source_text')
    require(isinstance(text,str) and len(text)==row['source_codepoints'] and
            hashlib.sha256(text.encode()).hexdigest()==row['source_sha256']==obj.get('source_sha256'),
            'raw_source_hash_or_length_mismatch')
    require(200<=len(text)<=20000, 'frozen_source_size_outside_frame')
    require(obj.get('human_gold') is False and obj.get('rights_review')=='pending_independent_record_review', 'cache_claim_changed')
    md,risks=gated_metadata(text,row['metadata'])
    require(obj.get('source_risks')==risks, 'risk_sidecar_changed')
    p=obj['projection']; validate_projection(text,p)
    require(p==project(text,row['source_frame'],md), 'frozen_projection_replay_mismatch')
    # Qualification/features are not read, recomputed or used by this gate.
    return obj


def record_views(obj, row):
    text=obj['raw_source_text']; p=obj['projection']
    views=[('raw_source','full_raw_source_view',text)]
    for i,segment in enumerate(p['segments']):
        views.append((f'projected_segment:{i}','projected_segment',segment['text']))
        for n,(lo,hi) in enumerate(segment['source_spans']):
            views.append((f'raw_span:{i}:{n}','mapped_contiguous_raw_source_span',text[lo:hi]))
    require(len(views)<=MAX_VIEWS, 'record_views_cap')
    sigs=[signature(t, row['record_key']+'/'+key, role) for key,role,t in views]
    require(sum(len(s.grams) for s in sigs)<=MAX_TOTAL_GRAMS, 'record_grams_cap')
    return views,sigs


def build_signature_package(rows, cache, out, guard):
    require(len(rows)==len(cache), 'record_cache_count_mismatch')
    writer=SignatureWriter(out,guard=lambda _:guard.check())
    writer.db.execute('PRAGMA temp_store=MEMORY')
    counts=Counter(); identities=[]
    try:
        for row,b in zip(rows,cache):
            guard.current_record={'record_key':row['record_key'],'member_key':row['member_key'],'source_sha256':row['source_sha256']}
            guard.check(); obj=load_bound_record(b,row); views,sigs=record_views(obj,row)
            for (key,role,text),sig in zip(views,sigs):
                # Conservative per-add SQLite page/index/journal reserve. Both live
                # DB and rollback journals remain below the charged private root.
                guard.check(1024**2+1024*len(sig.grams)+2*len(text.encode()))
                writer.add(text, source_id=row['source_frame'], member_key=row['member_key'],
                    exposure_role='calibration_exposed',source_view_role=role,
                    source_object_sha256=RAW_OBJECTS[row['source_frame']]['sha256'],
                    locator={'record_key':row['record_key'],'view_key':row['record_key']+'/'+key,
                             'source_sha256':row['source_sha256'],'projection_sha256':obj['projection']['projection_sha256'],
                             'record_locator':row['locator']})
                counts[role]+=1
            restricted=bool(obj['source_risks'] or obj['projection'].get('flags',{}).get('record_quarantine_reasons') or not obj['projection']['segments'])
            counts['records']+=1; counts['role_or_zero_segment_quarantines']+=int(restricted)
            identities.append({'record_key':row['record_key'],'member_key':row['member_key'],
                'source_sha256':row['source_sha256'],'projection_sha256':obj['projection']['projection_sha256'],
                'cache_sha256':b['sha256'],'bounded_projected_view_supported':not restricted})
        guard.current_record=None
        guard.check(1024**2+256*writer.binding_count); artifact=writer.finish(); guard.check()
        return artifact,dict(counts),identities
    except BaseException:
        writer.close_failed(); raise


def package_record_signatures(package, rows):
    """Reconstruct complete private signatures, translating IDs within THIS DB."""
    keys={r['record_key'] for r in rows}; result=defaultdict(list)
    for tid,role,locator in package.db.execute('SELECT text_id,source_view_role,locator_json FROM bindings ORDER BY id'):
        loc=strict_json(locator)
        if loc['record_key'] not in keys: continue
        raw,norm,npoints,count,packed=package.db.execute('SELECT raw_sha256,normalized_sha256,normalized_codepoints,gram_count,gram_ids_delta_zlib FROM texts WHERE id=?',(tid,)).fetchone()
        ids=unpack_ids(packed,count,package.max_gram_id); grams=set()
        for start in range(0,len(ids),400):
            part=ids[start:start+400]
            grams.update(x[0] for x in package.db.execute('SELECT sha256 FROM grams WHERE id IN ('+','.join('?' for _ in part)+')',part))
        require(len(grams)==count,'signature_dictionary_incomplete')
        blocks=tuple(package.db.execute('SELECT kind,ordinal,normalized_sha256,normalized_codepoints FROM blocks WHERE text_id=? ORDER BY kind,ordinal',(tid,)))
        result[loc['record_key']].append(Signature(loc['view_key'],role,raw,norm,npoints,frozenset(grams),blocks))
    require(set(result)==keys, 'signature_record_missing')
    return result


def compare_batch(rows, sigmap, packages, guard, budget):
    combined=[sig for row in rows for sig in sigmap[row['record_key']]]
    require(len(combined)<=MAX_VIEWS and sum(len(s.grams) for s in combined)<=MAX_TOTAL_GRAMS,'fixed_batch_cap_no_retry')
    require(len({s.key for s in combined})==len(combined),'duplicate_signature_view_key')
    names=[p.name for p in packages]
    require(len(names)==len(set(names))==4,'required_four_signature_packages')
    matched=[]
    for p in packages:
        guard.check()
        r=p.compare(combined,resource_callback=lambda _:guard.check(),comparison_budget=budget)
        require(r.get('complete_signature_scan') is True and r['reference_texts_expected']==r['reference_texts_scanned'], 'incomplete_package_scan')
        matched.append(r)
    result=[]
    for row in rows:
        views={s.key for s in sigmap[row['record_key']]}; receipts=[]
        for m in matched:
            hits=[h for h in m['hits'] if h['candidate_view'] in views]; tids={h['reference_text_id'] for h in hits}
            receipts.append({k:v for k,v in m.items() if k not in ('hits','bindings','candidate_full_gram_counts','candidate_mapped_gram_counts')}|
                {'hits':hits,'bindings':[b for b in m['bindings'] if b['reference_text_id'] in tids]})
        result.append({'record_key':row['record_key'],'source_sha256':row['source_sha256'],
                       'signature_scan_complete':True,'complete_declared_view_comparisons':True,'packages':receipts})
    return result


def reconstruct_graph(db):
    """Rebuild every namespaced member and prior ancestor, never compare old IDs."""
    dsu=DSU(); heads={}; old={}; excluded=set()
    for member,comp,flag in db.execute('SELECT member_key,component_id,excluded FROM members ORDER BY member_key'):
        validate_member(member); require(flag in (0,1), 'invalid_exclusion_flag')
        dsu.add(member); old[member]=comp
        if comp in heads: dsu.union(heads[comp],member,'old_component')
        else: heads[comp]=member
        if flag: dsu.expose(member); excluded.add(member)
    for a,b,kind in db.execute('SELECT a,b,kind FROM lineage'):
        require(a in old and b in old and old[a]==old[b], 'lineage_ancestry_mismatch')
        dsu.union(a,b,kind)
    mapping,contaminated=dsu.freeze()
    require(mapping==old, 'base_component_hash_mismatch')
    return dsu,old,excluded


def finish_graph(dsu,rows):
    # The old exposed set is intact here. Calibration is NOT yet exposed.
    mapping,old_contaminated=dsu.freeze(); source_counts={}
    old_hits=0
    for source in SOURCES:
        group=[r for r in rows if r['source_frame']==source]
        require(len(group)==32, 'calibration_frozen_count')
        comps={mapping[r['member_key']] for r in group}; source_counts[source]=len(comps)
        old_hits+=sum(mapping[r['member_key']] in old_contaminated for r in group)
    distinct=len({mapping[r['member_key']] for r in rows})
    underfilled=bool(old_hits or any(x<32 for x in source_counts.values()) or distinct<96)
    for row in rows: dsu.expose(row['member_key'])
    final,contaminated=dsu.freeze()
    require(final==mapping,'exposure_must_not_change_component_ids')
    return {'schema_version':VERSION,'member_to_component':final,'contaminated_components':sorted(contaminated),
            'old_contaminated_components_before_calibration_exclusion':sorted(old_contaminated)}, {
        'status':'calibration_underfilled' if underfilled else 'calibration_copy_gate_complete_pending_independent_review',
        'calibration_final_components':source_counts,'all_calibration_distinct_components':distinct,
        'calibration_records_connected_to_old_exclusion':old_hits,'member_count':len(mapping),
        'final_component_count':len(set(mapping.values())),'contaminated_component_count':len(contaminated)}


def apply_edges(dsu,edges):
    for edge in edges:
        a,b=edge['left_member_key'],edge['right_member_key']
        require(a in dsu.parent and b in dsu.parent,'copy_edge_member_missing_from_full_registry')
        require(edge.get('reasons'), 'copy_edge_without_evidence')
        dsu.union(a,b,'copy_edge')


def artifact_paths():
    return {'old_raw_database':OLD/'fingerprints.private.sqlite',
            'three_blog_raw_database':SV/'incremental-blog-exclusion.private.sqlite',
            'projected_database':SV/'old-projection-exclusion.signatures.private.sqlite',
            'coverage_database':SV/'old-projection-exclusion.coverage.private.sqlite',
            'derivation_receipt':SV/'old-projection-exclusion.receipt.private.json',
            'derivation_plan':SV/'old-projection-exclusion.plan.private.json',
            'projector':SP/'project_wikitext.py','validator':SP/'projection_contract.py',
            'independent_review_report':REVIEW_ROOT/'INDEPENDENT_REVIEW.zh.md'}


def code_bindings():
    return [binding(p) for p in sorted(PUBLIC.glob('*.py'))]+runner.source_code_bindings()


def validate_source_complete():
    require(filehash(SOURCE_CONTRACT)==SOURCE_CONTRACT_SHA,'source_contract_changed')
    c=load_json(SOURCE_CONTRACT)
    require(c['disk_preflight']['private_bytes_including_old']==BASELINE and c['stage_output_budget_bytes']==RESERVE,'shared_reservation_changed')
    require(filehash(SV/'calibration96.freeze.private.json')==FREEZE_SHA,'exact96_freeze_changed')
    freeze=load_json(SV/'calibration96.freeze.private.json'); rows=freeze['records']
    require(len(rows)==96 and len({r['record_key'] for r in rows})==96 and Counter(r['source_frame'] for r in rows)==Counter({s:32 for s in SOURCES}), 'exact96_scope_mismatch')
    require(sum(r['source_codepoints'] for r in rows)==144703,'frozen_character_total_changed')
    for b in c['code_bindings']+c['indirect_bindings']+[c['freeze'],c['registry'],c['metadata_database']]: verify_binding(b)
    r=load_json(SV/'calibration.receipt.private.json')
    require(r.get('status')=='source_projection_complete_pending_independent_review_and_lineage' and r.get('contract_sha256')==SOURCE_CONTRACT_SHA,'source_calibration_not_complete')
    for key in ('counts','completed_counts','actual_read_counts','projection_attempt_counts','source_attempt_counts'):
        require(r.get(key)=={s:32 for s in SOURCES},'source_receipt_incomplete_'+key)
    marker=load_json(SV/'calibration.ONE_TIME_STARTED.json')
    require(marker.get('stage')=='calibration' and marker.get('contract_sha256')==SOURCE_CONTRACT_SHA and marker.get('status')=='consumed_no_implicit_retry','source_marker_mismatch')
    require(marker.get('review_sha256')==r.get('review_sha256') and len(marker.get('root_GO_sha256',''))==64,'source_authority_binding_missing')
    files={SV/'calibration.records'/(digest(row['record_key'])+'.private.json.gz') for row in rows}
    require(set((SV/'calibration.records').iterdir())==files,'exact96_cache_file_scope')
    progress=[strict_json(line) for line in (SV/'calibration.progress.private.jsonl').read_bytes().splitlines()]
    require(len(progress)==96 and {x['record_key'] for x in progress}=={r['record_key'] for r in rows},'source_progress_incomplete')
    bykey={x['record_key']:x for x in progress}
    cache=[]
    for row in rows:
        b=binding(SV/'calibration.records'/(digest(row['record_key'])+'.private.json.gz'))
        event=bykey[row['record_key']]
        require(event['event']=='record_processed' and event['source_frame']==row['source_frame'] and event['source_sha256']==row['source_sha256'] and event['output_sha256']==b['sha256'],'cache_progress_hash_mismatch')
        cache.append(b)
    exposure=[strict_json(line) for line in (SV/'exposure.private.jsonl').read_bytes().splitlines()]
    e=[x for x in exposure if x.get('event')=='pre_read_calibration_exposure' and x.get('contract_sha256')==SOURCE_CONTRACT_SHA]
    require(len(e)==96 and {x['record_key'] for x in e}=={r['record_key'] for r in rows} and all(x.get('exclude_entire_final_component') is True for x in e),'source_exposure_incomplete')
    return c,freeze,cache


def prepare_manifest():
    """AFTER source run: hashes compressed caches, never decompresses them."""
    require(not MARKER.exists() and not MANIFEST.exists(),'one_time_or_proposal_exists_no_retry')
    c,freeze,cache=validate_source_complete(); guard=Guard(prior_seconds=runner.prior_wall_seconds()); guard.check()
    prior=runner.prior_budget_bindings()
    fixed=[SOURCE_CONTRACT,SV/'source-registry.private.json',SV/'metadata.registry.sqlite',SV/'calibration96.freeze.private.json',
           SV/'calibration.receipt.private.json',SV/'calibration.ONE_TIME_STARTED.json',SV/'calibration.progress.private.jsonl',
           SV/'calibration.source-read.private.jsonl',SV/'exposure.private.jsonl',CERT]
    result={'schema_version':VERSION,'status':'proposal_not_authorization','action':'CALIBRATION_COPY_GATE_GO',
            'fixed_private_root':str(PRIVATE),'control':str(CONTROL),'one_time_marker':str(MARKER),
            'source_contract_sha256':SOURCE_CONTRACT_SHA,'calibration_freeze_sha256':FREEZE_SHA,'certificate_sha256':CERT_SHA,
            'record_count':96,'source_codepoints':144703,'cache_bindings':cache,'input_bindings':[binding(p) for p in fixed],
            'code_bindings':code_bindings(),'indirect_bindings':runner.indirect_bindings(),
            'runtime':{'python':sys.version,'executable':binding(Path(sys.executable).resolve())},
            'artifact_bindings':{k:binding(p) for k,p in artifact_paths().items()},'prior_budget_bindings':prior,
            'prior_elapsed_seconds':runner.prior_wall_seconds(),'caps':CAPS,'shared_baseline':BASELINE,'shared_reserve_bytes':RESERVE,
            'batch_records':BATCH_RECORDS,'comparison_increment_cap':INCREMENT_CAP,'replacement_allowed':False,
            'candidate_frame_creation_allowed':False,'source_admission_authorized':False,'no_natural_body_decompressed_during_prepare':True}
    guard.write(MANIFEST,result)
    return {'status':'manifest_requires_independent_review_and_root_GO','manifest_sha256':filehash(MANIFEST)}


def verify_authority(manifest_path,manifest_sha,review_path,review_sha,go_path):
    require(Path(manifest_path).resolve()==MANIFEST,'manifest_path_changed')
    require(filehash(manifest_path)==manifest_sha and filehash(review_path)==review_sha,'independent_manifest_or_review_hash_mismatch')
    m=load_json(manifest_path); review=load_json(review_path); go=load_json(go_path)
    require(m.get('schema_version')==VERSION and m.get('status')=='proposal_not_authorization','manifest_schema')
    require(m.get('action')=='CALIBRATION_COPY_GATE_GO' and m.get('source_contract_sha256')==SOURCE_CONTRACT_SHA and m.get('calibration_freeze_sha256')==FREEZE_SHA and m.get('certificate_sha256')==CERT_SHA,'manifest_source_scope_changed')
    require(m.get('fixed_private_root')==str(PRIVATE) and m.get('control')==str(CONTROL) and m.get('one_time_marker')==str(MARKER),'fixed_execution_paths_changed')
    require(m.get('caps')==CAPS and m.get('shared_baseline')==BASELINE and m.get('shared_reserve_bytes')==RESERVE and m.get('batch_records')==BATCH_RECORDS and m.get('comparison_increment_cap')==INCREMENT_CAP,'manifest_limits_changed')
    require(m.get('record_count')==96 and m.get('source_codepoints')==144703 and m.get('replacement_allowed') is False and m.get('candidate_frame_creation_allowed') is False and m.get('source_admission_authorized') is False,'manifest_scope_changed')
    require(review.get('decision')=='APPROVE_CALIBRATION_COPY_GATE_EXECUTION' and review.get('manifest_sha256')==manifest_sha and review.get('synthetic_tests_passed') is True and review.get('reviewer') and review.get('independent_review') is True,'independent_review_required')
    require(go.get('actor')=='root' and go.get('action')=='CALIBRATION_COPY_GATE_GO' and go.get('manifest_sha256')==manifest_sha and go.get('review_sha256')==review_sha and go.get('no_other_stages') is True,'explicit_root_copy_gate_GO_required')
    require(m['runtime']['python']==sys.version,'runtime_changed');verify_binding(m['runtime']['executable'])
    require(m['code_bindings']==code_bindings(),'code_set_or_hash_changed')
    for b in m['code_bindings']+m['indirect_bindings']+m['input_bindings']+list(m['artifact_bindings'].values())+m['cache_bindings']: verify_binding(b)
    require({(b['path'],b['sha256'],b['bytes']) for b in runner.indirect_bindings()} <= {(b['path'],b['sha256'],b['bytes']) for b in m['indirect_bindings']},'runtime_dependency_unbound')
    require(m['prior_budget_bindings']==runner.prior_budget_bindings() and m['prior_elapsed_seconds']==runner.prior_wall_seconds(),'shared_prior_budget_changed')
    c,freeze,cache=validate_source_complete()
    require(cache==m['cache_bindings'],'immutable96_cache_changed')
    require(m['artifact_bindings']=={k:binding(p) for k,p in artifact_paths().items()},'certificate_artifact_scope_changed')
    require(filehash(CERT)==CERT_SHA,'compatibility_certificate_changed')
    return m,freeze


def acquire_marker(path,guard,payload):
    require(not Path(path).exists(),'one_time_stage_already_consumed_no_retry')
    guard.write(path,dict(payload,status='consumed_no_implicit_retry'))


def execute(manifest,manifest_sha,review,review_sha,go):
    require(not MARKER.exists(),'one_time_stage_already_consumed_no_retry')
    sandbox=runner.install_offline_sandbox()
    resource.setrlimit(resource.RLIMIT_AS,(CAPS['rss_bytes'],CAPS['rss_bytes']))
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    prior=runner.prior_wall_seconds(); guard=Guard(prior_seconds=prior); guard.check()
    def timeout(*_): raise GateError('wall_time_limit')
    signal.signal(signal.SIGALRM,timeout); signal.setitimer(signal.ITIMER_REAL,max(.001,CAPS['wall_seconds']-prior))
    m,freeze=verify_authority(manifest,manifest_sha,review,review_sha,go)
    acquire_marker(MARKER,guard,{'manifest_sha256':manifest_sha,'review_sha256':review_sha,'root_GO_sha256':filehash(go)})
    result={'schema_version':VERSION,'status':'stopped_partial_no_retry','manifest_sha256':manifest_sha,
            'review_sha256':review_sha,'source_admission_authorized':False,'G2_admitted':False,'human_gold':False,
            'model_POS_target_fit_calls':0,'candidate_frame_created':False,'replacement_records':0,
            'negative_match_is_semantic_copy_absence':False,'sandbox':sandbox,'outputs':[]}
    packages=[];adapter=None; db=None
    try:
        rows=freeze['records']; db=sqlite3.connect((SV/'metadata.registry.sqlite').as_uri()+'?mode=ro&immutable=1',uri=True)
        db.execute('PRAGMA query_only=ON'); dsu,old,old_exposed=reconstruct_graph(db)
        for row in rows: require(row['member_key'] in old and old[row['member_key']]==row['component_id'],'calibration_base_component_mismatch')
        artifacts=artifact_paths(); cert=load_json(CERT); by_artifact={}
        for name in sorted(PACKAGE_ARTIFACTS):
            p=SignaturePackage(artifacts[name],cert['artifacts'][name]['sha256'],cert['package_names'][name]);packages.append(p);by_artifact[name]=p
        adapter=ReviewedCompatibility(CERT,CERT_SHA,artifact_paths=artifacts,package_by_artifact=by_artifact)
        artifact,counts,identities=build_signature_package(rows,m['cache_bindings'],PRIVATE/'calibration.signatures.private.sqlite',guard)
        result['outputs'].append(artifact);result['signature_counts']=counts
        guard.write(PRIVATE/'record-identities.private.json',identities);result['outputs'].append(binding(PRIVATE/'record-identities.private.json'))
        own=SignaturePackage(artifact['path'],artifact['sha256'],'exact96_calibration');packages.append(own)
        budget={'used':0,'cap':INCREMENT_CAP};edge_count=0;all_old_hits=0;batch_bindings=[]
        for start in range(0,96,BATCH_RECORDS):
            batch=rows[start:start+BATCH_RECORDS];sigmap=package_record_signatures(own,batch)
            receipts=compare_batch(batch,sigmap,packages,guard,budget);edges=[]
            for row,r in zip(batch,receipts):
                # Alias expansion is mandatory even for raw-only/quarantined rows.
                # Annotation must not suppress collisions on a role failure.
                expanded=expand_coverage_aliases(r,row['member_key'],coverage_db=adapter.coverage,
                    package_by_artifact=by_artifact,package_names=cert['package_names'],resource_callback=lambda _:guard.check())
                apply_edges(dsu,expanded);edges.extend(expanded)
                if any(p['hits'] for p in r['packages'] if p['package']!='exact96_calibration'):all_old_hits+=1
            edge_count+=len(edges)
            p=PRIVATE/f'comparison-batch-{start//BATCH_RECORDS:02d}.private.json.gz'
            guard.write(p,{'record_keys':[r['record_key'] for r in batch],'receipts':receipts,'expanded_edges':edges},compressed=True)
            b=binding(p);batch_bindings.append(b);result['outputs'].append(b);guard.check()
        graph,aggregate=finish_graph(dsu,rows)
        require(not all_old_hits or aggregate['status']=='calibration_underfilled','old_match_without_old_contamination')
        graph.update(metadata_database_sha256=filehash(SV/'metadata.registry.sqlite'),calibration_freeze_sha256=FREEZE_SHA,
                     comparison_batches=batch_bindings,signature_package_sha256=artifact['sha256'])
        guard.write(PRIVATE/'final-components.private.json.gz',graph,compressed=True)
        result['outputs'].append(binding(PRIVATE/'final-components.private.json.gz'))
        result.update(aggregate,expanded_copy_edges=edge_count,old_package_hit_records=all_old_hits,
                      comparison_increment_count=budget['used'],matching_batches_completed=len(batch_bindings))
        for b in m['code_bindings']+m['cache_bindings']+list(m['artifact_bindings'].values()):verify_binding(b)
        guard.check()
    except BaseException as error:
        result['status']='stopped_partial_no_retry'
        # Exception messages can include text/locators. Only private terminal sees
        # vetted machine codes; unknown exceptions are represented by class name.
        result['failure_code']=str(error) if isinstance(error,(GateError,CompatibilityError)) else type(error).__name__
    finally:
        if adapter:adapter.close()
        for p in packages:p.close()
        if db:db.close()
        if getattr(guard,'current_record',None):result['current_record_at_failure']=guard.current_record
        result['resources']=guard.resources();signal.setitimer(signal.ITIMER_REAL,0)
        p=PRIVATE/'calibration-gate.receipt.private.json'; data=canonical(result)+b'\n'
        require(len(data)<=TERMINAL_RESERVE,'terminal_receipt_byte_limit')
        # Receipt path/identities only private. Terminal reserve is checked even
        # after pause, stop or caps; no retry and no removal of partial artifacts.
        require(guard.used()+len(data)<=CAPS['private_bytes'] and guard.used()-BASELINE+len(data)<=RESERVE,'terminal_receipt_budget_exhausted')
        with p.open('xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
    public={k:v for k,v in result.items() if k not in ('outputs','failure_code','sandbox','current_record_at_failure')}
    public['output_sha256']=[b['sha256'] for b in result['outputs']]
    public['terminal_receipt_sha256']=filehash(PRIVATE/'calibration-gate.receipt.private.json')
    # No file locators, record/member identities, per-record hashes, titles or text.
    path=PUBLIC/'execution.aggregate.json'
    with path.open('x') as f:json.dump(public,f,sort_keys=True);f.write('\n')
    return public


def main():
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest='cmd',required=True)
    sub.add_parser('prepare-manifest',help='Only after source run; immutable compressed cache hashing, no decompression')
    e=sub.add_parser('execute')
    for name in ('manifest','manifest-sha256','review','review-sha256','go'):e.add_argument('--'+name,required=True)
    a=p.parse_args()
    try:
        if a.cmd=='prepare-manifest':result=prepare_manifest()
        else:result=execute(a.manifest,a.manifest_sha256,a.review,a.review_sha256,a.go)
        print(json.dumps(result,sort_keys=True))
        return 0 if result['status'] not in ('stopped_partial_no_retry','calibration_underfilled') else 2
    except BaseException as exc:
        print(json.dumps({'status':'execution_blocked_no_authority_or_preflight','error_type':type(exc).__name__}))
        return 2
if __name__=='__main__':sys.exit(main())
