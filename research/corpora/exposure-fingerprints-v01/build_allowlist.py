"""Prepare private exclusion-only allowlist from existing receipts/metadata.
Does not read utterance/post/article bodies. No model or network dependencies.
"""
from pathlib import Path
import hashlib,json,sqlite3,sys
BASE=Path('/workspace/shared/style-compiler-data');REPO=Path('/workspace/shared/style-compiler')
OUT=BASE/'exposure-fingerprints-v01'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def put(p,x):
 with p.open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2);f.write('\n')
 return sha(p)
HELPERS={'wikiconv_annual_census.py':'e5051bd239812935096a035daadb3350a63ca151c7acd24021fa6eb6e39710b5','wikiconv_zip_audit.py':'84ced8137313f6d81c54b4fa6c271ef7f65ff110dc3d395330ce9cf603997e73'}
for name,h in HELPERS.items():assert sha(REPO/'research/audits'/name)==h
sys.path.insert(0,str(REPO/'research/audits'))
from wikiconv_annual_census import Archive,object_items
from wikiconv_zip_audit import metadata
sel=BASE/'learning-pilot-20261001-v02/frozen-selection.private.json'
assert sha(sel)=='ddbe04ae3a3a1d289fbb53e35872b2eb9df27407d92f6002066c992c1580b0b8'
s=json.loads(sel.read_text());excluded=set(s['excluded_component_ids'])|{r['component_id'] for r in s['selected_records']}
page_map=s['all_page_component_map'];pages={p for p,c in page_map.items() if c in excluded}
archive_path=BASE/'wikiconv-chinese-2017/full.corpus.zip'
a=Archive(archive_path,'635500ba887cef0c9d2bfaef03659de2974b5fd84b8a0cd90a9bd7bdef7f492a',80074478,871024181)
conv_page={k:metadata(v)['page_id'] for k,v in object_items(a.chunks('conversations.json'))};a.close()
assert pages<=set(conv_page.values())
dbp=BASE/'wikiconv-chinese-2017/structural-frame.sqlite';db=sqlite3.connect(dbp.as_uri()+'?mode=ro',uri=True);db.execute('PRAGMA query_only=ON')
db.row_factory=sqlite3.Row
control=dict(db.execute('select key,value from control'))
assert control['archive_sha256']=='635500ba887cef0c9d2bfaef03659de2974b5fd84b8a0cd90a9bd7bdef7f492a'
wanted_rows={r['rownum'] for r in db.execute('select rownum,conversation from views') if conv_page[r['conversation']] in pages}
view_rows=[dict(r) for r in db.execute('select seq,rownum,byte_offset,role,id,conversation,header,chars,nonempty,text_sha256 from views') if r['rownum'] in wanted_rows]
expected_hash=put(OUT/'expected-source-views.private.json',view_rows)
old=BASE/'wikiconv-chinese-2002-pilot/full.corpus.zip'
receipts={}
blogs_path=BASE/'non-dialogue-20261001/acquisition-receipt.private.json';blogs=json.loads(blogs_path.read_text());assert len(blogs['items'])==39
posts=[]
for r in blogs['items']:
 p=Path(r['raw_file']).resolve();assert (BASE/'non-dialogue-20261001').resolve() in p.parents
 posts.append({'path':str(p),'sha256':r['sha256'],'bytes':r['bytes'],'original_path':r['path'],'exposure_role':'prior_third_party_blog_diagnostic'})
pmc_path=BASE/'academic-pmc-20261001/fulltext-receipt.private.json';pmc=json.loads(pmc_path.read_text());assert len(pmc['results'])==6
papers=[{'path':str(BASE/'academic-pmc-20261001/fulltext'/f"{r['pmcid']}.xml"),'sha256':r['oai_raw_sha256'],'article_sha256':r['article_raw_sha256'],'article_range':r['article_raw_byte_range'],'pmcid':r['pmcid'],'exposure_role':'prior_licensed_PMC_diagnostic'} for r in pmc['results']]
x={'schema_version':'exclusion-fingerprint-allowlist/1','purpose':'old_exposure_exclusion_only','selection_sha256':sha(sel),'source_receipt_hashes':{'blogs':sha(blogs_path),'pmc':sha(pmc_path),'structural_db':sha(dbp)},'readers':HELPERS,'blogs':posts,'pmc':papers,'wikiconv2017':{'path':str(archive_path),'sha256':'635500ba887cef0c9d2bfaef03659de2974b5fd84b8a0cd90a9bd7bdef7f492a','bytes':80074478,'expanded_bytes':871024181,'conversation_to_page':conv_page,'excluded_old_components':sorted(excluded),'excluded_pages':sorted(pages),'allowed_top_rows':sorted(wanted_rows),'expected_view_file':str(OUT/'expected-source-views.private.json'),'expected_view_file_sha256':expected_hash},'wikiconv2002':{'path':str(old),'sha256':'8c6b3f21adaad7b1d55eef3122593b418264c61b7bab9cd30c2f07cfbfce41ab','bytes':22364,'scope':'all prior format-pilot source views'},'forbidden':['user_owner_writings','model_tokens_or_targets_or_predictions'],'new_three_pre2022_blog_diagnostics':'not_in_this_allowlist; still pending exclusion fingerprint coverage'}
h=put(OUT/'source-allowlist.private.json',x)
print(json.dumps({'allowlist_sha256':h,'blogs':39,'pmc':6,'old_component_union':len(excluded),'old_pages':len(pages),'2017_top_rows':len(wanted_rows),'2017_source_views':len(view_rows),'2017_source_view_codepoints':sum(r['chars'] for r in view_rows),'2017_max_view_codepoints':max(r['chars'] for r in view_rows),'raw_body_read':False}))
