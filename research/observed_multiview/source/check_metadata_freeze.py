"""Author metadata-only replay; no corpus bodies opened, no independent claim."""
from collections import Counter,defaultdict
import registry as r

def check():
    reg=r.load_json(r.PRIVATE/'source-registry.private.json');freeze=r.load_json(r.PRIVATE/'calibration96.freeze.private.json')
    r.verify_binding(reg['metadata_database']);r.require(freeze['registry_sha256']==r.filehash(r.PRIVATE/'source-registry.private.json'),'registry_binding')
    db=r.rodb(r.PRIVATE/'metadata.registry.sqlite');groups=defaultdict(list);excluded=set();members={}
    for member,component,contaminated in db.execute('select * from members'):
        r.validate_member(member);groups[component].append(member);members[member]=(component,contaminated)
        if contaminated:excluded.add(component)
    for component,group in groups.items():r.require(component==r.digest(sorted(group)),'component_hash')
    for a,b,kind in db.execute('select * from lineage'):r.require(members[a][0]==members[b][0],'known_hard_edge_split')
    rows=r.read_records(db);db.close()
    for row in rows:
        r.require(200<=row['source_codepoints']<=20000,'size_frame');r.require(row['component_id']==members[row['member_key']][0],'member_component')
        md=row['metadata']
        if row['source_frame']=='discussion':r.require(md['role']=='top_level' and md['header'] is False,'discussion_frame')
        else:r.require(md['namespace']=='0' and md['redirect'] is False,'wiki_frame')
    selected,available=r.choose_calibration(rows,excluded)
    r.require(selected==freeze['records'] and r.digest(selected)==freeze['records_sha256'],'calibration_replay_difference')
    s=r.load_json(r.SELECTION);old=set(s['excluded_component_ids'])|{v['component_id'] for v in s['selected_records']};oldgroups=defaultdict(set);oldcount=0
    for page,component in s['all_page_component_map'].items():
        member=r.wiki_member('wikiconv','zhwiki',page);c,exposed=members[member];oldgroups[component].add(c)
        if component in old:r.require(exposed==1,'old_exposure_lost');oldcount+=1
    r.require(all(len(g)==1 for g in oldgroups.values()),'old_ancestor_split');r.require(oldcount==5780,'old_page_count')
    result={'schema_version':'scale10-author-metadata-replay/1','status':'passed_metadata_only_not_independent_review','calibration_records_reproduced':96,'calibration_counts':dict(Counter(x['source_frame'] for x in selected)),'source_frame_counts':dict(Counter(x['source_frame'] for x in rows)),'canonical_component_hashes_recomputed':len(groups),'old_page_memberships_checked':len(s['all_page_component_map']),'old_excluded_pages_checked':oldcount,'cross_excluded_calibration_components':len({x['component_id'] for x in selected}&excluded),'raw_source_body_reads':0,'parser_target_or_fit_calls':0,'calibration_freeze_sha256':r.filehash(r.PRIVATE/'calibration96.freeze.private.json')}
    return result
if __name__=='__main__':
    import json
    result=check();r.write_new(r.PUBLIC/'metadata-freeze.author-readback.json',result);print(json.dumps(result,sort_keys=True))
