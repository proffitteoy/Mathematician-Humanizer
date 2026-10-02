"""Reuse existing local research instruments; never install/download/train."""
from __future__ import annotations
import argparse, hashlib, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def discover_research(start=ROOT):
    """Find containing checkout when installed under repo/skills; else sibling."""
    start=Path(start).resolve()
    for candidate in (start,*start.parents):
        if (candidate/'research/linguistic/adapter.py').is_file() and (candidate/'src/style_compiler').is_dir():
            return candidate
    return start.parent/'style-compiler'
DEFAULT_RESEARCH=discover_research()
DEFAULT_MODELS=ROOT.parent/'style-models/stanza-zh-hans-1.10.0'
def sha(text):return hashlib.sha256(text.encode('utf-8')).hexdigest()

def configure(repo):
    repo=Path(repo).resolve()
    if not (repo/'research/linguistic/adapter.py').is_file():
        raise ValueError('Missing existing style-compiler research checkout: '+str(repo))
    for p in (repo,repo/'src'):
        if str(p) not in sys.path:sys.path.insert(0,str(p))

class Analyzer:
    def __init__(self,repo=DEFAULT_RESEARCH,models=None):
        configure(repo)
        self.parser=None;self.missing_reason='No existing parser/model directory supplied; surface-only analysis'
        if models:
            try:
                from research.linguistic.stanza_local import LocalStanza
                self.parser=LocalStanza(models)
            except (ValueError,ImportError,OSError,RuntimeError) as exc:
                self.missing_reason=f'{type(exc).__name__}: local parser unavailable; no download attempted'
        self.repo=Path(repo)
    def analyze(self,text,label='user-input'):
        from research.surface.adapter import SourceObservation,SourceView,Interval,make_projection,measure
        view=SourceView(sha('writing-prototype-local-input'),label+'.txt',0,0,'writing-prototype/0.1',0,'','user_supplied_or_demo_prose',sha(text),len(text))
        obs=SourceObservation(view,text)
        projection=make_projection(view,(Interval(0,len(text)),) if text else (),annotation_profile='whole-input-no-role-inference/0.1',annotation_status='provisional')
        surface=measure(obs,projection)
        result={'schema_version':'writing-analysis/0.1','text_sha256':sha(text),'surface':surface,
                'linguistic':{'status':'unavailable','reason':self.missing_reason},
                'quality_score':None,'human_probability':None,'learned_multiview_ranker':'unavailable'}
        if self.parser:
            from research.linguistic.adapter import measure as lmeasure
            parsed=self.parser.parse(obs)
            result['linguistic']={'status':'measured_unvalidated', 'bundle':lmeasure(obs,projection,parsed),
                'parsed_sentences':sum(p.status=='ok' for p in parsed.sentences),
                'failed_sentences':sum(p.status=='failed' for p in parsed.sentences)}
        result['summary']=summarize(result)
        return result

def summarize(a):
    t=a['surface']['target_projection'];ls=a['linguistic']
    result={'counts':t['counts'],'sentence_content_lengths':[s['content_chars'] for s in t['sentences']],
            'surface_values':{k:v['value'] for k,v in t['features'].items()},
            'linguistic_status':ls['status'],'linguistic_values':{},'missing':{}}
    if ls['status']=='measured_unvalidated':
        vals=ls['bundle']['target']['global_measurements']
        result['linguistic_values']={k:v['value'] for k,v in vals.items()}
        result['missing']={k:v['missing_reason'] for k,v in vals.items() if v['value'] is None}
        result['observed_channels']=sum(v['value'] is not None for v in vals.values())
        result['total_channels']=len(vals)
        result['parsed_sentences']=ls['parsed_sentences'];result['failed_sentences']=ls['failed_sentences']
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('input',type=Path);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--research',type=Path,default=DEFAULT_RESEARCH);p.add_argument('--models',type=Path)
    a=p.parse_args();an=Analyzer(a.research,a.models);result=an.analyze(a.input.read_text(),a.input.stem)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result['summary'],ensure_ascii=False,indent=2))
if __name__=='__main__':main()
