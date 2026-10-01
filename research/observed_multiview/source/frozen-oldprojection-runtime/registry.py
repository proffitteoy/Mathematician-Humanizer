"""Offline metadata registry and immutable pre-body calibration/candidate freezes.

No corpus body decoder exists in this module. Only audited metadata and compressed
object hashing are allowed. Receipt names never imply human truth or admission.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
import time
import unicodedata

ROOT = Path('/workspace/shared/style-scale10-source-v01')
PRIVATE = ROOT/'private'
PUBLIC = ROOT/'public'
DATA = Path('/workspace/shared/style-compiler-data')
CORPUS = Path('/workspace/shared/style-pre2022-corpora')
PLAN = Path('/workspace/shared/style-learning-pilot/scale10-plan-v03')
SEED = 'style-observed-multiview-scale10-v1-20261001'
SOURCES = ('discussion','news_prose','guide_prose')
CAPS = {'wall_seconds':5400,'rss_bytes':3*1024**3,'private_bytes':1024**3,'old_fingerprint_minimum_bytes':566539146}
SELECTION = DATA/'learning-pilot-20261001-v02/frozen-selection.private.json'
OLD_ALLOWLIST = DATA/'exposure-fingerprints-v01/source-allowlist.private.json'
OLD_FP = DATA/'exposure-fingerprints-v01/fingerprints.private.sqlite'
# These are immutable audit inputs, not values supplied by the object under test.
PINNED = {
 str(SELECTION):'ddbe04ae3a3a1d289fbb53e35872b2eb9df27407d92f6002066c992c1580b0b8',
 str(OLD_ALLOWLIST):'c6a121bf83ad6908ff1306c35b148b11727a1644944a36ccb9f072ff037d0af3',
 str(OLD_FP):'0ca3ca3eec71b88498ed70990804a7dc72d33dc736a0174edd3fdce5e258c3f5',
 str(DATA/'wikiconv-chinese-2017/structural-frame.sqlite'):'604efda77ad12fd82c16be4c54ce1c0fa421e778ae64a912159e9479c9c0ff69',
 str(CORPUS/'private/zhwikinews-20211020.page-manifest.jsonl'):'5ab7fba1eaead73a10ece408cf03fa450fa8901568a926c636ab858a1eab3253',
 str(CORPUS/'private/zhwikivoyage-20211020.page-manifest.jsonl'):'1afd26c7468569f09f8a4eeabed8bc35148a22a1b8bfb53cad083b58089dcfeb',
 str(CORPUS/'private/wiki-exact-copy-groups.json'):'6236d1512ac7e3944dda7b41c3cc24916f26135bdd3cb19bdda94997a372cf3c',
 str(CORPUS/'private/wiki-acquisition-receipt.json'):'772dc22180047585bb898e4520922400f752de2ce4cff4851c04cee646119932',
 str(CORPUS/'private/representative-receipt.json'):'5f1260d133331cffbb082003c8e86737cde463104715dee23a09249647d3736e',
 str(PLAN/'protocol.zh.md'):'3c059fcfefd0c286527064893876274d38eb86099216765d956ad463e2b46896',
 str(PLAN/'admission-spec.zh.md'):'6a09ffcd51e92f7041910ad622344cc1dc461e1c579975f7e0181ae3828a2bff',
 str(PLAN/'sample_metadata.py'):'2aabab330821a7daca9953dd4339ff46bc1cac618588b16596384b75de9a3c08',
 str(CORPUS/'public/FILE_HASHES.json'):'11aef0e63e7004638844fc92835dce9597170fbf4c17536820e9deffe79da60e',
}
RAW_OBJECTS = {
 'discussion': {'source_id':'WikiConv2017','project':'zhwiki','path':str(DATA/'wikiconv-chinese-2017/full.corpus.zip'),'sha256':'635500ba887cef0c9d2bfaef03659de2974b5fd84b8a0cd90a9bd7bdef7f492a','bytes':80074478,'expanded_bytes':871024181,'license':'CC-BY-SA source text; corpus metadata separately licensed','profile':'explicit-nonheader-top-level-200-20000'},
 'news_prose': {'source_id':'zhwikinews-20211020','project':'zhwikinews','path':str(CORPUS/'private/raw/zhwikinews-20211020-pages-articles.xml.bz2'),'sha256':'156623daa4e5bb59121db738e2271e709dcb70937d2b473072b1837be9ad1def','bytes':21498368,'expanded_bytes':125037224,'license':'CC-BY-2.5','license_revision_id':170522,'profile':'main-nonredirect-200-20000'},
 'guide_prose': {'source_id':'zhwikivoyage-20211020','project':'zhwikivoyage','path':str(CORPUS/'private/raw/zhwikivoyage-20211020-pages-articles.xml.bz2'),'sha256':'1372fc86b61e83e33f991c1e494bf9b24c29294ab1f95e77f51a155adff3cc7a','bytes':11103655,'expanded_bytes':48482416,'license':'CC-BY-SA-3.0','license_revision_id':160013,'profile':'main-nonredirect-200-20000'},
}
READER_HASHES = {'wikiconv_annual_census.py':'e5051bd239812935096a035daadb3350a63ca151c7acd24021fa6eb6e39710b5','wikiconv_zip_audit.py':'84ced8137313f6d81c54b4fa6c271ef7f65ff110dc3d395330ce9cf603997e73'}

class GateError(RuntimeError): pass

def require(ok, code):
    if not ok: raise GateError(code)

def canonical(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')

def digest(value): return hashlib.sha256(canonical(value)).hexdigest()
def rank(purpose,key): return digest([SEED,purpose,key]),canonical(key)

def filehash(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''): h.update(b)
    return h.hexdigest()

def binding(path):
    p=Path(path); require(p.is_file() and not p.is_symlink(),'regular_nonsymlink_required')
    return {'path':str(p.resolve()),'sha256':filehash(p),'bytes':p.stat().st_size}

def verify_binding(b):
    p=Path(b['path']);require(p.is_file() and not p.is_symlink(),'bound_file_missing_or_symlink')
    require(p.stat().st_size==b['bytes'] and filehash(p)==b['sha256'],'bound_file_changed')

def load_json(path):
    def pairs(ps):
        d={}
        for k,v in ps:
            require(k not in d,'duplicate_json_key');d[k]=v
        return d
    return json.loads(Path(path).read_text(encoding='utf-8'),object_pairs_hook=pairs)

def write_new(path,value):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('xb') as f:
        f.write(canonical(value)+b'\n');f.flush();os.fsync(f.fileno())

def member_key(origin,project,object_id):
    require(all(isinstance(s,str) and s for s in (origin,project,object_id)),'invalid_member')
    return canonical([origin,project,object_id]).decode()

def wiki_member(alias,project,page_id):
    require(alias in ('wikiconv','discussion','mediawiki','wikimedia','WikiConv2017','WikiConv2002'),'unknown_source_alias')
    require(project in ('zhwiki','zhwikinews','zhwikivoyage'),'unknown_wiki_project')
    require(isinstance(page_id,str) and re.fullmatch('[0-9]+',page_id),'invalid_page_id')
    return member_key('wikimedia',project,'page:'+str(int(page_id)))

def validate_member(k):
    try: p=json.loads(k)
    except Exception: raise GateError('invalid_member') from None
    require(isinstance(p,list) and len(p)==3 and member_key(*p)==k,'invalid_member')
    if p[0]=='wikimedia': require(wiki_member('wikimedia',p[1],p[2].removeprefix('page:'))==k,'noncanonical_wiki_member')
    return k

class DSU:
    def __init__(self): self.parent={};self.exposed=set();self.counts=Counter()
    def add(self,k): validate_member(k);self.parent.setdefault(k,k)
    def find(self,k):
        require(k in self.parent,'missing_member')
        while self.parent[k]!=k:
            self.parent[k]=self.parent[self.parent[k]];k=self.parent[k]
        return k
    def union(self,a,b,kind):
        require(kind in ('old_component','exact_normalized','long_raw_block','direct_section','known_reprint','known_translation','concrete_unresolved','common_version','copy_edge'),'unknown_lineage_kind')
        self.add(a);self.add(b);x,y=self.find(a),self.find(b);self.parent[max(x,y)]=min(x,y);self.counts[kind]+=1
    def expose(self,k): self.add(k);self.exposed.add(k)
    def freeze(self):
        groups=defaultdict(list)
        for k in sorted(self.parent):groups[self.find(k)].append(k)
        mapping={};excluded=set()
        for group in groups.values():
            c=digest(group)
            for k in group:mapping[k]=c
            if set(group)&self.exposed:excluded.add(c)
        return mapping,excluded

def choose_calibration(rows,excluded):
    reps={}
    for r in rows:
        if r['component_id'] in excluded:continue
        key=r['component_id']
        if key not in reps or rank('representative',r['record_key'])<rank('representative',reps[key]['record_key']):reps[key]=r
    chosen=[];counts={}
    for source in SOURCES:
        group=sorted((r for r in reps.values() if r['source_frame']==source),key=lambda r:rank('calibration',[source,r['component_id']]))
        counts[source]=len(group);require(len(group)>=32,'calibration_underfilled_metadata')
        chosen.extend(group[:32])
    require(len(chosen)==96 and len({r['component_id'] for r in chosen})==96,'calibration_duplicate_component')
    return chosen,counts

def check_final_calibration(calibration,member_mapping,excluded_components=()):
    counts={}
    for source in SOURCES:
        rows=[r for r in calibration if r['source_frame']==source]
        require(len(rows)==32,'calibration_frozen_count')
        require(all(r['member_key'] in member_mapping for r in rows),'calibration_member_missing')
        comps={member_mapping[r['member_key']] for r in rows}
        counts[source]=len(comps)
        require(len(comps)==32,'calibration_underfilled')
        require(not comps&set(excluded_components),'calibration_old_contamination')
    # Also reject one final component owned by different sources.
    require(len({member_mapping[r['member_key']] for r in calibration})==96,'calibration_underfilled')
    return counts

def rodb(path):
    db=sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True);db.execute('PRAGMA query_only=ON');return db

def build_metadata():
    """Run only after source-tool implementation authorization; never read bodies."""
    start=time.monotonic();PRIVATE.mkdir(parents=True,exist_ok=True);PUBLIC.mkdir(parents=True,exist_ok=True)
    targets=[PRIVATE/'metadata.registry.sqlite',PRIVATE/'source-registry.private.json',PRIVATE/'calibration96.freeze.private.json',PUBLIC/'metadata-freeze.aggregate.json']
    require(not any(p.exists() for p in targets),'metadata_freeze_exists_no_overwrite')
    bindings=[]
    for path,sha in PINNED.items():
        b=binding(path);require(b['sha256']==sha,'pinned_input_changed');bindings.append(b)
    for spec in RAW_OBJECTS.values():
        b=binding(spec['path']);require(b['sha256']==spec['sha256'] and b['bytes']==spec['bytes'],'raw_object_changed');bindings.append(b)
    for name,sha in READER_HASHES.items():
        b=binding(Path('/workspace/shared/style-compiler/research/audits')/name);require(b['sha256']==sha,'reader_changed');bindings.append(b)
    # Bind the reviewed rights/source evidence without reopening any page text.
    extras=[CORPUS/'public/historical-license-evidence.json',CORPUS/'public/catalogue.json',CORPUS/'public/wiki-census.aggregate.json',Path('/workspace/shared/style-pre2022-corpora-review/public/INDEPENDENT_REVIEW.zh.md'),Path('/workspace/shared/style-pre2022-corpora-review/public/CORRECTION_RECEIPT.json'),Path('/workspace/shared/style-scale10-plan-review/public/REVIEW_RECEIPT.json')]
    for p in extras:bindings.append(binding(p))
    public_manifest=load_json(CORPUS/'public/FILE_HASHES.json')
    for ent in public_manifest:
        b=binding(CORPUS/'public'/ent['file']);require(b['sha256']==ent['sha256'] and b['bytes']==ent['bytes'],'source_public_manifest_changed')
    selection=load_json(SELECTION);require(selection['raw_text_in_output'] is False,'old_selection_contains_text')
    prior=set(selection['excluded_component_ids'])|{r['component_id'] for r in selection['selected_records']}
    require(len(selection['selected_records'])==192 and len(selection['excluded_component_ids'])==475 and len(prior)==667,'old_exclusion_counts')
    dsu=DSU();oldgroups=defaultdict(list)
    for page,c in selection['all_page_component_map'].items():
        m=wiki_member('wikiconv','zhwiki',page);dsu.add(m);oldgroups[c].append(m)
        if c in prior:dsu.expose(m)
    for c,group in oldgroups.items():
        for m in group[1:]:dsu.union(group[0],m,'old_component')
    require(len(dsu.exposed)==5780,'old_excluded_pages_count')
    oldfp=rodb(OLD_FP)
    require(dict(oldfp.execute('select key,value from control'))['status']=='complete','old_fingerprint_incomplete')
    oldmembers={r[0] for r in oldfp.execute('select distinct member_key from bindings')};oldfp.close()
    for m in oldmembers:dsu.expose(m)
    diagnostics=load_json(CORPUS/'private/representative-receipt.json')
    for r in diagnostics:dsu.expose(member_key('gitblog',r['repository'],'post:'+r['path']))
    allow=load_json(OLD_ALLOWLIST);conv=allow['wikiconv2017']['conversation_to_page']
    require(set(allow['wikiconv2017']['excluded_old_components'])==prior,'old_allowlist_components_mismatch')
    # The metadata registry intentionally keeps no utterance/page text.
    db=sqlite3.connect(targets[0]);db.execute('PRAGMA journal_mode=DELETE')
    db.executescript('''CREATE TABLE records(record_key TEXT PRIMARY KEY,source_frame TEXT NOT NULL,member_key TEXT NOT NULL,component_id TEXT,source_sha256 TEXT NOT NULL,source_codepoints INTEGER NOT NULL,locator_json TEXT NOT NULL,metadata_json TEXT NOT NULL);
    CREATE TABLE members(member_key TEXT PRIMARY KEY,component_id TEXT NOT NULL,excluded INTEGER NOT NULL);
    CREATE TABLE lineage(a TEXT NOT NULL,b TEXT NOT NULL,kind TEXT NOT NULL);
    CREATE TABLE control(key TEXT PRIMARY KEY,value TEXT NOT NULL);''')
    source_counts=Counter();meta=rodb(DATA/'wikiconv-chinese-2017/structural-frame.sqlite');meta.row_factory=sqlite3.Row
    require(dict(meta.execute('select key,value from control'))['status']=='structural_census_complete','structural_metadata_incomplete')
    for r in meta.execute("select seq,rownum,byte_offset,id,conversation,chars,text_sha256 from views where role='top_level' and header=0 and chars between 200 and 20000"):
        require(r['conversation'] in conv,'conversation_page_missing')
        page=conv[r['conversation']];member=wiki_member('discussion','zhwiki',page);require(member in dsu.parent,'old_page_membership_missing')
        key=canonical(['WikiConv2017','top_level',r['seq'],r['id']]).decode()
        loc={'rownum':r['rownum'],'byte_offset':r['byte_offset'],'seq':r['seq'],'id':r['id'],'conversation':r['conversation'],'page_id':page}
        md={'role':'top_level','header':False,'rights_review':'per_record_pending','authorship_role':'speaker_not_original_author','assistance_status':'unknown'}
        db.execute('insert into records values(?,?,?,NULL,?,?,?,?)',(key,'discussion',member,r['text_sha256'],r['chars'],canonical(loc).decode(),canonical(md).decode()));source_counts['discussion']+=1
    meta.close();require(source_counts['discussion']==117266,'discussion_metadata_capacity_changed')
    titles={};wiki_rows=[]
    for source in ('news_prose','guide_prose'):
        spec=RAW_OBJECTS[source]
        with (CORPUS/'private'/f"{spec['source_id']}.page-manifest.jsonl").open() as f:
            for line in f:
                r=json.loads(line);member=wiki_member('mediawiki',spec['project'],r['page_id']);dsu.add(member)
                titles[(spec['project'],r['title'])]=member
                # Concrete guide parent/subpage relation is a hard lineage cue;
                # generic regions and categories are NOT hard union labels.
                if source=='guide_prose' and '/' in r['title']:wiki_rows.append((spec['project'],r['title'],member))
                if r['namespace']!='0' or r['redirect'] or not 200<=r['source_codepoints']<=20000:continue
                key=canonical(['wikimedia',spec['project'],'page:'+str(int(r['page_id'])),'revision:'+str(int(r['revision_id']))]).decode()
                loc={k:r[k] for k in ('page_id','revision_id','revision_timestamp')}
                md={'namespace':r['namespace'],'redirect':r['redirect'],'rights_review':'per_record_pending','authorship_role':r['authorship_role'],'assistance_status':r['assistance_status'],'title':r['title'],'categories':r.get('categories',[]),'template_names':r.get('template_names',[]),'broad_categories_are_sensitivity_only':True}
                db.execute('insert into records values(?,?,?,NULL,?,?,?,?)',(key,source,member,r['source_text_sha256'],r['source_codepoints'],canonical(loc).decode(),canonical(md).decode()));source_counts[source]+=1
    for project,title,member in wiki_rows:
        parent=titles.get((project,title.rsplit('/',1)[0]))
        if parent:
            dsu.union(parent,member,'direct_section');db.execute('insert into lineage values(?,?,?)',(parent,member,'direct_section'))
    groups=load_json(CORPUS/'private/wiki-exact-copy-groups.json')
    for name,kind in [('exact_normalized_groups','exact_normalized'),('long_raw_block_groups','long_raw_block')]:
        for group in groups[name]:
            keys=[]
            for val in group:
                source,page=val.rsplit(':',1);project=source.split('-')[0];k=wiki_member('mediawiki',project,page);require(k in dsu.parent,'exact_group_member_missing');keys.append(k)
            for k in keys[1:]:dsu.union(keys[0],k,kind);db.execute('insert into lineage values(?,?,?)',(keys[0],k,kind))
    mapping,excluded=dsu.freeze()
    db.executemany('insert into members values(?,?,?)',((m,c,int(c in excluded)) for m,c in sorted(mapping.items())))
    db.execute('update records set component_id=(select m.component_id from members m where m.member_key=records.member_key)')
    db.execute('create index records_component on records(component_id)')
    db.execute('create index records_source on records(source_frame)')
    db.execute("insert into control values('status','metadata_only_frozen')");db.commit()
    rows=read_records(db);calibration,available=choose_calibration(rows,excluded)
    db.close()
    registry={'schema_version':'scale10-source-registry/1','status':'metadata_only_not_source_admitted','source_objects':RAW_OBJECTS,'input_bindings':bindings,'metadata_database':binding(targets[0]),'unicode_version':unicodedata.unidata_version,'canonical_origin_aliases':{'wikiconv':'wikimedia','discussion':'wikimedia','mediawiki':'wikimedia','WikiConv2017':'wikimedia','WikiConv2002':'wikimedia'},'source_text_read':False,'no_human_truth_claim':True,'reader_hashes':READER_HASHES,'old_components':667,'old_excluded_pages':5780,'old_fingerprint_member_count':len(oldmembers),'diagnostic_blog_members':3,'lineage_kind_counts':dict(dsu.counts),'unknown_semantic_lineage':'not_resolved_by_metadata; mandatory source-stage review','caps':CAPS}
    write_new(targets[1],registry)
    freeze={'schema_version':'scale10-calibration-freeze/1','seed':SEED,'status':'frozen_before_body_read_not_executed','registry_sha256':filehash(targets[1]),'metadata_database_sha256':filehash(targets[0]),'selection_rule':'known component global hash-first representative, then rank(calibration,[source_frame,component_id]) per source32','records':calibration,'records_sha256':digest(calibration),'replacement_allowed':False,'raw_text_read':False,'human_gold':False}
    write_new(targets[2],freeze)
    aggregate={'schema_version':'scale10-metadata-freeze-aggregate/1','status':'exact96_frozen_before_body_read','source_counts':dict(source_counts),'available_known_components_after_exclusion':available,'calibration_counts':{s:32 for s in SOURCES},'calibration_records':96,'canonical_members':len(mapping),'known_components':len(set(mapping.values())),'contaminated_components':len(excluded),'old_selected_plus_exposed_components':667,'old_excluded_page_members':5780,'lineage_kind_counts':dict(dsu.counts),'registry_sha256':filehash(targets[1]),'metadata_database_sha256':filehash(targets[0]),'calibration_freeze_sha256':filehash(targets[2]),'registry_code_sha256':filehash(Path(__file__)),'raw_source_body_read':False,'candidate_freeze_created':False,'new_parser_or_fit_run':False,'no_human_truth_claim':True,'elapsed_seconds':round(time.monotonic()-start,3)}
    write_new(targets[3],aggregate);return aggregate

def read_records(db):
    rows=[]
    for key,source,member,component,sha,chars,loc,md in db.execute('select * from records order by record_key'):
        rows.append({'record_key':key,'source_frame':source,'member_key':member,'component_id':component,'source_sha256':sha,'source_codepoints':chars,'locator':json.loads(loc),'metadata':json.loads(md)})
    return rows

def verify_final_graph(graph,db):
    """Independently enforce ancestry, canonical component IDs and contamination."""
    mapping=graph['member_to_component'];require(isinstance(mapping,dict),'final_graph_schema')
    groups=defaultdict(list)
    for member,component in mapping.items():
        validate_member(member);groups[component].append(member)
    for component,members in groups.items():require(component==digest(sorted(members)),'noncanonical_final_component')
    old_groups=defaultdict(set);old_contaminated=set()
    for member,prior_component,was_exposed in db.execute('select * from members'):
        require(member in mapping,'final_graph_old_member_missing')
        old_groups[prior_component].add(mapping[member])
        if was_exposed:old_contaminated.add(mapping[member])
    require(all(len(group)==1 for group in old_groups.values()),'final_graph_split_known_ancestor')
    excluded=set(graph['contaminated_components'])
    require(old_contaminated<=excluded,'final_graph_lost_old_contamination')
    require(excluded<=set(groups),'final_graph_unknown_exclusion')
    return mapping,excluded,old_contaminated


def freeze_candidates(review_path,review_sha256,final_components_path,final_components_sha256):
    """No body reads. Caller supplies independently reviewed completed calibration.

    Calibration review must bind exact frozen records, final member graph and
    frozen role/rule code. Newly merged/contaminated components never get replaced.
    """
    out=PRIVATE/'candidate6000.freeze.private.json';require(not out.exists(),'candidate_freeze_exists_no_retry')
    require(filehash(review_path)==review_sha256,'calibration_review_hash_mismatch')
    require(filehash(final_components_path)==final_components_sha256,'final_components_hash_mismatch')
    review=load_json(review_path);cal=load_json(PRIVATE/'calibration96.freeze.private.json')
    require(review.get('decision')=='CALIBRATION_COMPLETE_SOURCE_RULES_APPROVED','reviewed_calibration_not_complete')
    require(review.get('calibration_freeze_sha256')==filehash(PRIVATE/'calibration96.freeze.private.json'),'calibration_binding_mismatch')
    require(review.get('final_components_sha256')==final_components_sha256,'final_graph_binding_mismatch')
    require(review.get('unresolved_rights')==0 and review.get('unresolved_role_or_mapping')==0,'calibration_unresolved')
    require(review.get('independent_assistant_reviews')==2 and review.get('human_gold') is False,'review_contract_incomplete')
    require(review.get('source_rule_bindings'),'source_rules_not_frozen')
    for b in review['source_rule_bindings']:verify_binding(b)
    graph=load_json(final_components_path)
    reg=load_json(PRIVATE/'source-registry.private.json');verify_binding(reg['metadata_database'])
    db=rodb(PRIVATE/'metadata.registry.sqlite');mapping,excluded,old_contaminated=verify_final_graph(graph,db);rows=read_records(db);db.close()
    check_final_calibration(cal['records'],mapping,old_contaminated)
    excluded|={mapping[r['member_key']] for r in cal['records']}
    require(all(r['member_key'] in mapping for r in rows),'candidate_graph_members_missing')
    selected=[];counts={}
    for source,cap in [('discussion',3000),('news_prose',1500),('guide_prose',1500)]:
        frame=[dict(r,component_id=mapping[r['member_key']]) for r in rows if r['source_frame']==source and mapping[r['member_key']] not in excluded]
        frame.sort(key=lambda r:rank('candidate-frame',[source,r['record_key']]));selected.extend(frame[:cap]);counts[source]=min(cap,len(frame))
    result={'schema_version':'scale10-candidate-freeze/1','status':'frozen_before_candidate_body_eligibility','records':selected,'records_sha256':digest(selected),'counts':counts,'calibration_review_sha256':review_sha256,'final_components_sha256':final_components_sha256,'source_rule_bindings':review['source_rule_bindings'],'replacement_allowed':False,'body_eligibility_applied':False}
    write_new(out,result);return {'candidate_counts':counts,'candidate_freeze_sha256':filehash(out)}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--freeze-metadata',action='store_true');a=p.parse_args()
    require(a.freeze_metadata,'metadata_action_required');print(json.dumps(build_metadata(),sort_keys=True))
if __name__=='__main__':main()
