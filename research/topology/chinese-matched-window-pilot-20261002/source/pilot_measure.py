"""Opt-in offline Chinese BERT + unchanged local Stanza measurement adapters."""
import gc,importlib.metadata,json,os,socket,sys
from hashlib import sha1,sha256
from pathlib import Path
import numpy as np
from pilot_core import digest,serial,aligned_prefix_pair,slope_schedules,typed_values,HISTORY


def offline():
    os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false')
    def deny(*a,**kw):raise RuntimeError('Network disabled during measurement')
    socket.socket.connect=deny;socket.socket.connect_ex=deny;socket.create_connection=deny


def verify_model(root,lock):
    root=Path(root).resolve(strict=True)
    for f in lock['files']:
        p=root/f['name']
        if p.is_symlink() or not p.is_file() or p.stat().st_size!=f['bytes']:raise ValueError('Model asset size/path mismatch')
        h=sha256() if f['hash_kind']=='sha256' else sha1(b'blob '+str(f['bytes']).encode()+b'\0')
        with p.open('rb') as stream:
            for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
        if h.hexdigest()!=f['hash']:raise ValueError('Model asset digest mismatch')


def check_runtime(lock):
    pins={**lock['existing_required'],**{r['package']:r['version'] for r in lock['overlay_wheels']}}
    for name,version in pins.items():
        if importlib.metadata.version(name)!=version:raise ValueError('Runtime pin mismatch: '+name)
    if len(os.sched_getaffinity(0))>2:raise ValueError('Two-CPU affinity required')


def encode_selected(raw_pairs,model_root,model_lock):
    offline();verify_model(model_root,model_lock)
    import torch
    from transformers import AutoTokenizer,AutoModel
    torch.set_num_threads(2);torch.set_num_interop_threads(1)
    tokenizer=AutoTokenizer.from_pretrained(model_root,local_files_only=True,use_fast=True,trust_remote_code=False)
    if not tokenizer.is_fast:raise ValueError('Fast offset-aware tokenizer required')
    model=AutoModel.from_pretrained(model_root,local_files_only=True,trust_remote_code=False,use_safetensors=True,add_pooling_layer=False)
    model=model.to(device='cpu',dtype=torch.float32).eval()
    if model.config.hidden_size!=768 or model.config.model_type!='bert':raise ValueError('Chinese BERT shape mismatch')
    measured=[]
    for meta,raw in raw_pairs:
        align=aligned_prefix_pair(raw['human_text'],raw['machine_text'],tokenizer)
        pair=[]
        for j,arm in enumerate(('human','chatgpt')):
            r={k:meta[k] for k in ('component_id','pair_id','source','split')};r['arm']=arm
            r['alignment']={k:v for k,v in align.items() if k!='windows'}
            if not align['available']:
                r.update(window_text='',window_sha256=digest(''),window_characters=0,content_tokens=0,unknown_token_rate=None,
                         topology={'available':False,'reason':align['reason']},alignment_verified=False,
                         encoded_input_ids=None,encoded_special_tokens_mask=None,linguistic_input_sha256=None,han_characters=None)
            else:
                w=align['windows'][j];tokens=tokenizer(w['text'],return_tensors='pt',return_special_tokens_mask=True,truncation=False)
                special=tokens.pop('special_tokens_mask')[0].bool()
                actual=tokens['input_ids'][0][~special].tolist()
                if actual!=w['ids'] or len(actual)!=align['n_tokens']:raise ValueError('Encoder/window identity mismatch')
                with torch.inference_mode():states=model(**tokens).last_hidden_state[0][~special].cpu().numpy().copy()
                if states.shape!=(len(actual),768) or states.dtype!=np.float32 or not np.isfinite(states).all():raise ValueError('Invalid token states')
                topology=slope_schedules(states)
                r.update(window_text=w['text'],window_sha256=w['sha256'],window_characters=len(w['text']),content_tokens=len(actual),
                    unknown_token_rate=float(np.mean(np.asarray(actual)==tokenizer.unk_token_id)),
                    repeated_vector_fraction=float(1-len(np.unique(states,axis=0))/len(states)),topology=topology,
                    encoded_input_ids=tokens['input_ids'][0].tolist(),encoded_special_tokens_mask=special.int().tolist(),
                    aligned_content_ids=actual,alignment_verified=True,linguistic_input_sha256=None,
                    han_characters=None)
            pair.append(r)
        measured.extend(pair)
    del model,tokenizer;gc.collect()
    return measured


def measure_linguistic(records,instrument_root,stanza_models,source_lock):
    offline();root=Path(instrument_root).resolve(strict=True)
    for f in source_lock['files']:
        p=root/f['path']
        if p.is_symlink() or digest(p.read_bytes())!=f['sha256']:raise ValueError('Pinned instrument source mismatch')
    sys.path[:0]=[str(root/'src'),str(root)]
    from research.surface.adapter import SourceView,SourceObservation,Interval,make_projection
    from research.linguistic.stanza_local import LocalStanza
    from research.linguistic.adapter import measure,lexical
    from research.linguistic.schema import CHANNEL_IDS
    from research.linguistic.unicode_scripts import in_script
    channels=[c for c in CHANNEL_IDS if c not in HISTORY]
    if channels!=source_lock['channel_ids_68']:raise ValueError('Instrument channel identity mismatch')
    parser=LocalStanza(stanza_models,threads=2)
    for r in records:
        text=r['window_text'];r['lexical_tokens']=None
        if digest(text)!=r['window_sha256']:raise ValueError('Linguistic/window identity mismatch')
        r['linguistic_input_sha256']=digest(text)
        r['han_characters']=sum(in_script(c,'Han') for c in text)
        if not text.strip():
            measurements={c:{'value':None,'opportunities':None,'missing_reason':'unavailable_aligned_window','status':'unavailable','comparison_eligible':False} for c in channels}
        else:
            # Explicit derived-prefix source identity, not a mislabeled full-answer cache.
            blob=serial({'text':text});sv=SourceView(digest(blob),'derived-prefix.json',0,0,'derived-exact-prefix/1',0,'/text',r['arm'],digest(text),len(text))
            obs=SourceObservation(sv,text);projection=make_projection(sv,(Interval(0,len(text)),),annotation_profile='topology-zh-exact-prefix/v1',annotation_status='provisional')
            try:
                parsed=parser.parse(obs);bundle=measure(obs,projection,parsed)
                if (bundle['measurement_status']!='candidate_unvalidated' or bundle['empirical_model_admitted'] is not False
                        or bundle['learned_contract_compatible'] is not False):raise ValueError('Instrument flags changed')
                measurements=bundle['target']['global_measurements']
                if all(s.status!='failed' for s in parsed.sentences):
                    r['lexical_tokens']=sum(lexical(t) for s in parsed.sentences for t in s.tokens)
            except (ValueError,RuntimeError) as e:
                if str(e) not in {'source_resource_limit','sentence_count_resource_limit','total_token_resource_limit'}:
                    raise
                reason=str(e)
                measurements={c:{'value':None,'opportunities':None,'missing_reason':reason,'status':'unavailable','comparison_eligible':False} for c in channels}
        r['linguistic']=typed_values(measurements,channels)
    del parser;gc.collect()
    return records
