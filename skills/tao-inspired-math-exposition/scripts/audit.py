#!/usr/bin/env python3
"""Evidence-contract checker, never a proof checker or style classifier."""
import argparse,hashlib,json,pathlib,re
BASE={'goal','assumptions','reasoning','boundary','originality'}
def audit(text,review):
 errors=[]
 mode=review.get('mode')
 if mode not in ('exposition','learning'): errors.append('invalid mode')
 required=BASE|({'learning_test'} if mode=='learning' else set())
 actual=hashlib.sha256(text.encode('utf-8')).hexdigest()
 if review.get('text_sha256')!=actual: errors.append('text fingerprint changed or missing')
 checks=review.get('checks',{})
 if not isinstance(checks,dict): checks={};errors.append('checks must be an object')
 for key in sorted(required):
  item=checks.get(key,{})
  if not isinstance(item,dict): item={}
  if item.get('status')!='pass': errors.append(key+': missing, failed, or unresolved')
  quote=item.get('quote','');reason=item.get('reason','')
  if not isinstance(quote,str) or not quote.strip() or quote not in text: errors.append(key+': evidence not found')
  if not isinstance(reason,str) or len(reason.strip())<8: errors.append(key+': review reason missing or too short')
 return {'mechanical_contract_pass':not errors,'errors':errors,'text_sha256':actual,'mode':mode,'han_chars':len(re.findall(r'[\u3400-\u9fff]',text)),'question_marks':text.count('?')+text.count('？'),'semantic_correctness':'NOT_AUTOMATICALLY_VERIFIED','author_similarity':'NOT_MEASURED'}
def main():
 p=argparse.ArgumentParser();p.add_argument('--text',required=True);p.add_argument('--review',required=True);p.add_argument('--out');a=p.parse_args()
 try:r=audit(pathlib.Path(a.text).read_text(),json.loads(pathlib.Path(a.review).read_text()))
 except (OSError,ValueError,TypeError) as e: print(str(e));return 2
 s=json.dumps(r,ensure_ascii=False,indent=2)
 if a.out:pathlib.Path(a.out).write_text(s+'\n')
 print(s);return 0 if r['mechanical_contract_pass'] else 1
if __name__=='__main__':raise SystemExit(main())
