"""Read-only boundary census on the already frozen selection. No parser or fit."""
import argparse,collections,hashlib,json,pathlib,sys,time,resource

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--repo',type=pathlib.Path,required=True);ap.add_argument('--data',type=pathlib.Path,required=True);ap.add_argument('--private-manifest',type=pathlib.Path,required=True);ap.add_argument('--output',type=pathlib.Path,required=True);a=ap.parse_args()
 sys.path[:0]=[str(a.repo/'src'),str(a.repo/'research/audits')]
 from wikiconv_annual_census import Archive,jsonl_records,views
 from style_compiler.segmentation import segment
 start=time.monotonic();m=json.loads(a.private_manifest.read_text());selected={r['rownum']:r for r in m['selected_records']};stats=collections.defaultdict(collections.Counter);seen=0
 z=Archive(a.data/'wikiconv-chinese-2017/full.corpus.zip',m['archive_sha256'],80074478,871024181)
 for n,o,r in jsonl_records(z.chunks('utterances.jsonl')):
  if n not in selected:continue
  e=selected[n];v=next(views(r));text=v['text'];assert hashlib.sha256(text.encode()).hexdigest()==e['source_sha256'] and v['id']==e['id'];seen+=1;p=e['partition'];s=segment(text)[1];assert [[x.start,x.end] for x in s]==e['source_unit_spans'];good=0
  for target in range(4,min(32,len(s))):
   stats[p]['original_candidate_pairs']+=1
   gap=text[s[target-1].end:s[target].start]
   if not gap or not gap.isspace():stats[p]['boundary_unconfirmed_pairs']+=1;continue
   prefix=text[:s[target].start]; ps=segment(prefix)[1]
   assert [(x.start,x.end) for x in ps]==[(x.start,x.end) for x in s[:target]]
   # Arbitrary suffixes may begin with terminals/closers; already seen whitespace
   # must keep all prior unit spans unchanged.
   for suffix in ['！下一句。','”下一句。','甲。','\n乙。','3.14接續']:
    check=segment(prefix+suffix)[1][:target]
    assert [(x.start,x.end) for x in check]==[(x.start,x.end) for x in ps]
   stats[p]['boundary_closed_pairs']+=1;good+=1
  stats[p]['selected_records']+=1;stats[p]['records_with_closed_pairs']+=good>0;stats[p]['records_without_closed_pairs']+=good==0
 assert seen==192
 z.close();out={'profile':'observed-whitespace-closed-prefix/0.1','private_manifest_sha256':hashlib.sha256(a.private_manifest.read_bytes()).hexdigest(),'boundary_rule_sha256':hashlib.sha256((pathlib.Path(__file__).parent/'prefix-boundary-rule.json').read_bytes()).hexdigest(),'script_sha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),'partitions':{p:dict(v) for p,v in stats.items()},'source_segmenter_prefix_equalities_checked':sum(v['boundary_closed_pairs'] for v in stats.values()),'suffix_variant_checks_per_closed_prefix':5,'new_parser_inference':False,'raw_text_or_locators_in_output':False,'sampler_membership_changed':False,'wall_seconds':round(time.monotonic()-start,3),'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'new_download_bytes':0}
 with a.output.open('x') as f:json.dump(out,f,ensure_ascii=False,indent=2);f.write('\n')
 print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
