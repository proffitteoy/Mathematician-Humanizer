"""Independent audit of saved private predictions vs public aggregate.

Does not load Stanza or use evaluate.score_pair / linguistic._aggregate.
Original straightforward formulas audit scoring plus six downstream sensors.
"""
import argparse,json,math,statistics,unicodedata
from collections import Counter
from pathlib import Path


def is_lex(t):return t['upos']!='PUNCT' and any(not c.isspace() and unicodedata.category(c)[0]!='P' for c in t['form'])

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--private-records',type=Path,required=True);ap.add_argument('--aggregate',type=Path,required=True);args=ap.parse_args()
    units=json.loads(args.private_records.read_text());agg=json.loads(args.aggregate.read_text())
    units=[u for u in units if all(a in u for a in ('reference','production','control'))]
    checks=0
    for arm in ('production','control'):
        for stratum in ('all','news','wiki'):
            subset=[u for u in units if stratum=='all' or u['stratum']==stratum]
            for kind in ('all','reference_lexical'):
                totals=Counter()
                for unit in subset:
                    gold=unit['reference']['tokens'];pred=unit[arm]['tokens']
                    for g in gold:
                        if kind=='reference_lexical' and not is_lex(g):continue
                        totals['reference_tokens']+=1
                        matches=[p for p in pred if p['start']==g['start'] and p['end']==g['end']]
                        assert len(matches)<=1
                        if not matches:totals['unmatched_reference_tokens']+=1;continue
                        p=matches[0];totals['aligned_dependents']+=1;totals['upos_correct']+=g['upos']==p['upos']
                        if not g['head'] or not p['head']:head_ok=g['head']==p['head']==0
                        else:
                            gh,ph=gold[g['head']-1],pred[p['head']-1]
                            head_ok=gh['start']==ph['start'] and gh['end']==ph['end']
                        totals['head_correct']+=head_ok
                        totals['full_las_correct']+=head_ok and g['deprel']==p['deprel']
                        totals['base_las_correct']+=head_ok and g['deprel'].split(':')[0]==p['deprel'].split(':')[0]
                actual=agg['scores_common_gate_only'][arm][stratum][kind]
                for key in ('reference_tokens','aligned_dependents','unmatched_reference_tokens','upos_correct','head_correct','full_las_correct','base_las_correct'):
                    assert actual[key]==totals[key],(arm,stratum,kind,key);checks+=1
        # Recompute per-record metric errors independently, native denominators.
        paired={k:[] for k in ('zh:upos.NOUN','zh:upos.PART','zh:upos.SCONJ','zh:word_length.mean','zh:dependency.span_mean','zh:dependency.depth_mean')}
        for unit in units:
            values={}
            for a in ('reference',arm):
                all_tokens=unit[a]['tokens'];lex=[t for t in all_tokens if is_lex(t)];rank={t['local_id']:i for i,t in enumerate(lex)}
                v={f'zh:upos.{p}':sum(t['upos']==p for t in lex)/len(lex) for p in ('NOUN','PART','SCONJ')}
                v['zh:word_length.mean']=sum(sum(not c.isspace() and not unicodedata.category(c).startswith('P') for c in t['form']) for t in lex)/len(lex)
                distances=[abs(rank[t['local_id']]-rank[t['head']]) for t in lex if t['head'] in rank and t['deprel'].split(':')[0]!='punct']
                v['zh:dependency.span_mean']=statistics.mean(distances) if distances else None
                depths=[]
                for t in lex:
                    depth=0;current=t
                    while current['head']:
                        depth+=1;current=all_tokens[current['head']-1]
                    depths.append(depth)
                v['zh:dependency.depth_mean']=statistics.mean(depths)
                values[a]=v
            for key in paired:
                if values['reference'][key]is not None and values[arm][key]is not None:paired[key].append(values[arm][key]-values['reference'][key])
        for key,delta in paired.items():
            reported=agg['channels'][arm][key]
            assert reported['paired_records']==len(delta);checks+=1
            assert math.isclose(reported['mae'],statistics.mean(abs(x) for x in delta),rel_tol=1e-12,abs_tol=1e-12);checks+=1
            assert math.isclose(reported['signed_bias'],statistics.mean(delta),rel_tol=1e-12,abs_tol=1e-12);checks+=1
    print(json.dumps({'independent_aggregate_comparisons_passed':checks,'private_records_checked':len(units),'no_raw_text_or_locator_output':True}))

if __name__=='__main__':main()
