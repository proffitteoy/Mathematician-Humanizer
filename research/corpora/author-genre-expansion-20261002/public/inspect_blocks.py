"""Offline preservation audit, not linguistic feature extraction or model input."""
import json,re,hashlib
from lxml import html
from acquire_sources import ROOT
BLOCKS={'p','div','h1','h2','h3','h4','h5','h6','li','figcaption','blockquote','pre','table'}
def source_blocks(body):
    out=[]
    for n in body.iterdescendants():
        if n.tag not in BLOCKS: continue
        if any(c.tag in BLOCKS for c in n.iterdescendants()):continue
        text=n.text_content().strip()
        if not text:continue
        ancestors={a.tag for a in n.iterancestors()}
        role=('marked_quotation' if n.tag=='blockquote' or 'blockquote' in ancestors else
              'caption' if n.tag=='figcaption' or 'figure' in ancestors else
              'heading' if n.tag.startswith('h') else
              'list_item' if n.tag=='li' or 'li' in ancestors else
              'code_or_table' if n.tag in {'pre','table'} or ancestors&{'pre','table'} else
              'paragraph_element_mixed' if n.tag=='p' else 'division_element_mixed')
        out.append({'role':role,'source_tag':n.tag,'text':text})
    return out
if __name__=='__main__':
    rows=[json.loads(x) for x in (ROOT/'private/document_receipts.jsonl').read_text().splitlines()]
    out=[]
    for r in rows:
        body=html.fromstring((ROOT/r['body_html_path']).read_text())
        blocks=source_blocks(body); full=body.text_content(); key=hashlib.sha256(r['url'].encode()).hexdigest()[:20]
        (ROOT/'private/text'/f'{key}.blocks.json').write_text(json.dumps(blocks,ensure_ascii=False,indent=2)+'\n')
        (ROOT/'private/text'/f'{key}.body-text.txt').write_text(full)
        out.append({**r,'whole_body_text_codepoints':len(full),'whole_body_han_codepoints':len(re.findall('[\u3400-\u4dbf\u4e00-\u9fff]',full)),'nonempty_leaf_block_elements':len(blocks),'body_text_sha256':hashlib.sha256(full.encode()).hexdigest(),'text_representation':'HTML body text, private inspection only; not cleaned author prose','block_roles_status':'HTML structural roles only; inline speech, quotation, citations, borrowed text unresolved'})
    (ROOT/'private/structural_receipts.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps([{'author':r['author'],'title':r['title'],'chars':r['whole_body_text_codepoints'],'han':r['whole_body_han_codepoints'],'blocks':r['nonempty_leaf_block_elements']} for r in out],ensure_ascii=False,indent=2))
