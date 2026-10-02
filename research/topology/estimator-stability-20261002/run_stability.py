"""One bounded, offline run of the pre-frozen PHD reliability protocol."""
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[k]='2'
for k in ('HF_HUB_OFFLINE','TRANSFORMERS_OFFLINE','HF_HUB_DISABLE_TELEMETRY','HF_HUB_DISABLE_IMPLICIT_TOKEN','PYTHONDONTWRITEBYTECODE'):
    os.environ[k]='1'
from pathlib import Path
ROOT=Path(__file__).resolve().parent
PILOT=ROOT.parent/'topology-replication-20261002'
os.environ['HF_HOME']=str(ROOT/'unused-offline-cache')
import datetime, hashlib, json, resource, signal, sys, time, zipfile
START=time.monotonic()
os.sched_setaffinity(0, sorted(os.sched_getaffinity(0))[:2])
import numpy as np
import scipy
from scipy.spatial.distance import cdist
import torch, transformers
from transformers import RobertaModel, RobertaTokenizer
sys.path.insert(0,str(PILOT/'recovered'))
from phd import Config, make_plan, sample_sizes, mst_edges
from analyze_stability import analyze
SEEDS=list(range(20261010,20261030))
PROTOCOL_SHA='2636a1371c5454512e3f13e0cfd3313804e4ab0faf4adda62a0773d59e4eaaf9'
SELECTION_SHA='a4b31b5982c5107adab88a2fca25989c19df4e3b193ceedea50ba946cce5f1b5'

def sha(data): return hashlib.sha256(data).hexdigest()
def file_sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()
def write(name,obj):
    (ROOT/name).write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n')
def disk(path):return sum(p.stat().st_size for p in path.rglob('*') if p.is_file() and not p.is_symlink())
def check_budget(*unused):
    if time.monotonic()-START>1790: raise RuntimeError('wall_time_safety_stop')
    if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss>=int(2.75*1024**2):raise RuntimeError('rss_safety_stop')
def transform(s):
    if s is None or not np.isfinite(s) or s==1:return None
    d=float(1/(1-s))
    return d if np.isfinite(d) else None

def measure(distance,n,seed):
    sizes=sample_sizes(n,'gptid_notebook_v1')
    config=Config(protocol='gptid_notebook_v1',seed=seed)
    plan=make_plan(n,sizes,config)
    out={'seed':seed,'sample_sizes':sizes,'plan_sha256':sha(json.dumps(plan,separators=(',',':')).encode()),'runs':[]}
    x=np.log(np.asarray(sizes,dtype=float));q=len(x)
    den=q*np.sum(x*x)-np.sum(x)**2
    for run in plan:
        energies=[[float(mst_edges(distance[np.ix_(ids,ids)]).sum()) for ids in group] for group in run]
        med=np.array([np.median(v) for v in energies])
        if den==0 or not np.all(np.isfinite(med)) or np.any(med<=0):
            out['runs'].append({'draw_energies':energies,'median_energies':med.tolist(),'slope':None,'dimension':None,'undefined_reason':'degenerate_grid_or_energy'})
            continue
        y=np.log(med)
        slope=float((q*np.sum(x*y)-np.sum(x)*np.sum(y))/den)
        centered=float((x-x.mean())@(y-y.mean())/((x-x.mean())@(x-x.mean())))
        intercept=float(y.mean()-slope*x.mean())
        resid=y-(intercept+slope*x);total=float(((y-y.mean())**2).sum())
        out['runs'].append({'draw_energies':energies,'median_energies':med.tolist(),'slope':slope,'centered_slope':centered,'slope_formula_abs_error':abs(slope-centered),'intercept':intercept,'r_squared':None if total==0 else float(1-(resid@resid)/total),'dimension':transform(slope),'slope_outside_0_1':not (0<=slope<1)})
    slopes=[r['slope'] for r in out['runs']]
    out['mean_slope']=None if None in slopes else float(np.mean(slopes))
    out['dimension']=transform(out['mean_slope'])
    out['status']='defined' if out['dimension'] is not None else 'undefined'
    out['mean_slope_outside_0_1']=None if out['mean_slope'] is None else not (0<=out['mean_slope']<1)
    out['dimension_outside_2_18']=None if out['dimension'] is None else not (2<=out['dimension']<=18)
    return out

def synthetic_checks():
    # No selected corpus measurements: deterministic synthetic/replayed arithmetic only.
    from phd import estimate
    points=np.random.default_rng(872).normal(size=(80,4))
    got=measure(cdist(points,points),80,20261010)
    ref=estimate(points,Config(protocol='gptid_notebook_v1',seed=20261010))
    np.testing.assert_allclose([r['slope'] for r in got['runs']],[r['slope'] for r in ref['runs']],rtol=0,atol=1e-12)
    for a,b in zip(got['runs'],ref['runs']):np.testing.assert_array_equal(a['draw_energies'],b['draw_energies'])
    assert transform(1) is None and transform(1.01)<0 and transform(.99)>99
    assert sample_sizes(63,'gptid_notebook_v1')==list(range(40,60,3))
    return {'synthetic_energy_exact_parity':True,'synthetic_slope_parity_atol':1e-12,'singular_and_negative_transform_checks':True}

def main():
    assert file_sha(ROOT/'STABILITY_PROTOCOL.md')==PROTOCOL_SHA
    assert not (ROOT/'measurements.jsonl').exists(), 'no_repeated_measurement_run'
    assert not (ROOT/'run-manifest.json').exists(), 'existing_run_requires_honest_review_not_retry'
    original_files=[p for p in PILOT.rglob('*') if p.is_file() and 'runtime' not in p.relative_to(PILOT).parts]
    baseline={str(p.relative_to(PILOT)):file_sha(p) for p in original_files}
    write('pilot-baseline-hashes.json',baseline)
    manifest={'status':'running','started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'protocol_sha256':PROTOCOL_SHA,'selection_sha256':SELECTION_SHA,'seeds':SEEDS,'script_hashes':{p.name:file_sha(p) for p in [ROOT/'run_stability.py',ROOT/'analyze_stability.py']},'limits':{'wall_seconds':1800,'rss_bytes':3*1024**3,'new_disk_bytes':500*1024**2,'total_working_bytes':3_000_000_000,'cpu_count':2},'cpu_affinity':sorted(os.sched_getaffinity(0)),'runtime':{'python':sys.version,'numpy':np.__version__,'scipy':scipy.__version__,'torch':torch.__version__,'transformers':transformers.__version__},'new_network_requests':0,'new_model_or_data_downloads':0,'baseline_working_bytes':disk(PILOT),'completed_cells':0,'computed_distinct_clouds':0,'reused_cells':0}
    write('run-manifest.json',manifest)
    signal.signal(signal.SIGALRM,check_budget);signal.setitimer(signal.ITIMER_REAL,1,1)
    cells=[]
    try:
        manifest['synthetic_checks']=synthetic_checks()
        assert manifest['baseline_working_bytes']+disk(ROOT)<3_000_000_000
        assert file_sha(PILOT/'selection-manifest.json')==SELECTION_SHA
        selection=json.loads((PILOT/'selection-manifest.json').read_text())
        old=json.loads((PILOT/'paired-pilot-results.json').read_text())
        saved={(r['domain'],r['source_index']):r for r in old['records']}
        model_manifest=json.loads((PILOT/'model-manifest.json').read_text())
        for item in model_manifest['files']:
            p=PILOT/'roberta-base'/item['path']
            assert p.stat().st_size==item['bytes'] and file_sha(p)==item['sha256']
        manifest['model_revision']=model_manifest['revision']
        torch.set_num_threads(2);torch.set_num_interop_threads(1);torch.manual_seed(20261002);torch.use_deterministic_algorithms(True)
        tokenizer=RobertaTokenizer.from_pretrained(PILOT/'roberta-base',local_files_only=True);tokenizer.truncation_side='right'
        model=RobertaModel.from_pretrained(PILOT/'roberta-base',local_files_only=True,use_safetensors=True,add_pooling_layer=False,attn_implementation='eager').to(device='cpu',dtype=torch.float32).eval()
        def encode(ids):
            xx=torch.tensor([tokenizer.build_inputs_with_special_tokens(ids)],dtype=torch.long)
            with torch.inference_mode():h=model(input_ids=xx,attention_mask=torch.ones_like(xx)).last_hidden_state[0,1:-1].numpy()
            assert h.shape==(len(ids),768) and np.isfinite(h).all()
            return h.copy()
        with (ROOT/'measurements.jsonl').open('x') as out:
            for dom in selection['domains']:
                zpath=PILOT/'private-inputs'/('human_gpt3_davinci_003_'+dom['domain']+'.zip')
                assert file_sha(zpath)==dom['source_archive_sha256']
                with zipfile.ZipFile(zpath) as z:rows=json.loads(z.read(z.namelist()[0]))
                for chosen in dom['selected']:
                    row=rows[chosen['index']];prior=saved[(dom['domain'],chosen['index'])]
                    assert row['split']=='train' and sha(row['prefix'].encode())==chosen['prefix_sha256']
                    ids={}
                    for label,field,key in [('human','gold_completion','gold_sha256'),('ai','gen_completion','gen_sha256')]:
                        text=row[field];assert sha(text.encode())==chosen[key]
                        ids[label]=tokenizer.encode(text.replace('\n',' ').replace('  ',' '),add_special_tokens=False)
                    match=min(256,len(ids['human']),len(ids['ai']));assert match==prior['matched_n']
                    for label in ['human','ai']:
                        cache={}
                        for condition,n in [('original_window',min(510,len(ids[label]))),('matched_reencoded',match)]:
                            prior_cond=prior['texts'][label]['conditions'][condition]
                            assert prior_cond['content_tokens']==n
                            cell={'domain':dom['domain'],'source_index':chosen['index'],'label':label,'condition':condition,'n':n,'source_sha256':prior['texts'][label]['source_sha256'],'cloud_sha256':prior_cond['cloud_float32_c_order_sha256']}
                            if n in cache:
                                cloud_sha,reports=cache[n]
                                assert cloud_sha==cell['cloud_sha256']
                                cell['measurement_source']='same_token_ids_reused';manifest['reused_cells']+=1
                            else:
                                cloud=encode(ids[label][:n]);cloud_sha=sha(cloud.tobytes())
                                assert cloud_sha==cell['cloud_sha256'], 'cloud_hash_mismatch'
                                distance=cdist(cloud,cloud);assert np.isfinite(distance).all()
                                reports=[]
                                for seed in SEEDS:
                                    reports.append(measure(distance,n,seed));check_budget()
                                cache[n]=(cloud_sha,reports);manifest['computed_distinct_clouds']+=1
                                cell['measurement_source']='deterministically_reencoded_hash_verified'
                            cell['reports']=reports;cells.append(cell)
                            out.write(json.dumps(cell,separators=(',',':'),allow_nan=False)+'\n');out.flush()
                            manifest['completed_cells']=len(cells)
                            manifest['elapsed_seconds']=time.monotonic()-START
                            manifest['peak_rss_kib']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                            manifest['new_derived_bytes']=disk(ROOT)
                            assert manifest['new_derived_bytes']<500*1024**2
                            assert manifest['baseline_working_bytes']+manifest['new_derived_bytes']<3_000_000_000
                            write('run-manifest.json',manifest)
                    print(json.dumps({'completed_pairs':len(cells)//4,'completed_cells':len(cells),'elapsed_seconds':time.monotonic()-START,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}),flush=True)
                del rows
        assert len(cells)==128
        manifest['all_128_cloud_hashes_match_pilot']=True
        manifest['analysis']=analyze(cells,ROOT)
        current={str(p.relative_to(PILOT)):file_sha(p) for p in original_files}
        assert current==baseline,'pilot_artifact_changed'
        manifest['original_pilot_artifacts_unchanged']=True
        manifest['verified_original_file_count']=len(baseline)
        manifest['status']='completed'
    except BaseException as e:
        manifest['status']='incomplete';manifest['error_type']=type(e).__name__;manifest['error']=str(e)
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        manifest['elapsed_seconds']=time.monotonic()-START
        manifest['peak_rss_kib']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        manifest['new_derived_bytes']=disk(ROOT)
        manifest['ended_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
        write('run-manifest.json',manifest)
        print(json.dumps(manifest),flush=True)

if __name__=='__main__':main()
