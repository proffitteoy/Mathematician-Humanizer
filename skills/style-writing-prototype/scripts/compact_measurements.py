"""Publish explicit summaries, never pretend they are complete analyzer bundles."""
import argparse,hashlib,json
from pathlib import Path
KEEP=('zh:dependency.span_mean','zh:syntax.subordinate_arcs','zh:syntax.nominal_modifier_size','zh:lexical.content_overlap','zh:syntax.initial_pos_reuse')
def compact(raw,raw_bytes,filename):
    sf=raw['surface'];lg=raw['linguistic'];b=lg['bundle'];t=b['target']
    result={k:raw[k] for k in ('text_sha256','summary','quality_score','human_probability','learned_multiview_ranker')}
    result.update(schema_version='writing-analysis-compact/0.1',artifact_form='compact_measurement_summary_not_full_analysis',
      full_bundle={'local_filename':filename,'sha256':hashlib.sha256(raw_bytes).hexdigest(),'bytes':len(raw_bytes),'included_in_publication':False},
      omitted=['raw token/POS/dependency graph and node/edge records','full 71-channel sentence vectors except five disclosed diagnostic channels','duplicated raw-source surface view'],
      surface={k:sf[k] for k in ('measurement_profile','measurement_profile_sha256','target_projection')},
      linguistic={'status':lg['status'],'parsed_sentences':lg['parsed_sentences'],'failed_sentences':lg['failed_sentences'],
         'bundle':{'target':{'global_measurements':t['global_measurements'],'sequence':[
             {**{k:v for k,v in row.items() if k not in {'measurements','vector'}},'measurements':{k:row['measurements'][k] for k in KEEP}} for row in t['sequence']]}}})
    # Preserve identities without raw token graphs. Key names remain producer-defined.
    for key,value in b.items():
        if key!='target' and any(term in key for term in ('profile','schema','sha256')):
            result['linguistic']['bundle'][key]=value
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('input_directory',type=Path);p.add_argument('output_directory',type=Path);a=p.parse_args();a.output_directory.mkdir(parents=True,exist_ok=True)
    for f in sorted(a.input_directory.glob('*.json')):
        raw=f.read_bytes();j=json.loads(raw);out=compact(j,raw,f.name)
        (a.output_directory/f.name).write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print('Wrote exact-text-bound compact summaries with full-bundle hashes; raw graphs omitted.')
if __name__=='__main__':main()
