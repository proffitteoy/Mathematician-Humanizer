"""Offline original sampler; no parser inference, fitting, network, or raw output.

Consume already authorized private WikiConv annual files and audited read-only
SQLite. Freeze source-record representatives of known page/copy components.
Only aggregate evidence belongs in a repository. Private manifest locators do not.
"""
from __future__ import annotations
import argparse, collections, hashlib, json, pathlib, resource, sqlite3, sys, time, unicodedata, zipfile, xml.etree.ElementTree as ET

SEED='style-observed-sequence-wikiconv-2017-v1-20261001'
ARCHIVE_HASH='635500ba887cef0c9d2bfaef03659de2974b5fd84b8a0cd90a9bd7bdef7f492a'
OLD_HASH='8c6b3f21adaad7b1d55eef3122593b418264c61b7bab9cd30c2f07cfbfce41ab'
RULE_HASH='60909d8ddfbef07edec7baa2a52d4980f9de269dc9994f50f8d5414881502a54'


def sha(data): return hashlib.sha256(data).hexdigest()
def canonical(x): return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def rank(purpose,key): return (sha((SEED+'|'+purpose+'|'+key).encode()),key)
def norm(text): return ''.join(c for c in unicodedata.normalize('NFKC',text) if not c.isspace())
def fulltext_copy_key(text):
    n=norm(text)
    return sha(n.encode()) if n else None

def han_ln_fraction(text,in_script):
    letters=[c for c in text if unicodedata.category(c)[0] in 'LN']
    return sum(in_script(c,'Han') for c in letters)/len(letters) if letters else 0.0

def shingles(text): return {text[i:i+5] for i in range(max(0,len(text)-4))}
def copy_edge(a,b):
    small=min(len(a),len(b))
    if small<40:return False
    common=len(a & b)
    return common>=40 and 5*common>=4*small

class DSU:
    def __init__(self,keys): self.parent={k:k for k in keys}
    def find(self,k):
        if k not in self.parent:self.parent[k]=k
        while self.parent[k]!=k:
            self.parent[k]=self.parent[self.parent[k]];k=self.parent[k]
        return k
    def union(self,a,b):
        a,b=self.find(a),self.find(b)
        if a!=b:self.parent[max(a,b)]=min(a,b)
    def key(self,k):return self.find(k)

def allocate(records,dsu,exposed_pages):
    excluded={dsu.key(p) for p in exposed_pages}
    groups=collections.defaultdict(list)
    for r in records:
        g=dsu.key(r['page_id'])
        if g not in excluded:groups[g].append(r)
    ordered=sorted(groups,key=lambda k:rank('component',k))
    sample=[]
    for i,g in enumerate(ordered[:192]):
        r=min(groups[g],key=lambda r:rank('record',r['id']))
        sample.append(dict(r,component_id=g,partition='train' if i<128 else 'development' if i<160 else 'test'))
    return sample,groups,excluded

def write_new(path,obj):
    blob=json.dumps(obj,ensure_ascii=False,indent=2).encode()+b'\n'
    with path.open('xb') as f:f.write(blob)
    assert path.read_bytes()==blob
    return sha(blob)

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--repo',type=pathlib.Path,required=True)
    ap.add_argument('--data',type=pathlib.Path,required=True)
    ap.add_argument('--private-out',type=pathlib.Path,required=True)
    ap.add_argument('--aggregate-out',type=pathlib.Path,required=True)
    args=ap.parse_args(); start=time.monotonic()
    root=args.repo.resolve();base=args.data.resolve();out=args.private_out.resolve()
    if root==out or root in out.parents:raise ValueError('private_output_inside_repo')
    out.mkdir(parents=True,exist_ok=True)
    for f in ['frozen-selection.private.json','candidate-frame.private.json']:
        if (out/f).exists():raise ValueError('refuse_overwrite')
    here=pathlib.Path(__file__).resolve().parent
    if sha((here/'selection-preregister.json').read_bytes())!=RULE_HASH:raise ValueError('rule_hash_changed')
    sys.path[:0]=[str(root),str(root/'src'),str(root/'research/audits')]
    from wikiconv_annual_census import Archive,jsonl_records,object_items,views
    from wikiconv_zip_audit import metadata
    from style_compiler.segmentation import segment
    from research.linguistic.unicode_scripts import in_script
    def guard():
        if time.monotonic()-start>900:raise RuntimeError('sampler_time_cap')
        if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss>1024*1024:raise RuntimeError('sampler_rss_cap')
    p=base/'wikiconv-chinese-2017'
    db=sqlite3.connect((p/'structural-frame.sqlite').as_uri()+'?mode=ro',uri=True)
    db.row_factory=sqlite3.Row
    control=dict(db.execute('SELECT key,value FROM control'))
    assert control['archive_sha256']==ARCHIVE_HASH and control['status']=='structural_census_complete'
    eligible={r[0] for r in db.execute('SELECT id FROM frame WHERE eligible=1')}
    old_groups={r[0] for r in db.execute('SELECT id FROM sample')}
    old_sample=json.loads((p/'frozen-sample-private.json').read_text())
    assert set(old_sample['group_keys'])==old_groups and len(old_groups)==24 and len(eligible)==3395
    archive=Archive(p/'full.corpus.zip',ARCHIVE_HASH,80074478,871024181)
    page={};page_type={}
    for k,r in object_items(archive.chunks('conversations.json')):
        m=metadata(r);assert isinstance(m['page_id'],str) and m['page_id']
        page[k]=m['page_id'];page_type[k]=m['page_type']
    dsu=DSU(set(page.values()))
    exposed={page[k] for k in old_groups}
    old_bytes=(base/'wikiconv-chinese-2002-pilot/full.corpus.zip').read_bytes()
    assert sha(old_bytes)==OLD_HASH
    old_texts=[]
    with zipfile.ZipFile(base/'wikiconv-chinese-2002-pilot/full.corpus.zip') as z:
        cm=json.loads(z.read('conversations.json'));old_pages={metadata(r)['page_id'] for r in cm.values()}
        exposed.update(old_pages)
        for line in z.read('utterances.jsonl').splitlines():
            if line.strip():
                for v in views(json.loads(line)):
                    if v['header']==0 and v['text'].strip():old_texts.append((metadata(cm[v['conversation']])['page_id'],v['text']))
    # Already inspected nonpersonal sources are excluded via the same copy graph.
    external_exposed=collections.Counter()
    br=json.loads((base/'non-dialogue-20261001/acquisition-receipt.private.json').read_text())
    assert br['status']=='complete' and len(br['items'])==39
    for item in br['items']:
        raw=pathlib.Path(item['raw_file']).read_bytes();assert sha(raw)==item['sha256']
        key='exposed-blog:'+item['sha256'];exposed.add(key);old_texts.append((key,raw.decode('utf-8')));external_exposed['blog']+=1
    pr=json.loads((base/'academic-pmc-20261001/fulltext-receipt.private.json').read_text())
    assert len(pr['results'])==6
    for item in pr['results']:
        raw=(base/'academic-pmc-20261001/fulltext'/f"{item['pmcid']}.xml").read_bytes()
        assert sha(raw)==item['oai_raw_sha256'] and b'<!DOCTYPE' not in raw and b'<!ENTITY' not in raw
        key='exposed-pmc:'+item['article_raw_sha256'];exposed.add(key)
        old_texts.append((key,''.join(ET.fromstring(raw).itertext())));external_exposed['pmc']+=1
    # Exact long-text families over all annual source views, including versions
    previous_hash=None;first_page=None;exact_rows=0;exact_cross_edges=0
    for r in db.execute('SELECT text_sha256,conversation FROM views WHERE header=0 AND chars>=200 ORDER BY text_sha256'):
        h,c=r
        if h!=previous_hash: previous_hash=h;first_page=page[c]
        elif page[c]!=first_page:dsu.union(first_page,page[c]);exact_cross_edges+=1
        exact_rows+=1
    want={r['rownum']:dict(r) for r in db.execute('SELECT v.* FROM views v JOIN frame f ON v.conversation=f.id WHERE f.eligible=1 AND v.role="top_level" AND v.header=0 AND v.chars BETWEEN 200 AND 20000')}
    candidates=[];copy_texts=list(old_texts);reasons=collections.Counter();frame_rows=0;prefix_exposed_pages=set()
    for n,offset,r in jsonl_records(archive.chunks('utterances.jsonl')):
        if n%1000==0:guard()
        is_exposed=n<=1000 or r['conversation_id'] in old_groups
        if is_exposed:
            pp=page[r['conversation_id']];exposed.add(pp)
            if n<=1000:prefix_exposed_pages.add(pp)
            for v in views(r):
                if v['header']==0 and v['text'].strip():copy_texts.append((pp,v['text']))
        if n not in want:continue
        v=next(views(r)); e=want[n];text=v['text'];frame_rows+=1
        assert e['id']==v['id'] and e['conversation']==v['conversation'] and e['byte_offset']==offset
        assert sha(text.encode())==e['text_sha256'] and len(text)==e['chars']
        units=segment(text)[1]
        if not 8<=len(units)<=64:reasons['unit_count_outside_8_64']+=1;continue
        if any(s.end-s.start>512 for s in units):reasons['unit_over512codepoints']+=1;continue
        if han_ln_fraction(text,in_script)<.5:reasons['han_script_fraction_under_half']+=1;continue
        pp=page[v['conversation']]
        candidates.append({'id':v['id'],'conversation_id':v['conversation'],'page_id':pp,'page_type':page_type[v['conversation']],
          'rownum':n,'byte_offset':offset,'role':'top_level','source_sha256':e['text_sha256'],'source_codepoints':len(text),
          'unit_count':len(units),'prefix_units_cap':min(32,len(units)),'candidate_pairs':min(32,len(units))-4,
          'source_unit_spans':[[s.start,s.end] for s in units]})
        copy_texts.append((pp,text))
    assert frame_rows==len(want) and 'utterances.jsonl' in archive.verified
    archive.close()
    # All inspected metadata is now fixed. These are copy/length design features,
    # not parser targets and never surfaced as individual held-out observations.
    unique={(p,sha(t.encode())):(p,t) for p,t in copy_texts}
    copy_texts=list(unique.values());full={};units_seen={};shingle_sets=[]
    normalized_edges=unit_edges=near_edges=0
    for pp,t in copy_texts:
        n=norm(t)
        if n:
            h=fulltext_copy_key(t)
            if h in full:dsu.union(pp,full[h]);normalized_edges+=1
            else:full[h]=pp
        for s in segment(t)[1]:
            u=norm(t[s.start:s.end])
            if len(u)>=64:
                h=sha(u.encode())
                if h in units_seen:dsu.union(pp,units_seen[h]);unit_edges+=1
                else:units_seen[h]=pp
        shingle_sets.append((pp,shingles(n)))
    pair_checks=0
    for i,(p1,s1) in enumerate(shingle_sets):
        guard()
        for p2,s2 in shingle_sets[:i]:
            if p1==p2:continue
            pair_checks+=1
            if copy_edge(s1,s2):dsu.union(p1,p2);near_edges+=1
    sample,groups,excluded=allocate(candidates,dsu,exposed)
    assert len({r['component_id'] for r in sample})==len(sample)
    assert not any(dsu.key(r['page_id']) in excluded for r in sample)
    # Verify every declared copy family and exposure member remains in one group.
    by_part={r['component_id']:r['partition'] for r in sample}
    components={k:sorted({r['conversation_id'] for r in v}) for k,v in groups.items()}
    common={'schema_version':'observed-sequence-frame/0.1','archive_sha256':ARCHIVE_HASH,'selection_rule_sha256':RULE_HASH,
      'exposure_addendum_sha256':sha((here/'exposure-addendum-v0.2.json').read_bytes()),'sampler_sha256':sha(pathlib.Path(__file__).read_bytes()),
      'producer_code_sha256':{x:sha((root/x).read_bytes()) for x in ['src/style_compiler/segmentation.py','research/linguistic/unicode_scripts.py','research/audits/wikiconv_annual_census.py','research/audits/wikiconv_zip_audit.py']},
      'parser_run':False,'fit_run':False,'raw_text_in_output':False}
    private={**common,'status':'frozen_design_manifest_not_training_admission','selected_records':sample,
      'exposure_pages':sorted(exposed),'excluded_component_ids':sorted(excluded),'all_page_component_map':{k:dsu.key(k) for k in page.values()},
      'prior_diagnostic_groups':sorted(old_groups),'available_candidate_components':components}
    private_hash=write_new(out/'frozen-selection.private.json',private)
    frame_hash=write_new(out/'candidate-frame.private.json',{**common,'records':candidates,'exclusion_counts':dict(reasons)})
    counts=collections.Counter(r['partition'] for r in sample)
    strata=collections.defaultdict(collections.Counter)
    pairs=collections.Counter();ns=collections.Counter()
    for r in sample:
        strata[r['partition']][r['page_type']]+=1;pairs[r['partition']]+=r['candidate_pairs'];ns[r['partition']]+=r['prefix_units_cap']
    agg={**common,'status':'selection_complete_pending_root_review' if len(sample)==192 else 'underfilled_stop_no_fit',
      'prior_exposure':{'old2017diagnostic_groups':len(old_groups),'external_exposed_sources':dict(external_exposed),'entire2002archive_pages':len(old_pages),'precautionary_first2017records':1000,'precautionary_prefix_distinct_pages':len(prefix_exposed_pages),'exposed_pages_union':len(exposed),'excluded_known_components':len(excluded),
       'unknown_arbitrary_prior_inspection_disproved':False},
      'frame':{'structural_conversations':len(eligible),'size_candidate_records':len(want),'sequence_candidate_records':len(candidates),'candidate_exclusions':dict(reasons),
       'components_before_exposure_removal':len({dsu.key(r['page_id']) for r in candidates}),'components_after_exposure_removal':len(groups),'candidate_records_excluded_by_exposure':sum(dsu.key(r['page_id']) in excluded for r in candidates)},
      'copy_audit':{'all_year_long_nonheader_view_rows':exact_rows,'all_year_exact_cross_page_edges':exact_cross_edges,'candidate_exposure_text_views_deduped_by_page_rawhash':len(copy_texts),
       'normalized_fulltext_edges':normalized_edges,'long_unit_edges':unit_edges,'near_copy_pair_checks':pair_checks,'near_copy_edges':near_edges,'scope':'All annual-file long exact views; normalized and near-copy edges restricted to candidates plus exposed texts; unobserved external lineage unresolved'},
      'selection':{'target_components':192,'actual_components':len(sample),'one_source_record_per_component':True,'partition_components':dict(counts),'partition_page_types':{k:dict(v) for k,v in strata.items()},
       'capped_observed_units':dict(ns),'preparse_candidate_pairs':dict(pairs),'boundaries_and_missing_parse_can_reduce_pairs':True,'new_test_target_values_computed':0},
      'private_manifest_sha256':private_hash,'private_candidate_frame_sha256':frame_hash,
      'resources':{'elapsed_seconds':round(time.monotonic()-start,3),'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'new_download_bytes':0,
       'streamed2017member_bytes':40800231+829880895,'private_output_bytes':sum(f.stat().st_size for f in out.iterdir() if f.is_file())},
      'no_individual_author_or_human_origin_admission':True,'comparison_eligible_promoted':False}
    assert agg['resources']['private_output_bytes']<20000000
    write_new(args.aggregate_out,agg)
    print(json.dumps({k:agg[k] for k in ['status','frame','selection','resources']},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
