import json,hashlib,re
from lxml import html
from acquire_sources import ROOT,fetch
manifest=json.loads((ROOT/'public/SELECTION_MANIFEST.json').read_text())
output=ROOT/'public/ARTICLE_CATALOG.jsonl'
private=ROOT/'private/document_receipts.jsonl'
done={x['url'] for x in map(json.loads,output.read_text().splitlines())} if output.exists() else set()
for row in manifest:
 if row['url'] in done: continue
 path=fetch(row['url'],'article')
 if not path: continue
 t=html.fromstring(path.read_bytes())
 a=t.xpath('//article[contains(@class,"node--view-mode-full")]')
 if not a: print('No article',row['url'],flush=True); continue
 a=a[0];b=a.xpath('.//div[contains(@class,"field--name-field-content")]')
 if not b: print('No body',row['url'],flush=True); continue
 b=b[0]; paragraphs=[n.text_content().strip() for n in b.xpath('.//p') if n.text_content().strip()]
 author=[n.text_content().strip() for n in a.xpath('.//span[@class="content-extra_author"]//a')]
 dates=re.findall(r'\d{4}-\d{2}-\d{2}', ''.join(a.xpath('.//span[@class="content-extra_info"]//text()')))
 license_links=t.xpath('//a[contains(@href,"creativecommons.org/licenses/")]/@href')
 key=hashlib.sha256(row['url'].encode()).hexdigest()[:20]
 prose='\n\n'.join(paragraphs)
 (ROOT/'private/text'/f'{key}.txt').write_text(prose)
 (ROOT/'private/text'/f'{key}.body.html').write_bytes(html.tostring(b,encoding='utf-8'))
 r={**row,'article_byline':author,'article_date_claim':dates[0] if dates else None,'license':'CC BY-NC-ND 3.0 Taiwan','license_links':sorted(set(license_links)),'article_level_license_notice_present':'本文採用' in a.text_content() and bool(license_links),'historical_evidence':'current original-site page and author index agree; no historical byte snapshot verified','snapshot_acquired':'current original HTML only','assistance_status':'unknown; no claim of unaided human authorship','original_html_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'byline_matches':author==[row['author']],'date_matches':bool(dates) and dates[0]==row['publication_date_claim'],'source_class':'collective humanities/social-science blog','model_admission':'not admitted; research-source acquisition only'}
 with output.open('a') as f:f.write(json.dumps(r,ensure_ascii=False)+'\n')
 pr={'url':row['url'],'html_path':str(path.relative_to(ROOT)),'text_path':f'private/text/{key}.txt','body_html_path':f'private/text/{key}.body.html','body_text_sha256':hashlib.sha256(prose.encode()).hexdigest(),'body_text_codepoints':len(prose),'han_codepoints':len(re.findall('[\u3400-\u4dbf\u4e00-\u9fff]',prose)),'nonempty_p_elements':len(paragraphs),'title':row['title'],'author':row['author']}
 with private.open('a') as f:f.write(json.dumps(pr,ensure_ascii=False)+'\n')
 print(row['author'],row['publication_date_claim'],row['title'],pr['body_text_codepoints'],len(paragraphs),r['byline_matches'],r['date_matches'],r['article_level_license_notice_present'],flush=True)
