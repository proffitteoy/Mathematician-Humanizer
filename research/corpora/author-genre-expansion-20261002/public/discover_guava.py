import json,urllib.parse
from lxml import html
from acquire_sources import ROOT,fetch
NAMES=['邱韻芳','趙恩潔','郭佩宜','趙綺芳','林秀幸','潘美玲','徐雨村','容邵武','彭仁郁','莊雅仲']
rows=[json.loads(x) for x in (ROOT/'public/REQUEST_RECEIPTS.jsonl').read_text().splitlines()]
rec=next(x for x in rows if '/6338' in x['url'])
tree=html.fromstring((ROOT/rec['private_path']).read_bytes())
links={a.text_content().strip():urllib.parse.urljoin('https://guavanthropology.tw',a.get('href')) for a in tree.xpath('//h3/a')}
for name in NAMES:
 p=fetch(links[name],'author_index')
 if not p:continue
 t=html.fromstring(p.read_bytes())
 print(name,[(a.text_content().strip(),a.get('href')) for a in t.xpath('//h2/a')],flush=True)
 print('pages',[(a.text_content().strip(),a.get('href')) for a in t.xpath('//nav[contains(@class,"pager")]//a')],flush=True)
