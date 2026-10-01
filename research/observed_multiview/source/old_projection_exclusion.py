"""One-time automatic old-source projection signatures, solely for exclusion.

No model records, targets, predictions, owner texts, network or new acquisition.
Enumerates the same licensed source views as the frozen raw exclusion package,
plus the separately authorized three diagnostic blogs. No plaintext persisted.
"""
from __future__ import annotations
import argparse,collections,hashlib,importlib,json,os,pathlib,resource,sqlite3,sys,time,signal,xml.etree.ElementTree as ET,zipfile
from registry import (ROOT,PRIVATE,PUBLIC,DATA,GateError,require,canonical,digest,filehash,binding,load_json,write_new,READER_HASHES)
from runner import Guard,install_offline_sandbox,tree_bytes,prior_budget_bindings,prior_wall_seconds,indirect_bindings
from matcher import SignatureWriter,normalize,norm_hash
from project_wikitext import exclusion_project,PROFILE
from projection_contract import validate_projection

OLDROOT=DATA/'exposure-fingerprints-v01'
OLDSHA='0ca3ca3eec71b88498ed70990804a7dc72d33dc736a0174edd3fdce5e258c3f5'
ALLOWSHA='c6a121bf83ad6908ff1306c35b148b11727a1644944a36ccb9f072ff037d0af3'
NEWALLOW=PRIVATE/'incremental-blog-exclusion-allowlist.private.json'
NEWALLOWSHA='a3bbaf1bb352eeca4c10a96c5b6eb9817e94dc2ea28d20055a603973884a492f'
PROJECTOR_SHA='387a8a82eb4024ac2c324b841f0ebbc090818f2d81a364113881b9ae0b954da0'
VALIDATOR_SHA='e508374e28bc2390da33aabd95bf6d89bac9c84181a8a6447d0407b7c88976a2'
PLAN=PRIVATE/'old-projection-exclusion.plan.private.json'
COVER=PRIVATE/'old-projection-exclusion.coverage.private.sqlite'
OUT=PRIVATE/'old-projection-exclusion.signatures.private.sqlite'
RECEIPT=PRIVATE/'old-projection-exclusion.receipt.private.json'
MARKER=PRIVATE/'old-projection-exclusion.ONE_TIME_STARTED.private.json'


def rodb(p):return sqlite3.connect(pathlib.Path(p).resolve().as_uri()+'?mode=ro&immutable=1',uri=True)
def view_key(source,member,role,objhash,rawhash,locator):return hashlib.sha256(canonical([source,member,role,objhash,rawhash,locator])).digest()
def rawsha(text):return hashlib.sha256(text.encode('utf-8')).hexdigest()
def wiki_member(page):return canonical(['wikimedia','zhwiki','page:'+str(int(page))]).decode()


def enumerate_old(allow,guard):
    """Reproduce only allowlisted old views; all locators bind the prior package."""
    audit=pathlib.Path('/workspace/shared/style-compiler/research/audits')
    for name,h in READER_HASHES.items():require(filehash(audit/name)==h,'old_reader_changed')
    sys.path.insert(0,str(audit))
    from wikiconv_annual_census import Archive,jsonl_records,views
    from wikiconv_zip_audit import metadata
    for item in allow['blogs']:
        guard.check();raw=pathlib.Path(item['path']).read_bytes();require(hashlib.sha256(raw).hexdigest()==item['sha256'] and len(raw)==item['bytes'],'old_blog_changed')
        member=canonical(['gitblog','zhengtianbao.github.io','post:'+item['original_path']]).decode()
        yield raw.decode('utf-8'),'third_party_blog39',member,'raw_markdown',item['sha256'],{'path':item['path'],'git_post':item['original_path']}
    for item in allow['pmc']:
        guard.check();raw=pathlib.Path(item['path']).read_bytes();require(hashlib.sha256(raw).hexdigest()==item['sha256'],'old_PMC_changed')
        lo,hi=item['article_range'];require(hashlib.sha256(raw[lo:hi]).hexdigest()==item['article_sha256'],'old_article_changed')
        require(b'<!DOCTYPE' not in raw and b'<!ENTITY' not in raw,'XML_entity_forbidden')
        tree=ET.fromstring(raw);articles=[e for e in tree.iter() if e.tag.split('}')[-1]=='article'];require(len(articles)==1,'old_article_count')
        member=canonical(['pmc','PMC',item['pmcid']]).decode();article=articles[0]
        yield raw.decode('utf-8'),'PMC6',member,'raw_OAI_XML',item['sha256'],{'path':item['path']}
        yield ''.join(article.itertext()),'PMC6',member,'article_itertext_unclassified',item['sha256'],{'path':item['path'],'article_sha256':item['article_sha256']}
        for i,e in enumerate(article.iter()):
            tag=e.tag.split('}')[-1]
            if tag in ('p','article-title','title'):yield ''.join(e.itertext()),'PMC6',member,'JATS_'+tag+'_text_not_training_prose',item['sha256'],{'path':item['path'],'element_preorder':i,'tag':tag}
    old=allow['wikiconv2002'];path=pathlib.Path(old['path']);guard.check();require(filehash(path)==old['sha256'] and path.stat().st_size==old['bytes'],'old2002_changed')
    with zipfile.ZipFile(path) as z:
        conv=json.loads(z.read('conversations.json'))
        for row,line in enumerate(z.read('utterances.jsonl').splitlines(),1):
            guard.check()
            if not line.strip():continue
            for k,v in enumerate(views(json.loads(line))):
                page=metadata(conv[v['conversation']])['page_id']
                yield v['text'],'WikiConv2002',wiki_member(page),v['role'],old['sha256'],{'row':row,'view_ordinal':k,'header':v['header'],'record_id':v['id']}
    s=allow['wikiconv2017'];ep=pathlib.Path(s['expected_view_file']);require(filehash(ep)==s['expected_view_file_sha256'],'expected_oldviews_changed')
    expected=collections.defaultdict(list)
    for e in load_json(ep):expected[e['rownum']].append(e)
    for group in expected.values():group.sort(key=lambda r:r['seq'])
    wanted=set(s['allowed_top_rows']);require(set(expected)==wanted,'old_toprows_mismatch');seen=set()
    archive=Archive(pathlib.Path(s['path']),s['sha256'],s['bytes'],s['expanded_bytes'])
    try:
        def chunks():
            for chunk in archive.chunks('utterances.jsonl'):guard.check();yield chunk
        for row,offset,record in jsonl_records(chunks()):
            if row%1000==0:guard.check()
            if row not in wanted:continue
            observed=list(views(record));require(len(observed)==len(expected[row]),'old_view_count_changed')
            for v,e in zip(observed,expected[row]):
                require(offset==e['byte_offset'] and v['role']==e['role'] and v['id']==e['id'] and v['conversation']==e['conversation'] and len(v['text'])==e['chars'] and rawsha(v['text'])==e['text_sha256'],'old_view_identity_changed')
                yield v['text'],'WikiConv2017',wiki_member(s['conversation_to_page'][v['conversation']]),v['role'],s['sha256'],{'row':row,'seq':e['seq'],'byte_offset':offset,'header':v['header'],'record_id':v['id'],'conversation_id':v['conversation'],'whole_parent_row_contaminated':True}
            seen.add(row)
        require(seen==wanted and set(archive.verified)=={'utterances.jsonl'},'old_annual_full_coverage_failed')
    finally:archive.close()


def prepare(focused_review_path,focused_review_sha256):
    require(filehash(OLDROOT/'fingerprints.private.sqlite')==OLDSHA,'old_signature_changed')
    require(filehash(OLDROOT/'source-allowlist.private.json')==ALLOWSHA,'old_allowlist_changed')
    require(filehash(NEWALLOW)==NEWALLOWSHA,'threeblog_allowlist_changed')
    require(filehash(PUBLIC/'project_wikitext.py')==PROJECTOR_SHA and filehash(PUBLIC/'projection_contract.py')==VALIDATOR_SHA,'projector_review_hash_changed')
    require(filehash(focused_review_path)==focused_review_sha256,'focused_review_changed')
    review=load_json(focused_review_path)
    require(review.get('decision')=='PASS_FOCUSED_PROJECTOR_KERNEL_ONLY' and review.get('reviewed_hashes',{}).get('project_wikitext.py')==PROJECTOR_SHA and review.get('reviewed_hashes',{}).get('projection_contract.py')==VALIDATOR_SHA,'focused_projection_review_not_approved')
    code=[binding(PUBLIC/n) for n in ('old_projection_exclusion.py','matcher.py','project_wikitext.py','projection_contract.py','registry.py','runner.py')]
    plan={'schema_version':'old-projection-exclusion-plan/1','purpose':'exclusion_only','source_scope':'existing_licensed_old324320_views_plus3_diagnostic_blogs','old_package_sha256':OLDSHA,'old_allowlist_sha256':ALLOWSHA,'new_three_allowlist_sha256':NEWALLOWSHA,'code_bindings':code,'indirect_bindings':indirect_bindings(),'prior_budget_bindings':prior_budget_bindings(),'prior_seconds':prior_wall_seconds(),'runtime_executable':binding(pathlib.Path(sys.executable).resolve()),'focused_projection_review':binding(focused_review_path),'projector_profile':PROFILE,'old_view_codepoints_cap':200000,'candidate_codepoints_cap_unchanged':20000,'model_parser_fit_target_calls_allowed':0,'human_or_author_truth_claim':False,'new_download_bytes':0,'owner_text_allowed':False,'total_private_bytes_cap':1073741824,'rss_cap':3221225472,'shared_wall_seconds_cap':5400,'rawtext_persisted':False}
    write_new(PLAN,plan);return {'plan_sha256':filehash(PLAN),'source_projection_not_run':True}


def execute(plan_sha256,root_go):
    require(root_go is True,'root_exclusion_projection_GO_required')
    require(filehash(PLAN)==plan_sha256,'independent_plan_hash_changed');plan=load_json(PLAN)
    require(plan['prior_budget_bindings']==prior_budget_bindings() and plan['prior_seconds']==prior_wall_seconds(),'prior_budget_history_changed')
    for b in plan['code_bindings']+plan['indirect_bindings']+plan['prior_budget_bindings']+[plan['focused_projection_review'],plan['runtime_executable']]:
        require(filehash(b['path'])==b['sha256'] and pathlib.Path(b['path']).stat().st_size==b['bytes'],'frozen_code_or_review_changed')
    require(filehash(OLDROOT/'fingerprints.private.sqlite')==OLDSHA and filehash(OLDROOT/'source-allowlist.private.json')==ALLOWSHA and filehash(NEWALLOW)==NEWALLOWSHA,'bound_source_metadata_changed')
    install_offline_sandbox();resource.setrlimit(resource.RLIMIT_AS,(3*1024**3,3*1024**3));resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    guard=Guard(prior_seconds=plan['prior_seconds']);guard.check();guard.write(MARKER,{'plan_sha256':plan_sha256,'purpose':'old_projected_exclusion_only','one_time_consumed':True})
    def timeout(*args):raise GateError('wall_time_limit')
    signal.signal(signal.SIGALRM,timeout);signal.setitimer(signal.ITIMER_REAL,max(.001,5400-guard.prior_seconds))
    old=rodb(OLDROOT/'fingerprints.private.sqlite');old.row_factory=sqlite3.Row
    text_index={r['raw_sha256']:dict(r) for r in old.execute('select id,raw_sha256,codepoints,normalized_sha256,normalized_codepoints from texts')}
    known_norm={r['normalized_sha256']:r['id'] for r in text_index.values() if r['normalized_codepoints']}
    known_blocks={r[0]:r[1] for r in old.execute('select normalized_sha256,text_id from blocks')}
    expected=collections.Counter()
    for r in old.execute('select b.source_id,b.member_key,b.source_view_role,b.source_object_sha256,b.locator_json,t.raw_sha256 from bindings b join texts t on t.id=b.text_id'):
        expected[view_key(r['source_id'],r['member_key'],r['source_view_role'],r['source_object_sha256'],r['raw_sha256'],json.loads(r['locator_json']))]+=1
    expected_count=sum(expected.values());require(expected_count==324320,'old_binding_count_changed')
    cover=sqlite3.connect(COVER);cover.executescript('PRAGMA journal_mode=DELETE;PRAGMA synchronous=FULL;CREATE TABLE control(key TEXT PRIMARY KEY,value TEXT);CREATE TABLE coverage(raw_sha256 TEXT PRIMARY KEY,old_text_id INTEGER,source_codepoints INTEGER,projection_sha256 TEXT,segments INTEGER,barriers INTEGER,quarantine INTEGER,new_signature_views INTEGER,raw_equivalent_views INTEGER,old_block_equivalent_views INTEGER);CREATE TABLE segments(old_raw_sha256 TEXT,segment_index INTEGER,projected_raw_sha256 TEXT,normalized_sha256 BLOB,normalized_codepoints INTEGER,coverage_kind TEXT,reference_text_id INTEGER,source_start INTEGER,source_end INTEGER,PRIMARY KEY(old_raw_sha256,segment_index));')
    writer=SignatureWriter(OUT,guard=lambda _:guard.check());seen=set();counts=collections.Counter();source_counts=collections.Counter();start=time.monotonic();result={'schema_version':'old-projected-exclusion-receipt/1','status':'partial','plan_sha256':plan_sha256,'purpose':'exclusion_only','G2_admitted':False,'source_bodies_written':False,'model_parser_target_prediction_calls':0}
    def process(text,source,member,role,objhash,locator,is_old=True):
        h=rawsha(text);source_counts[source]+=1;counts['source_views_seen']+=1
        if is_old:
            require(h in text_index and text_index[h]['codepoints']==len(text),'old_text_unknown')
            k=view_key(source,member,role,objhash,h,locator);require(expected[k]>0,'old_source_view_binding_mismatch');expected[k]-=1
        if h in seen:return
        guard.check();require(len(text)<=200000,'historical_view_size_cap')
        projection=exclusion_project(text);validate_projection(text,projection)
        counters=collections.Counter()
        for s in projection['segments']:
            norm=normalize(s['text']);nh=norm_hash(norm)
            if nh in known_norm:
                counters['raw_equivalent_views']+=1;kind='old_normalized_full';ref=known_norm[nh]
            elif len(norm)>=64 and nh in known_blocks:
                counters['old_block_equivalent_views']+=1;kind='old_normalized_long_block';ref=known_blocks[nh]
            elif not norm:
                counters['empty_projected_views']+=1;kind='empty';ref=None
            else:
                # Reserve a conservative upper bound BEFORE dictionary/SQLite IO.
                guard.check(min(len(norm),200000)*256+1048576)
                ref=writer.add(s['text'],source_id=source,member_key=member,exposure_role='prior_exposed_projected_exclusion_only',source_view_role='conservative_projected_segment',source_object_sha256=objhash,locator={'old_raw_sha256':h,'old_text_id':text_index[h]['id'] if is_old else None,'projection_sha256':projection['projection_sha256'],'projection_profile':PROFILE,'segment_index':s['index'],'source_spans':s['source_spans'],'old_source_view_role':role})
                counters['new_signature_views']+=1;kind='new_projected_signature'
            cover.execute('insert into segments values(?,?,?,?,?,?,?,?,?)',(h,s['index'],rawsha(s['text']),nh,len(norm),kind,ref,s['source_spans'][0][0],s['source_spans'][0][1]))
        cover.execute('insert into coverage values(?,?,?,?,?,?,?,?,?,?)',(h,text_index[h]['id'] if is_old else None,len(text),projection['projection_sha256'],len(projection['segments']),len(projection['barriers']),int(bool(projection['flags']['record_quarantine_reasons'])),counters['new_signature_views'],counters['raw_equivalent_views'],counters['old_block_equivalent_views']))
        seen.add(h);counts.update(counters);counts['unique_texts_projected']+=1;counts['projected_segments']+=len(projection['segments']);counts['record_quarantines']+=bool(projection['flags']['record_quarantine_reasons']);counts['zero_segment_views']+=not projection['segments']
        if len(seen)%500==0:cover.commit();guard.check()
    try:
        allow=load_json(OLDROOT/'source-allowlist.private.json')
        for view in enumerate_old(allow,guard):process(*view)
        require(sum(expected.values())==0 and set(text_index)<=seen,'old_projected_coverage_incomplete')
        for item in load_json(NEWALLOW)['sources']:
            guard.check();raw=pathlib.Path(item['local_path']).read_bytes();require(len(raw)==item['bytes'] and hashlib.sha256(raw).hexdigest()==item['sha256'],'newthree_source_changed')
            member=canonical(['gitblog',item['repository'],'post:'+item['path']]).decode()
            process(raw.decode('utf-8'),'new_pre2022_blog3',member,'raw_markdown',item['sha256'],{},False)
        artifact=writer.finish();cover.execute('CREATE INDEX segments_by_reference ON segments(coverage_kind,reference_text_id)');cover.executemany('insert into control values(?,?)',[('status','complete'),('projector_profile',PROFILE),('plan_sha256',plan_sha256),('old_package_sha256',OLDSHA),('old_projection_signature_package_sha256',artifact['sha256'])]);cover.commit();cover.close();old.close();guard.check()
        result.update(status='complete_projected_signature_package_pending_independent_review',old_expected_views=expected_count,old_missing_views=sum(expected.values()),old_unique_texts_expected=len(text_index),new_package=artifact,coverage_database=binding(COVER),cross_projection_coverage_certified=False,coverage_scope='all_known_source_views_processed_by_frozen_conservative_projection; omitted_role_regions_remain_only_in_raw_views; not semantic_copy_completeness',counts=dict(counts),source_counts=dict(source_counts))
    except BaseException as exc:
        try:cover.commit();cover.close();writer.close_failed();old.close()
        except Exception:pass
        result.update(status='stopped_partial_no_retry',failure_code=str(exc) if isinstance(exc,GateError) else type(exc).__name__,counts=dict(counts),source_counts=dict(source_counts));raise
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        result['resources']={'elapsed_seconds':guard.elapsed(),'prior_stage_elapsed_seconds':guard.prior_seconds,'cpu_seconds':time.process_time()-guard.cpu_started,'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,'total_private_bytes_including_old':max(566539146,tree_bytes(OLDROOT))+tree_bytes(PRIVATE)}
        data=canonical(result)+b'\n'
        if result['resources']['total_private_bytes_including_old']+len(data)<=1073741824:write_new(RECEIPT,result)
    public={k:v for k,v in result.items() if k not in {'new_package','coverage_database'}}
    public['signature_package_sha256']=artifact['sha256'];public['signature_package_bytes']=artifact['bytes'];public['coverage_database_sha256']=filehash(COVER)
    write_new(PUBLIC/'old-projected-exclusion.aggregate.json',public)
    return public

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='action',required=True)
    prep=sub.add_parser('prepare');prep.add_argument('--focused-review',required=True);prep.add_argument('--focused-review-sha256',required=True)
    run=sub.add_parser('execute');run.add_argument('--plan-sha256',required=True);run.add_argument('--root-exclusion-projection-go',action='store_true')
    a=p.parse_args();out=prepare(a.focused_review,a.focused_review_sha256) if a.action=='prepare' else execute(a.plan_sha256,a.root_exclusion_projection_go);print(json.dumps(out))
