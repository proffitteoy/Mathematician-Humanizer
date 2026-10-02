import json,hashlib,re,datetime
from lxml import html
from acquire_sources import ROOT,fetch
for url in ['https://e-info.org.tw/copyright','https://e-info.org.tw/editorial-guidelines','https://tnf.org.tw/faq']:
 fetch(url,'rights_or_editorial_evidence')
manifest=json.loads((ROOT/'public/EINFO_SELECTION_MANIFEST.json').read_text());out=ROOT/'public/EINFO_ARTICLE_CATALOG.jsonl';private=ROOT/'private/einfo_document_receipts.jsonl'
done={x['url'] for x in map(json.loads,out.read_text().splitlines())} if out.exists() else set()
for row in manifest:
 if row['url'] in done:continue
 path=fetch(row['url'],'article')
 if not path:continue
 t=html.fromstring(path.read_bytes());scripts=t.xpath('//script[@id="__NEXT_DATA__"]/text()')
 if not scripts:raise ValueError('missing source hydration')
 p=json.loads(scripts[0])['props']['pageProps']['postData'];key=hashlib.sha256(row['url'].encode()).hexdigest()[:20]
 blocks=p['content']['blocks'];texts=[b['text'] for b in blocks if b.get('text')];content='\n\n'.join(texts)
 (ROOT/'private/text'/f'{key}.draftjs.json').write_text(json.dumps(p['content'],ensure_ascii=False,indent=2)+'\n')
 (ROOT/'private/text'/f'{key}.body-text.txt').write_text(content)
 roles={k:[{'id':x['id'],'name':x['name']} for x in p.get(k,[])] for k in ('reporters','stringers','writers','translators','reviewers','sources')}
 date=datetime.datetime.fromisoformat(p['publishTime'].replace('Z','+00:00')).astimezone(datetime.timezone(datetime.timedelta(hours=8))).date().isoformat()
 r={**row,'title':p['title'],'article_date_claim':date,'publication_timestamp':p['publishTime'],'current_page_updated_at':p.get('updatedAt'),'byline_roles':roles,'article_byline':[x['name'] for x in p['reporters']],'byline_matches':[x['name'] for x in p['reporters']]==[row['author']],'pre2022_date_claim':date<'2022-01-01','license':'CC BY-NC-ND 4.0 International, site default with stated exceptions','license_evidence_url':'https://e-info.org.tw/copyright','license_basis':'site-default original reporting; third-party excerpts, separately marked work and project-specific restrictions require individual review','source_class':'edited environmental journalism','genre':'reported_environment_news','topic_tags':[x['name'] for x in p['tags']],'historical_evidence':'pre2022 original-site publication field; current bytes acquired in 2026; no historical snapshot verified','assistance_status':'unknown; contemporary editorial policy permits auxiliary AI use and is not retroactive proof for earlier articles','original_html_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'model_status':'source research only; candidate for future stratified analysis, no fit performed'}
 with out.open('a') as f:f.write(json.dumps(r,ensure_ascii=False)+'\n')
 pr={'url':row['url'],'author':row['author'],'title':p['title'],'html_path':str(path.relative_to(ROOT)),'draftjs_path':f'private/text/{key}.draftjs.json','text_path':f'private/text/{key}.body-text.txt','body_text_sha256':hashlib.sha256(content.encode()).hexdigest(),'whole_body_text_codepoints':len(content),'whole_body_han_codepoints':len(re.findall('[\u3400-\u4dbf\u4e00-\u9fff]',content)),'nonempty_source_blocks':len(texts),'block_types':sorted(set(b['type'] for b in blocks)),'role_status':'source DraftJS block boundaries preserved; inline quotations and borrowed speech unresolved'}
 with private.open('a') as f:f.write(json.dumps(pr,ensure_ascii=False)+'\n')
 print(row['author'],date,p['title'],len(content),len(texts),r['byline_matches'],p.get('updatedAt'),flush=True)
