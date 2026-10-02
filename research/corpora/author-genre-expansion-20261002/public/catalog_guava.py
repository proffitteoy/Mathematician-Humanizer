import json,re,urllib.parse
from lxml import html
from acquire_sources import ROOT
rows=[json.loads(x) for x in (ROOT/'public/REQUEST_RECEIPTS.jsonl').read_text().splitlines()]
selected=[]; authors=[]
for rec in rows:
 if rec['kind']!='author_index' or not rec['private_path']:continue
 name=urllib.parse.unquote(rec['url'].split('/')[-1]);t=html.fromstring((ROOT/rec['private_path']).read_bytes()); candidates=[]
 for a in t.xpath('//h2/a'):
  header=a.getparent().getparent();d=re.search(r'\d{4}-\d{2}-\d{2}',header.text_content())
  if d and d[0]<'2022-01-01':
   candidates.append({'source_id':'guava','author':name,'author_url':rec['url'],'title':a.text_content().strip(),'publication_date_claim':d[0],'url':urllib.parse.urljoin(rec['url'],a.get('href')),'topic_tags':[s.text_content().strip() for s in header.xpath('.//div[contains(@class,"tags")]/span') if s.text_content().strip()]})
 candidates=sorted(candidates,key=lambda x:x['publication_date_claim'])
 # Dates spread within each known author. This is a transparent pilot convenience sample.
 indices=sorted(set(round(i*(len(candidates)-1)/3) for i in range(4)))
 picks=[candidates[i] for i in indices]
 authors.append({'author':name,'author_url':rec['url'],'identity_type':'original platform byline with author biography','observed_pre2022_index_count':len(candidates),'first_date_claim':candidates[0]['publication_date_claim'],'last_date_claim':candidates[-1]['publication_date_claim'],'selected_titles':[x['title'] for x in picks]})
 selected+=picks
(ROOT/'public/GUAVA_AUTHOR_CATALOG.json').write_text(json.dumps(authors,ensure_ascii=False,indent=2)+'\n')
(ROOT/'public/SELECTION_MANIFEST.json').write_text(json.dumps(selected,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(authors,ensure_ascii=False,indent=2))
