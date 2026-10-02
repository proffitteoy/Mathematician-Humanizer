import collections,datetime,hashlib,json,pathlib,statistics
from lxml import html
from acquire_sources import ROOT
from inspect_blocks import source_blocks
R=ROOT/'public'
def rows(p):return [json.loads(x) for x in p.read_text().splitlines()]
g=rows(R/'ARTICLE_CATALOG.jsonl'); e=rows(R/'EINFO_ARTICLE_CATALOG.jsonl'); req=rows(R/'REQUEST_RECEIPTS.jsonl');s=json.loads((ROOT/'private/structural_receipts.json').read_text());es=rows(ROOT/'private/einfo_document_receipts.jsonl')
checks={}
checks['selected_guava_identities_complete']={x['url'] for x in g}=={x['url'] for x in json.loads((R/'SELECTION_MANIFEST.json').read_text())}
checks['selected_einfo_identities_complete']={x['url'] for x in e}=={x['url'] for x in json.loads((R/'EINFO_SELECTION_MANIFEST.json').read_text())}
checks['unique_selected_urls']=len({x['url'] for x in g+e})==47
checks['all_original_response_hashes_match']=all(hashlib.sha256((ROOT/x['private_path']).read_bytes()).hexdigest()==x['sha256'] and (ROOT/x['private_path']).stat().st_size==x['response_bytes'] for x in req if x['status']==200)
checks['guava_dates_agree']=all(x['date_matches'] and x['article_date_claim']<'2022-01-01' for x in g)
checks['guava_all_article_license_notice']=all(x['article_level_license_notice_present'] and any('/by-nc-nd/3.0/tw/' in a for a in x['license_links']) for x in g)
sole=collections.Counter(x['author'] for x in g if x['sole_author_eligible'])
checks['ten_new_guava_authors_four_sole_bylines_each']=len(sole)==10 and set(sole.values())=={4}
checks['one_coauthored_row_kept_separate']=sum(not x['sole_author_eligible'] for x in g)==1
checks['einfo_two_reporters_three_pieces_each']=collections.Counter(x['author'] for x in e)=={'陳文姿':3,'賴品瑀':3} and all(x['byline_matches'] for x in e)
checks['einfo_all_pre2022_claims']=all(x['pre2022_date_claim'] for x in e)
checks['all_body_receipts_present']=len(s)==41 and len(es)==6
checks['all_body_nonempty_han_1000']=all(x['whole_body_han_codepoints']>=1000 for x in s+es)
checks['direct_http_payload_plus_unlogged_initial_probe_under_20mib']=sum(x['response_bytes'] for x in req)+81156<20971520
checks['articles_under_200']=len(g+e)<200
# Fixtures test structural handling only; these are not corpus prose.
fixture=html.fromstring('<div><p>甲</p><div>乙</div><blockquote><p>丙</p></blockquote><figure><figcaption>丁</figcaption></figure><h2>戊</h2><div><p>己</p></div></div>')
b=source_blocks(fixture)
checks['block_fixture_order_no_duplicates']=[x['text'] for x in b]==list('甲乙丙丁戊己')
checks['block_fixture_quote_and_caption_roles']=[x['role'] for x in b][2:4]==['marked_quotation','caption']
checks['div_prose_case_recovered']=next(x['whole_body_han_codepoints'] for x in s if x['url'].endswith('/6886'))==4558
article_urls={x['url'] for x in g+e};article_req=[x for x in req if x['url'] in article_urls and x['status']==200]
bygen=collections.Counter(x['genre'] for x in g+e)
agg={'article_count':47,'new_repeated_named_author_trajectories':12,'guava_articles':41,'guava_sole_author_articles':40,'guava_coauthored_articles':1,'einfo_articles':6,'guava_sole_bylines_per_author':dict(sole),'einfo_bylines_per_author':dict(collections.Counter(x['author'] for x in e)),'current_page_claimed_publication_range':[min(x['article_date_claim'] for x in g+e),max(x['article_date_claim'] for x in g+e)],'verified_pre2022_immutable_snapshots':0,'genre_counts_provisional':dict(bygen),'body_text_codepoints_including_quotes_captions_references':sum(x['whole_body_text_codepoints'] for x in s+es),'body_han_codepoints_including_quotes_captions_references':sum(x['whole_body_han_codepoints'] for x in s+es),'guava_han_min_median_max':[min(x['whole_body_han_codepoints'] for x in s),statistics.median(x['whole_body_han_codepoints'] for x in s),max(x['whole_body_han_codepoints'] for x in s)],'einfo_han_min_median_max':[min(x['whole_body_han_codepoints'] for x in es),statistics.median(x['whole_body_han_codepoints'] for x in es),max(x['whole_body_han_codepoints'] for x in es)],'nonempty_source_structural_blocks':sum(x['nonempty_leaf_block_elements'] for x in s)+sum(x['nonempty_source_blocks'] for x in es),'guava_structural_block_min_median_max':[min(x['nonempty_leaf_block_elements'] for x in s),statistics.median(x['nonempty_leaf_block_elements'] for x in s),max(x['nonempty_leaf_block_elements'] for x in s)],'verified_article_html_bytes':sum(x['response_bytes'] for x in article_req),'receipt_recorded_requests':len(req),'receipt_recorded_response_bytes':sum(x['response_bytes'] for x in req),'initial_unlogged_probe_allowance_bytes':81156,'accounted_direct_payload_bytes':sum(x['response_bytes'] for x in req)+81156,'single_timeout_retried_once':True,'rights_filtered_source':'twreporter.org; no article corpus acquired','resource_note':'Single-thread lightweight processes, no feature extraction or fitting. Initial evidence/discovery network work briefly overlapped; article acquisitions were sequential. Web search/open tool transport bytes unavailable.','model_status':'No existing frozen TRAIN/DEV/TEST corpus or feature cache modified; new source pool unassigned','assistance_status':'Human byline and publication context supported; unaided composition not verified'}
(R/'AGGREGATE_AUDIT.json').write_text(json.dumps(agg,ensure_ascii=False,indent=2)+'\n')
result={'verified_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'checks':checks,'passed':all(checks.values()),'check_count':len(checks)}
(R/'VERIFICATION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(agg,ensure_ascii=False,indent=2))
assert all(checks.values())
