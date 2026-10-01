"""Summarize frozen character checks for the authorized 96; no new parser/rules."""
import collections,gzip,hashlib,json,pathlib
V=pathlib.Path('/workspace/shared/style-scale10-source-v01/private');O=pathlib.Path('/workspace/shared/style-scale10-calibration-results-review-v01/public')
freeze=json.loads((V/'calibration96.freeze.private.json').read_text());out={}
for frame in ('discussion','news_prose','guide_prose'):
 rows=[x for x in freeze['records']if x['source_frame']==frame];s=collections.Counter();reject=collections.Counter();pointrej=collections.Counter();uh=collections.Counter();ch=collections.Counter();mh=collections.Counter();mc=collections.Counter();cp=[]
 for r in rows:
  name=hashlib.sha256(json.dumps(r['record_key'],ensure_ascii=False,separators=(',',':')).encode()).hexdigest()+'.private.json.gz'
  x=json.loads(gzip.decompress((V/'calibration.records'/name).read_bytes()));cs=x['preparse']['segment_checks'];segs=x['projection']['segments'];s['fixed_records']+=1;s['source_codepoints']+=r['source_codepoints'];s['raw_source_length_200_20000_pass']+=200<=r['source_codepoints']<=20000;s['no_projected_segments']+=not bool(segs);s['records_with_segments']+=bool(segs);s['preparse_eligible_records']+=x['preparse']['preparse_eligible'];s['projected_codepoints']+=sum(len(z['text'])for z in segs);s['segments']+=len(cs)
  mh[max([z['unit_count']for z in cs],default=0)]+=1;mc[max([z['closed_points_count']for z in cs],default=0)]+=1;cp.append(max([len(z['text'])for z in segs],default=0))
  for z in cs:
   reject.update(z['rejections']);pointrej.update(z['candidate_point_rejections'].values());uh[z['unit_count']]+=1;ch[z['closed_points_count']]+=1;s['confirmed_closed_points_all_segments']+=z['closed_points_count'];s['candidate_closed_point_checks']+=z['closed_points_count']+len(z['candidate_point_rejections'])
  for code,label in [('unit_count_outside_8_64','units_8_64'),('unit_over512_codepoints','unit_length_le512'),('han_LN_fraction_under_half','Han_fraction_ge_half'),('fewer_than4_closed_points','closed_points_ge4')]:
   s['records_any_segment_pass_'+label]+=any(code not in z['rejections']for z in cs)
  current=cs
  for code,label in [('unit_count_outside_8_64','units_8_64'),('unit_over512_codepoints','unit_length_le512'),('han_LN_fraction_under_half','Han_fraction_ge_half'),('fewer_than4_closed_points','closed_points_ge4')]:
   current=[z for z in current if code not in z['rejections']];s['same_segment_cumulative_survival_'+label]+=bool(current)
 def ordered(c):return dict(sorted(c.items()))
 out[frame]={'counts':dict(s),'segment_rejection_counts_overlapping':ordered(reject),'closed_point_rejection_counts':ordered(pointrej),'all_segment_unit_count_histogram':ordered(uh),'all_segment_closed_points_histogram':ordered(ch),'per_record_max_units_histogram_including_zero_output':ordered(mh),'per_record_max_closed_points_histogram_including_zero_output':ordered(mc),'per_record_max_segment_codepoints_sorted':sorted(cp)}
result={'schema_version':'fixed96-character-qualification-diagnostics/1','frozen_input_seal_sha256':'26f40568753bece5e26197fc696c371d728efbea3ed4ce111ab0c296bb371b51','denominator':96,'NLP_calls':0,'fit_calls':0,'rules_changed':False,'new_candidates_read':0,'definitions':{'rejection_counts':'按输出片段计，多原因重叠，不能相加作记录数','cumulative_survival':'同一片段依次满足单位数、单单位长度、Han比例、闭合点；不能把不同片段的优点拼合','closed_point_checks':'冻结候选target=4至min(32,units)-1；统计真实空白/原文空白/稳定前缀的现有检查，不增改阈值','projection_retention':'原始字符包括大量模板/网址/列表，保留率不等于有效散文损失率'},'by_source':out}
(O/'qualification-diagnostics.aggregate.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False,indent=2))
