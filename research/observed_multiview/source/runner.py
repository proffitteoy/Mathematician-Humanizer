"""Guarded offline source-only execution. IMPLEMENTATION is not permission to run.

Real execution requires independent contract hash, review hash and explicit GO.
All paths/record identities remain private. There is no automatic resume/retry.
"""
from __future__ import annotations
import argparse
import bz2
from collections import Counter
import ctypes
import errno
import hashlib
import gzip
import importlib
import json
import os
from pathlib import Path
import resource
import signal
import sys
import time
import unicodedata
import xml.parsers.expat

# Two threads are a maximum, not a claim that NLP libraries were used.
for _key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[_key]='2'
os.environ['CUDA_VISIBLE_DEVICES']=''
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parent))
from registry import (ROOT,PRIVATE,PUBLIC,DATA,CAPS,SOURCES,RAW_OBJECTS,READER_HASHES,
    GateError,require,canonical,digest,filehash,binding,verify_binding,load_json,write_new)

STAGES={'calibration':('CALIBRATION_GO','APPROVE_CALIBRATION_EXECUTION','calibration96.freeze.private.json'),
        'candidates':('CANDIDATE_SOURCE_GO','APPROVE_CANDIDATE_SOURCE_EXECUTION','candidate6000.freeze.private.json')}
CALIBRATION_OUTPUT_BUDGET=80*1024**2
CANDIDATES_EXECUTION_BLOCKED_UNTIL_FINGERPRINT_WRITER_INTEGRATED=True
FORBIDDEN_IMPORTS={'stanza','torch','transformers','sklearn','tensorflow','jax','pandas'}


def install_offline_sandbox():
    """Kernel seccomp deny-network + deny-child-execution, not just socket stubs."""
    require(sys.platform=='linux','linux_seccomp_required')
    libc=ctypes.CDLL(None,use_errno=True)
    require(libc.prctl(38,1,0,0,0)==0,'no_new_privileges_failed')
    lib=ctypes.CDLL('libseccomp.so.2',use_errno=True)
    lib.seccomp_init.argtypes=[ctypes.c_uint32];lib.seccomp_init.restype=ctypes.c_void_p
    lib.seccomp_syscall_resolve_name.argtypes=[ctypes.c_char_p];lib.seccomp_syscall_resolve_name.restype=ctypes.c_int
    lib.seccomp_rule_add.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_int,ctypes.c_uint];lib.seccomp_rule_add.restype=ctypes.c_int
    lib.seccomp_load.argtypes=[ctypes.c_void_p];lib.seccomp_load.restype=ctypes.c_int
    lib.seccomp_release.argtypes=[ctypes.c_void_p]
    ctx=lib.seccomp_init(0x7fff0000);require(bool(ctx),'seccomp_init_failed')
    denied=('socket','socketpair','socketcall','connect','bind','listen','accept','accept4','sendto','sendmsg','sendmmsg','recvfrom','recvmsg','recvmmsg','execve','execveat','fork','vfork','clone','clone3','io_uring_setup')
    try:
        for name in denied:
            nr=lib.seccomp_syscall_resolve_name(name.encode())
            if nr>=0:require(lib.seccomp_rule_add(ctx,0x00050000|errno.EPERM,nr,0)==0,'seccomp_rule_failed')
        require(lib.seccomp_load(ctx)==0,'seccomp_load_failed')
    finally:lib.seccomp_release(ctx)
    def audit(event,args):
        if event=='import' and args and str(args[0]).split('.')[0] in FORBIDDEN_IMPORTS:raise GateError('model_or_parser_import_forbidden')
        if event in ('subprocess.Popen','os.system','os.posix_spawn','os.fork'):raise GateError('child_execution_forbidden')
    sys.addaudithook(audit)
    return {'network_disabled':'kernel_seccomp','child_execution_disabled':True,'gpu_disabled':True,'max_numeric_threads':2}


def tree_bytes(root):
    return sum(p.stat().st_size for p in Path(root).rglob('*') if p.is_file())

class Guard:
    def __init__(self,private=PRIVATE,old_root=DATA/'exposure-fingerprints-v01',control=None,caps=None,prior_seconds=0):
        self.private=Path(private);self.old_root=Path(old_root);self.control=Path(control or self.private/'control.json');self.caps=dict(CAPS if caps is None else caps)
        self.started=time.monotonic();self.cpu_started=time.process_time();self.prior_seconds=prior_seconds;self.last_bytes=0;self.last_resource_check=-1.0;self.stage_output_budget=None;self.stage_initial_bytes=tree_bytes(self.private)
    def elapsed(self):return time.monotonic()-self.started
    def check(self,reserve=0):
        require(self.prior_seconds+self.elapsed()<=self.caps['wall_seconds'],'wall_time_limit')
        require(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024<=self.caps['rss_bytes'],'rss_limit')
        if reserve or time.monotonic()-self.last_resource_check>=1:
            old=max(self.caps['old_fingerprint_minimum_bytes'],tree_bytes(self.old_root));total=old+tree_bytes(self.private)
            self.last_bytes=total;self.last_resource_check=time.monotonic()
        require(self.last_bytes+reserve+4096<=self.caps['private_bytes'],'private_byte_limit')
        if self.stage_output_budget is not None:
            require(tree_bytes(self.private)-self.stage_initial_bytes+reserve+4096<=self.stage_output_budget,'stage_output_byte_limit')
        state=load_json(self.control);require(set(state)=={'state'} and state['state'] in ('run','pause','stop'),'invalid_control')
        if state['state']=='stop':raise GateError('operator_stop')
        while state['state']=='pause':
            time.sleep(0.1)
            require(self.prior_seconds+self.elapsed()<=self.caps['wall_seconds'],'wall_time_limit')
            state=load_json(self.control);require(set(state)=={'state'} and state['state'] in ('run','pause','stop'),'invalid_control')
            if state['state']=='stop':raise GateError('operator_stop')
    def append(self,path,value):
        data=canonical(value)+b'\n';self.check(len(data));p=Path(path)
        with p.open('ab') as f:f.write(data);f.flush();os.fsync(f.fileno())
        self.last_resource_check=-1;self.check()
    def write(self,path,value):
        data=canonical(value)+b'\n';self.check(len(data));require(not Path(path).exists(),'one_time_or_output_already_exists');write_new(path,value);self.last_resource_check=-1;self.check()
    def write_compressed(self,path,value):
        data=gzip.compress(canonical(value)+b'\n',compresslevel=6,mtime=0);self.check(len(data));require(not Path(path).exists(),'output_already_exists')
        with Path(path).open('xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
        self.last_resource_check=-1;self.check()


def source_code_bindings():
    required={'registry.py','runner.py','project_wikitext.py','projection_contract.py','preparse.py','source_risk_gate.py','compatibility.py'}
    require(required<={p.name for p in PUBLIC.glob('*.py')},'implementation_code_incomplete')
    return [binding(p) for p in sorted(PUBLIC.glob('*.py'))]


def indirect_bindings():
    paths=[Path('/workspace/shared/style-compiler/src/style_compiler/segmentation.py'),Path('/workspace/shared/style-compiler/research/linguistic/unicode_scripts.py'),Path('/lib/x86_64-linux-gnu/libseccomp.so.2').resolve()]
    # Bind imported stdlib Python/extension modules plus their source-only imports.
    for name in ('html.entities','dataclasses','zipfile','zlib','codecs','struct','stat','inspect'):
        importlib.import_module(name)
    for m in tuple(sys.modules.values()):
        raw=getattr(m,'__file__',None)
        if raw:
            p=Path(raw).resolve()
            if p.is_file() and str(p).startswith((str(Path(sys.base_prefix).resolve()),'/usr/local/lib/python','/usr/lib/python','/opt/pyvenv')) and 'site-packages' not in str(p):paths.append(p)
    ctypes.CDLL('libseccomp.so.2')
    for line in Path('/proc/self/maps').read_text().splitlines():
        fields=line.split()
        if len(fields)>=6 and fields[-1].startswith('/') and '.so' in fields[-1]:
            p=Path(fields[-1]).resolve()
            if p.is_file():paths.append(p)
    return [binding(p) for p in sorted(set(paths))]


def disk_preflight(freeze_path):
    freeze=load_json(freeze_path);rows=freeze['records'];private_bytes=tree_bytes(PRIVATE)
    old_bytes=max(CAPS['old_fingerprint_minimum_bytes'],tree_bytes(DATA/'exposure-fingerprints-v01'))
    used=old_bytes+private_bytes;remaining=CAPS['private_bytes']-used
    require(remaining>=CALIBRATION_OUTPUT_BUDGET+4096,'calibration_output_reservation_unavailable')
    return {'private_bytes_including_old':used,'remaining_global_bytes':remaining,'calibration_output_reservation_bytes':CALIBRATION_OUTPUT_BUDGET,'headroom_after_reservation_bytes':remaining-CALIBRATION_OUTPUT_BUDGET,'calibration_source_codepoints_sum':sum(r['source_codepoints'] for r in rows),'calibration_source_codepoints_max':max(r['source_codepoints'] for r in rows),'record_count':len(rows),'natural_bodies_read':False,'reservation_is_conservative_not_proof_of_actual_output_size':True}


def prepare_contract(stage):
    """Drafts a reviewable proposal. It cannot mint GO or an approval receipt."""
    require(stage in STAGES,'unknown_stage');require(stage=='calibration','candidates_execution_blocked_until_fingerprint_writer_integrated');freeze=PRIVATE/STAGES[stage][2]
    require(freeze.is_file(),'required_metadata_freeze_missing')
    reg=load_json(PRIVATE/'source-registry.private.json')
    result={'schema_version':'scale10-source-execution-contract/1','stage':stage,'status':'proposal_not_authorization',
      'fixed_private_root':str(PRIVATE),'registry':binding(PRIVATE/'source-registry.private.json'),'freeze':binding(freeze),
      'code_bindings':source_code_bindings(),'indirect_bindings':indirect_bindings(),'source_bindings':reg['input_bindings'],'metadata_database':reg['metadata_database'],
      'prior_budget_bindings':prior_budget_bindings(),'runtime':{'python_version':sys.version,'executable':binding(Path(sys.executable).resolve()),'unicode_version':unicodedata.unidata_version},
      'caps':CAPS,'stage_output_budget_bytes':CALIBRATION_OUTPUT_BUDGET,'disk_preflight':disk_preflight(freeze),'candidates_execution_blocked_until_fingerprint_writer_integrated':True,'output_policy':'private_per_record_public_aggregate_only','source_only':True,'network_disabled_required':True,
      'body_eligibility_before_freeze':False,'replacement_allowed':False,'one_time_marker':str(PRIVATE/(stage+'.ONE_TIME_STARTED.json')),
      'human_gold':False,'per_record_rights_review_required':True,'candidate_dependency_matcher_required_before_admission':True}
    p=PRIVATE/(stage+'.contract.proposal.json');write_new(p,result)
    return {'contract_sha256':filehash(p),'stage':stage,'status':'proposal_requires_independent_review_and_root_GO'}


def verify_contract(stage,contract_path,expected_contract_sha256,review_path,expected_review_sha256,go_path):
    require(stage in STAGES,'unknown_stage');require(stage=='calibration','candidates_execution_blocked_until_fingerprint_writer_integrated')
    require(repr(expected_contract_sha256)!=repr(None) and len(expected_contract_sha256)==64,'independent_contract_hash_required')
    require(filehash(contract_path)==expected_contract_sha256,'independent_contract_hash_mismatch')
    require(filehash(review_path)==expected_review_sha256,'independent_review_hash_mismatch')
    c=load_json(contract_path);review=load_json(review_path);go=load_json(go_path)
    require(c.get('schema_version')=='scale10-source-execution-contract/1' and c.get('stage')==stage,'contract_schema_or_stage')
    require(c.get('fixed_private_root')==str(PRIVATE),'output_root_change_forbidden')
    require(c.get('stage_output_budget_bytes')==CALIBRATION_OUTPUT_BUDGET and c.get('candidates_execution_blocked_until_fingerprint_writer_integrated') is True,'stage_budget_or_scope_changed')
    require(c.get('caps')==CAPS and c.get('source_only') is True and c.get('replacement_allowed') is False,'contract_scope_or_caps_changed')
    require(c.get('human_gold') is False and c.get('body_eligibility_before_freeze') is False,'claim_or_order_changed')
    require(c.get('one_time_marker')==str(PRIVATE/(stage+'.ONE_TIME_STARTED.json')),'one_time_marker_path_changed')
    require(review.get('decision')==STAGES[stage][1] and review.get('contract_sha256')==expected_contract_sha256,'source_review_not_approved')
    require(review.get('reviewer') and review.get('synthetic_tests_passed') is True,'source_review_missing')
    require(go.get('action')==STAGES[stage][0] and go.get('actor')=='root','explicit_stage_GO_required')
    require(go.get('contract_sha256')==expected_contract_sha256 and go.get('review_sha256')==expected_review_sha256,'GO_frozen_binding_mismatch')
    require(go.get('no_other_stages') is True,'GO_scope_required')
    require(c.get('prior_budget_bindings',[])==prior_budget_bindings(),'prior_budget_receipts_changed')
    require(c['runtime']['python_version']==sys.version and c['runtime']['unicode_version']==unicodedata.unidata_version,'runtime_changed')
    verify_binding(c['runtime']['executable'])
    require(c['code_bindings']==source_code_bindings(),'source_code_set_or_hash_changed')
    require(c.get('indirect_bindings'),'indirect_dependencies_missing')
    required_indirect={str(Path('/workspace/shared/style-compiler/src/style_compiler/segmentation.py')),str(Path('/workspace/shared/style-compiler/research/linguistic/unicode_scripts.py')),str(Path('/lib/x86_64-linux-gnu/libseccomp.so.2').resolve())}
    require(required_indirect<={b['path'] for b in c['indirect_bindings']},'indirect_dependencies_missing')
    frozen_dependencies={(b['path'],b['sha256'],b['bytes']) for b in c['indirect_bindings']}
    require({(b['path'],b['sha256'],b['bytes']) for b in indirect_bindings()}<=frozen_dependencies,'runtime_indirect_dependency_unbound')
    for b in c['source_bindings']+c['code_bindings']+c['indirect_bindings']+[c['registry'],c['freeze'],c['metadata_database']]:verify_binding(b)
    require(c['registry']['path']==str(PRIVATE/'source-registry.private.json'),'registry_path_mismatch')
    require(c['freeze']['path']==str(PRIVATE/STAGES[stage][2]),'freeze_path_mismatch')
    reg=load_json(c['registry']['path']);freeze=load_json(c['freeze']['path'])
    require(c['source_bindings']==reg['input_bindings'] and c['metadata_database']==reg['metadata_database'],'registry_indirect_binding_mismatch')
    require(freeze['records_sha256']==digest(freeze['records']) and freeze['replacement_allowed'] is False,'freeze_integrity')
    disk_preflight(PRIVATE/STAGES[stage][2])
    require(len({r['record_key'] for r in freeze['records']})==len(freeze['records']),'duplicate_frozen_record')
    if stage=='calibration':
        require(freeze['registry_sha256']==c['registry']['sha256'],'freeze_registry_binding')
        require(Counter(r['source_frame'] for r in freeze['records'])==Counter({s:32 for s in SOURCES}),'exact96_required')
        require(len({r['component_id'] for r in freeze['records']})==96,'calibration_components_not_unique')
    else:
        require(review.get('calibration_complete') is True,'candidate_calibration_gate')
        require(freeze.get('calibration_review_sha256')==review.get('calibration_review_sha256'),'candidate_calibration_review_binding')
        require(freeze.get('body_eligibility_applied') is False,'candidate_not_prefrozen')
        for b in freeze['source_rule_bindings']:verify_binding(b)
        limits={'discussion':3000,'news_prose':1500,'guide_prose':1500}
        require(all(n<=limits.get(s,-1) for s,n in Counter(r['source_frame'] for r in freeze['records']).items()),'candidate_cap')
    return c,freeze


def preread_exposure(guard,stage,records,contract_sha256):
    """Append and fsync all calibration exposure entries before any body stream."""
    if stage!='calibration':return
    p=guard.private/'exposure.private.jsonl'
    for r in records:
        guard.append(p,{'event':'pre_read_calibration_exposure','stage':stage,'contract_sha256':contract_sha256,'record_key':r['record_key'],'member_key':r['member_key'],'known_component_id':r['component_id'],'source_sha256':r['source_sha256'],'exclude_entire_final_component':True,'body_opened_yet':False})


def checked_text(row,text):
    require(isinstance(text,str),'source_text_not_string')
    require(len(text)==row['source_codepoints'] and hashlib.sha256(text.encode('utf-8')).hexdigest()==row['source_sha256'],'source_view_identity_mismatch')
    require(200<=len(text)<=20000,'frozen_source_size_outside_frame');return text


def stream_discussion(rows,guard):
    """Decode structural JSON, but inspect/process text only for frozen rows."""
    auditdir=Path('/workspace/shared/style-compiler/research/audits')
    for name,sha in READER_HASHES.items():require(filehash(auditdir/name)==sha,'reader_changed')
    sys.path.insert(0,str(auditdir))
    try:
        from wikiconv_annual_census import Archive,jsonl_records
        from wikiconv_zip_audit import normalize
    finally:sys.path.pop(0)
    spec=RAW_OBJECTS['discussion'];want={r['locator']['rownum']:r for r in rows};seen=set()
    archive=Archive(Path(spec['path']),spec['sha256'],spec['bytes'],spec['expanded_bytes'])
    try:
        def chunks():
            for block in archive.chunks('utterances.jsonl'):guard.check();yield block
        for rownum,offset,record in jsonl_records(chunks()):
            guard.check()
            if rownum not in want:continue
            row=want[rownum];loc=row['locator']
            if hasattr(guard,'on_source_attempt'):guard.on_source_attempt(row)
            if hasattr(guard,'on_source_read') and isinstance(record.get('text'),str):guard.on_source_read(row,record['text'])
            v=normalize(record,'top_level')
            require(rownum not in seen and offset==loc['byte_offset'] and v['id']==loc['id'] and v['conversation']==loc['conversation'] and v['header'] is False,'frozen_discussion_locator_mismatch')
            seen.add(rownum);yield row,checked_text(row,v['text'])
        require(set(archive.verified)=={'utterances.jsonl'},'unexpected_archive_member_read')
        require(seen==set(want),'frozen_discussion_records_missing')
    finally:archive.close()
    require(filehash(spec['path'])==spec['sha256'],'source_changed_during_read')


def stream_wiki(source,rows,guard):
    """SAX retains source text solely for frozen page/revision identities.

    Other bodies pass through the stream without eligibility, projection, role,
    copy-signature or model handling. DTD/external entities are rejected.
    """
    spec=RAW_OBJECTS[source];want={r['locator']['page_id']:r for r in rows};seen=set();ready=[]
    stack=[];page={};capture=[];text_parts=[];text_chars=0
    parser=xml.parsers.expat.ParserCreate()
    def denied(*args):raise GateError('XML_entities_or_DTD_forbidden')
    parser.StartDoctypeDeclHandler=denied;parser.EntityDeclHandler=denied;parser.ExternalEntityRefHandler=denied
    def start(name,attrs):
        nonlocal page,capture,text_parts,text_chars
        stack.append(name)
        if name=='page':guard.check();page={'redirect':False};text_parts=[];text_chars=0
        if stack[-2:]==['page','redirect']:page['redirect']=True
        if stack[-2:]==['revision','text'] and page.get('id') in want and hasattr(guard,'on_source_attempt'):guard.on_source_attempt(want[page['id']])
        capture=[]
    def chars(data):
        nonlocal text_chars
        if stack[-2:]==['revision','text']:
            if page.get('id') in want:
                text_chars+=len(data);require(text_chars<=20000,'selected_source_char_limit');text_parts.append(data)
        elif stack[-2:] in (['page','id'],['page','ns'],['revision','id'],['revision','timestamp']):
            capture.append(data);require(sum(map(len,capture))<256,'XML_metadata_limit')
    def end(name):
        nonlocal capture,text_parts
        if stack[-2:]==['revision','text'] and page.get('id') in want and hasattr(guard,'on_source_read'):
            guard.on_source_read(want[page['id']],''.join(text_parts))
        if stack[-2:]==['page','id']:page['id']=''.join(capture)
        elif stack[-2:]==['page','ns']:page['namespace']=''.join(capture)
        elif stack[-2:]==['revision','id']:page['revision_id']=''.join(capture)
        elif stack[-2:]==['revision','timestamp']:page['revision_timestamp']=''.join(capture)
        elif name=='page':
            guard.check();pid=page.get('id')
            if pid in want:
                row=want[pid];loc=row['locator'];require(pid not in seen,'duplicate_selected_page')
                require(page['namespace']=='0' and page['redirect'] is False and page['revision_id']==loc['revision_id'] and page['revision_timestamp']==loc['revision_timestamp'],'frozen_wiki_locator_mismatch')
                seen.add(pid);ready.append((row,checked_text(row,''.join(text_parts))));text_parts=[]
        require(stack and stack[-1]==name,'XML_stack');stack.pop();capture=[]
    parser.StartElementHandler=start;parser.CharacterDataHandler=chars;parser.EndElementHandler=end
    expanded=0
    with bz2.open(spec['path'],'rb') as f:
        while True:
            guard.check();chunk=f.read(65536)
            if not chunk:break
            expanded+=len(chunk);require(expanded<=spec['expanded_bytes'],'expanded_byte_limit');parser.Parse(chunk,False)
            while ready:yield ready.pop(0)
        parser.Parse(b'',True)
    while ready:yield ready.pop(0)
    require(expanded==spec['expanded_bytes'] and seen==set(want),'wiki_expanded_or_selected_count_mismatch')
    require(filehash(spec['path'])==spec['sha256'],'source_changed_during_read')


def prior_budget_bindings():
    pairs=[(PRIVATE/'old-projection-exclusion.ONE_TIME_STARTED.private.json',PRIVATE/'old-projection-exclusion.receipt.private.json'),(PRIVATE/'incremental-blog-exclusion-ONE_TIME_STARTED.private.json',PUBLIC/'incremental-blog-exclusion-coverage.aggregate.json')]
    for marker,receipt in pairs:require(not marker.exists() or receipt.exists(),'prior_source_stage_incomplete')
    paths=[PRIVATE/(stage+'.receipt.private.json') for stage in STAGES]+[pairs[0][1],pairs[1][1],PUBLIC/'metadata-freeze.aggregate.json']
    return [binding(p) for p in paths if p.is_file()]


def prior_wall_seconds():
    total=0.0
    for stage in tuple(STAGES)+('old-projection-exclusion',):
        p=PRIVATE/(stage+'.receipt.private.json')
        if p.exists():total+=load_json(p)['resources']['elapsed_seconds']
    incremental=PUBLIC/'incremental-blog-exclusion-coverage.aggregate.json'
    if incremental.exists():total+=load_json(incremental)['resources']['elapsed_seconds']
    metadata=PUBLIC/'metadata-freeze.aggregate.json'
    if metadata.exists():total+=load_json(metadata).get('elapsed_seconds',0)
    return total


def durable_read_event(guard,path,event):
    """Accounting after consumption must survive a stop/pause at this boundary.

    Reserved bookkeeping space is checked directly; this appends no source text.
    Terminal PRIVATE receipt also records the current identity if this write fails.
    """
    data=canonical(event)+b'\n'
    total=max(guard.caps['old_fingerprint_minimum_bytes'],tree_bytes(guard.old_root))+tree_bytes(guard.private)
    require(total+len(data)<=guard.caps['private_bytes'],'private_byte_limit_during_read_accounting')
    with Path(path).open('ab') as f:f.write(data);f.flush();os.fsync(f.fileno())
    guard.last_resource_check=-1


def execute(stage,contract,contract_sha,review,review_sha,go):
    require(stage=='calibration','candidates_execution_blocked_until_fingerprint_writer_integrated')
    sandbox=install_offline_sandbox()
    resource.setrlimit(resource.RLIMIT_AS,(CAPS['rss_bytes'],CAPS['rss_bytes']))
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    def timeout(*args):raise GateError('wall_time_limit')
    signal.signal(signal.SIGALRM,timeout);signal.setitimer(signal.ITIMER_REAL,CAPS['wall_seconds'])
    guard=Guard(private=PRIVATE,prior_seconds=prior_wall_seconds());guard.stage_output_budget=CALIBRATION_OUTPUT_BUDGET;guard.check()
    require(not (PRIVATE/(stage+'.ONE_TIME_STARTED.json')).exists(),'one_time_stage_already_consumed')
    c,freeze=verify_contract(stage,contract,contract_sha,review,review_sha,go)
    marker=PRIVATE/(stage+'.ONE_TIME_STARTED.json')
    guard.write(marker,{'stage':stage,'contract_sha256':contract_sha,'review_sha256':review_sha,'root_GO_sha256':filehash(go),'status':'consumed_no_implicit_retry'})
    counts=Counter();read_counts=Counter();attempt_counts=Counter();source_attempt_counts=Counter();read_keys=set();source_attempt_keys=set();current=None;result={'schema_version':'scale10-source-stage-receipt/1','stage':stage,'contract_sha256':contract_sha,'review_sha256':review_sha,'status':'partial','model_or_POS_or_target_calls':0,'human_gold':False,'source_admission_complete':False,'sandbox':sandbox}
    def on_source_attempt(row):
        nonlocal current
        current={'record_key':row['record_key'],'member_key':row['member_key'],'source_frame':row['source_frame'],'source_sha256':row['source_sha256'],'status':'selected_source_view_attempt'}
        if row['record_key'] not in source_attempt_keys:
            source_attempt_keys.add(row['record_key']);source_attempt_counts[row['source_frame']]+=1
            durable_read_event(guard,PRIVATE/(stage+'.source-read.private.jsonl'),dict(current,event='selected_source_view_attempt'))
    def on_source_read(row,text):
        nonlocal current
        on_source_attempt(row)
        current=dict(current,status='selected_source_view_read_before_projection')
        if row['record_key'] not in read_keys:
            read_keys.add(row['record_key']);read_counts[row['source_frame']]+=1
            durable_read_event(guard,PRIVATE/(stage+'.source-read.private.jsonl'),dict(current,event='selected_source_view_read',source_codepoints=len(text),observed_source_sha256=hashlib.sha256(text.encode()).hexdigest()))
    guard.on_source_attempt=on_source_attempt;guard.on_source_read=on_source_read
    output=PRIVATE/(stage+'.records')
    try:
        output.mkdir(exist_ok=False)
        preread_exposure(guard,stage,freeze['records'],contract_sha)
        # Imports occur only after all source/code/indirect hash checks and exposure.
        project=importlib.import_module('project_wikitext').project
        qualify=importlib.import_module('preparse').qualify
        gated_metadata=importlib.import_module('source_risk_gate').gated_metadata
        for source in SOURCES:
            rows=[r for r in freeze['records'] if r['source_frame']==source]
            if not rows:continue
            guard.append(PRIVATE/(stage+'.source-read.private.jsonl'),{'event':'source_stream_open_intent','source_frame':source,'source_object_sha256':RAW_OBJECTS[source]['sha256'],'selected_records':len(rows),'unselected_body_handling':'stream_discard_no_projection_or_signatures'})
            for row in rows:
                guard.append(PRIVATE/(stage+'.source-read.private.jsonl'),{'event':'selected_source_view_pre_read','source_frame':source,'record_key':row['record_key'],'member_key':row['member_key'],'source_sha256':row['source_sha256'],'automated_only':stage=='candidates'})
            stream=stream_discussion(rows,guard) if source=='discussion' else stream_wiki(source,rows,guard)
            for row,text in stream:
                current={'record_key':row['record_key'],'member_key':row['member_key'],'source_frame':source,'source_sha256':row['source_sha256'],'status':'source_view_yielded_before_projection'}
                on_source_read(row,text)
                guard.check();attempt_counts[source]+=1
                guard.append(PRIVATE/(stage+'.source-read.private.jsonl'),dict(current,event='source_projection_attempt'))
                metadata,source_risks=gated_metadata(text,row['metadata'])
                projection=project(text,source,metadata);preparse=qualify(projection,row['record_key'],text)
                record={'source_risks':source_risks,'metadata':row,'source_sha256':row['source_sha256'],'projection':projection,'preparse':preparse,'rights_review':'pending_independent_record_review','human_gold':False}
                if stage=='calibration':record['raw_source_text']=text
                guard.write_compressed(output/(digest(row['record_key'])+'.private.json.gz'),record)
                guard.append(PRIVATE/(stage+'.progress.private.jsonl'),{'event':'record_processed','record_key':row['record_key'],'source_frame':source,'source_sha256':row['source_sha256'],'output_sha256':filehash(output/(digest(row['record_key'])+'.private.json.gz'))})
                counts[source]+=1;current=None;guard.check()
        require(sum(counts.values())==len(freeze['records']),'selected_record_count_mismatch')
        for b in c['code_bindings']+c['indirect_bindings']+[c['freeze'],c['registry']]:verify_binding(b)
        result['status']='source_projection_complete_pending_independent_review_and_lineage'
    except BaseException as exc:
        result['status']='stopped_partial_no_retry';result['failure_code']=str(exc) if isinstance(exc,GateError) else type(exc).__name__
        raise
    finally:
        result['counts']=dict(counts);result['completed_counts']=dict(counts);result['actual_read_counts']=dict(read_counts);result['projection_attempt_counts']=dict(attempt_counts);result['source_attempt_counts']=dict(source_attempt_counts);result['resources']={'elapsed_seconds':guard.elapsed(),'cpu_seconds':time.process_time()-guard.cpu_started,'prior_stage_elapsed_seconds':guard.prior_seconds,'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,'private_bytes_including_old_fingerprints':max(CAPS['old_fingerprint_minimum_bytes'],tree_bytes(guard.old_root))+tree_bytes(PRIVATE),'caps':CAPS}
        # Emergency terminal receipt is bounded and retains failure after stop.
        private_result=dict(result)
        if current is not None:private_result['current_record_at_failure']=current
        data=canonical(private_result)+b'\n';p=PRIVATE/(stage+'.receipt.private.json')
        if not p.exists() and result['resources']['private_bytes_including_old_fingerprints']+len(data)<=CAPS['private_bytes']:
            with p.open('xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
        signal.setitimer(signal.ITIMER_REAL,0)
    # This contains only aggregates; no IDs, titles, locators or source text.
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    draft=sub.add_parser('prepare-contract');draft.add_argument('--stage',choices=STAGES,required=True)
    run=sub.add_parser('execute');run.add_argument('--stage',choices=STAGES,required=True)
    for flag in ('contract','contract-sha256','review','review-sha256','go'):run.add_argument('--'+flag,required=True)
    a=p.parse_args()
    try:
        result=prepare_contract(a.stage) if a.command=='prepare-contract' else execute(a.stage,a.contract,a.contract_sha256,a.review,a.review_sha256,a.go)
        print(json.dumps(result,sort_keys=True))
    except GateError as exc:print(json.dumps({'status':'blocked_or_stopped','code':str(exc)}));return 2
    except Exception as exc:print(json.dumps({'status':'blocked_or_stopped','code':type(exc).__name__}));return 2
    return 0
if __name__=='__main__':sys.exit(main())
