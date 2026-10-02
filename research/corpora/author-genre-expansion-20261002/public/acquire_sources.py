#!/usr/bin/env python3
"""Bounded, sequential acquisition. Source bytes remain private; receipts are metadata only."""
import datetime,hashlib,json,pathlib,time,urllib.request,urllib.error,urllib.parse,sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
for _directory in ('public','private/raw','private/text','private/evidence'):
    (ROOT/_directory).mkdir(parents=True,exist_ok=True)
CAP=20*1024*1024
MAX_RESPONSE=1024*1024
ALLOW={'guavanthropology.tw','www.twreporter.org','web.archive.org','www.ioe.sinica.edu.tw','creativecommons.org','e-info.org.tw','www.e-info.org.tw','v2.e-info.org.tw','tnf.org.tw'}
def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def fetch(url,kind='evidence'):
    host=urllib.parse.urlsplit(url).hostname
    if host not in ALLOW: raise ValueError('Host not approved '+str(host))
    if host == 'www.twreporter.org' and urllib.parse.urlsplit(url).path not in {'/robots.txt','/a/lience-footer'}:
        raise ValueError('Reporter article acquisition excluded by observed usage restriction')
    ledger=ROOT/'public'/'REQUEST_RECEIPTS.jsonl'
    rows=[json.loads(x) for x in ledger.read_text().splitlines()] if ledger.exists() else []
    if len(rows)>=200: raise RuntimeError('request cap')
    spent=sum(x['response_bytes'] for x in rows)
    if spent+MAX_RESPONSE>CAP: raise RuntimeError('byte cap')
    url=urllib.parse.quote(url,safe=':/?&=%#')
    key=hashlib.sha256(url.encode()).hexdigest()[:20]
    existing=[x for x in rows if x['url']==url and x.get('status')==200]
    if existing:
        cached=ROOT/existing[0]['private_path']
        if not cached.exists() or hashlib.sha256(cached.read_bytes()).hexdigest()!=existing[0]['sha256']:
            raise RuntimeError('Prior receipt exists but private bytes are missing or changed; no implicit redownload')
        return cached
    req=urllib.request.Request(url,headers={'User-Agent':'ChineseSourceResearch/1.0 (bounded noncommercial provenance audit)','Accept-Encoding':'identity'})
    start=time.monotonic(); b=b''; status=None; err=None; final=url; headers={}
    try:
      with urllib.request.urlopen(req,timeout=22) as r:
        status=r.status; final=r.url
        if urllib.parse.urlsplit(final).hostname not in ALLOW: raise ValueError('unexpected redirect host')
        headers={k:r.headers.get(k) for k in ('Content-Type','Last-Modified','ETag','Content-Length')}
        b=r.read(MAX_RESPONSE+1)
        if len(b)>MAX_RESPONSE: raise RuntimeError('response cap')
    except Exception as e: err=type(e).__name__+': '+str(e)
    path=pathlib.Path('private')/('raw' if kind=='article' else 'evidence')/(key+'.html')
    if b: (ROOT/path).write_bytes(b)
    record={'url':url,'final_url':final,'kind':kind,'retrieved_at_utc':now(),'status':status,'response_bytes':len(b),'sha256':hashlib.sha256(b).hexdigest() if b else None,'seconds':round(time.monotonic()-start,3),'headers':headers,'error':err,'private_path':str(path) if b else None}
    with ledger.open('a') as f:f.write(json.dumps(record,ensure_ascii=False)+'\n')
    if err: print(record,file=sys.stderr);return None
    time.sleep(.3)
    return ROOT/path
if __name__=='__main__':
    for u in sys.argv[1:]: print(fetch(u))
