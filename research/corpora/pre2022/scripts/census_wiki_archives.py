"""Structural-only census of authorized snapshots. No parser/model or admission."""
import bz2, collections, datetime, hashlib, json, pathlib, re, unicodedata, xml.etree.ElementTree as ET, argparse
from add_wiki_role_flags import apply_role_flags

ap=argparse.ArgumentParser();ap.add_argument('source_root',type=pathlib.Path);args=ap.parse_args()
BASE=args.source_root
receipts=json.loads((BASE/'private/wiki-acquisition-receipt.json').read_text())
all_records=[]
reports=[]
norm_groups=collections.defaultdict(list)
block_groups=collections.defaultdict(set)
for receipt in receipts['results']:
    source=receipt['source_id'];ns_counts=collections.Counter();stats=collections.Counter();categories=collections.Counter();templates=collections.Counter();times=[];editors=set();members=[]
    raw=BASE/'private/raw'/receipt['filename']
    with bz2.open(raw,'rb') as stream:
        for event,e in ET.iterparse(stream,events=('end',)):
            if e.tag.rsplit('}',1)[-1]!='page':continue
            ns_uri=e.tag.split('}')[0]+'}' if '}' in e.tag else ''
            q=lambda s:ns_uri+s
            text_of=lambda node,tag:node.findtext(q(tag))
            ns=text_of(e,'ns');ns_counts[ns]+=1
            title=text_of(e,'title') or '';pid=text_of(e,'id');revs=e.findall(q('revision'));stats['revisions_all_namespaces']+=len(revs)
            redirect=e.find(q('redirect')) is not None
            if len(revs)!=1:stats['pages_with_revision_count_not_one']+=1
            for rev in revs:
                tnode=rev.find(q('text'));text=tnode.text or '' if tnode is not None else ''
                stats['text_nodes_all_namespaces']+=int(tnode is not None)
                stats['nonempty_texts_all_namespaces']+=int(bool(text.strip()))
                if ns!='0':continue
                timestamp=text_of(rev,'timestamp');rid=text_of(rev,'id');times.append(timestamp or '')
                stats['main_revisions']+=1;stats['main_redirects']+=redirect;stats['main_nonredirects']+=not redirect
                stats['main_nonredirect_nonempty']+=bool(not redirect and text.strip())
                stats['main_text_utf8_bytes']+=len(text.encode());stats['main_text_codepoints']+=len(text)
                stats['main_revisions_missing_timestamp']+=not bool(timestamp)
                stats['main_revisions_on_or_after_2022']+=bool(timestamp and timestamp>='2022-01-01T00:00:00Z')
                contrib=rev.find(q('contributor'));cid=text_of(contrib,'id') if contrib is not None else None;user=text_of(contrib,'username') if contrib is not None else None
                ip=text_of(contrib,'ip') if contrib is not None else None
                editor_key=hashlib.sha256((source+'|'+(cid or user or ip or 'unknown')).encode()).hexdigest();editors.add(editor_key)
                bot_name_hint=bool(user and re.search(r'bot$|機器人|机器人',user,re.I));stats['main_latest_editor_bot_name_heuristic']+=bot_name_hint;stats['main_latest_editor_is_ip']+=bool(ip)
                cs=re.findall(r'\[\[\s*(?:Category|分类|分類)\s*:\s*([^\]|]+)',text,re.I)
                ts=re.findall(r'\{\{\s*([^{}|\n]+)',text)
                categories.update(cs);templates.update(x.strip() for x in ts)
                stats['main_with_category_markup']+=bool(cs);stats['main_with_template_markup']+=bool(ts)
                normalized=''.join(c for c in unicodedata.normalize('NFKC',text) if not c.isspace())
                normhash=hashlib.sha256(normalized.encode()).hexdigest()
                sourcekey=source+':'+str(pid)
                han=sum('\u4e00'<=c<='\u9fff' or '\u3400'<=c<='\u4dbf' for c in text)
                ln=sum(unicodedata.category(c)[0] in 'LN' for c in text)
                long_blocks=[b for b in re.split(r'\n\s*\n',text) if len(b)>=200]
                hashes=[]
                for b in long_blocks:
                    nb=''.join(c for c in unicodedata.normalize('NFKC',b) if not c.isspace())
                    h=hashlib.sha256(nb.encode()).hexdigest();hashes.append(h)
                    if not redirect:block_groups[h].add(sourcekey)
                rec=dict(source_id=source,page_id=pid,revision_id=rid,revision_timestamp=timestamp,title=title,namespace=ns,redirect=redirect,source_text_sha256=hashlib.sha256(text.encode()).hexdigest(),normalized_wikitext_sha256=normhash,source_codepoints=len(text),han_codepoints=han,letter_number_codepoints=ln,blankline_block_count=len(re.split(r'\n\s*\n',text)),long_block_hashes=hashes,categories=cs,template_names=list(dict.fromkeys(x.strip() for x in ts)),latest_editor_pseudokey=editor_key,latest_editor_bot_name_heuristic=bot_name_hint,authorship_role='latest_editor_only_not_original_author',assistance_status='unknown',origin_status='historical_source_not_verified_unassisted',model_admitted=False)
                members.append(rec)
                if not redirect and normalized:norm_groups[normhash].append(sourcekey)
                if not redirect and len(text)>=200:stats['main_nonredirect_wikitext_ge200chars']+=1
                if not redirect and len(text)>=200 and ln and han/ln>=.5:stats['main_nonredirect_wikitext_ge200chars_han_ln_ge_half']+=1
            e.clear()
    (BASE/'private'/f'{source}.page-manifest.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in members))
    all_records.extend(members)
    report=dict(source_id=source,namespace_counts=dict(ns_counts),counts=dict(stats),main_revision_timestamp_min=min(times),main_revision_timestamp_max=max(times),main_latest_editor_pseudokeys=len(editors),most_frequent_category_markup=categories.most_common(15),most_frequent_template_names=templates.most_common(15),license=receipt['text_license'],raw_archive_sha256=receipt['sha256'],compressed_bytes=receipt['compressed_bytes'],expanded_bytes=receipt['expanded_bytes'],parser_run=False,model_admitted=False,unit='one_page_revision_not_a_sentence_or_template_expansion')
    reports.append(report)
    print(source,json.dumps(report,ensure_ascii=False),flush=True)
dup=[v for v in norm_groups.values() if len(v)>1];blockdup=[v for v in block_groups.values() if len(v)>1]
aggregate=dict(schema_version='style-pre2022-wiki-census/1',reports=reports,exact_normalized_nonredirect_duplicate_groups=len(dup),nonredirect_pages_in_exact_normalized_duplicate_groups=sum(map(len,dup)),long_raw_blankline_block_shared_hash_groups=len(blockdup),pages_sharing_at_least_one_long_raw_blankline_block=len(set().union(*blockdup)) if blockdup else 0,limitations=['Wikitext structural census only. Templates are not expanded and markup has not been projected to author prose.','Category and template names are source labels, not validated genre/topic classifications.','Last editor and bot-name heuristics do not identify original authors, all bots, or human/unassisted provenance.','Exact NFKC whitespace-normalized duplicates and exact long raw blocks only; semantic and near-copy dependencies remain.','No comparison with old sealed text or targets. New full cross-source lineage audit is mandatory before any split.','Displayed source counts are not independent usable training records.'])
(BASE/'public/wiki-census.aggregate.json').write_text(json.dumps(aggregate,ensure_ascii=False,indent=2)+'\n')
(BASE/'private/wiki-exact-copy-groups.json').write_text(json.dumps(dict(exact_normalized_groups=dup,long_raw_block_groups=[sorted(x) for x in blockdup]),ensure_ascii=False,indent=2)+'\n')
print('DONE',len(all_records),len(dup),flush=True)

apply_role_flags(BASE/'private',BASE/'public/wiki-census.aggregate.json')
