"""Deterministic architecture construction after TRAIN-only eligibility."""
import json,hashlib
import torch
from .models import *
FIXED_SEEDS=(1701,1702,1703)
def deterministic_seed(seed):
    import random
    random.seed(seed);torch.manual_seed(seed);torch.use_deterministic_algorithms(True)
def build_ladder(catalog,seed=1701,transform=None):
    D=len(catalog.ids);targets=None if transform is None else tuple(torch.where(transform.score_eligible)[0].tolist())
    active=None if transform is None else tuple(torch.where(transform.active_values)[0].tolist());view=InputView(D,tuple(range(D)),active_value_indices=active)
    def build(name):
        deterministic_seed(seed);m=PrefixModel(name,view,D,target_indices=targets);m.initialization_seed=seed;return m
    models={name:build(name) for name in ('F1','Fcov','F2','F3','F4')};brackets={}
    if abs(parameter_count(models['Fcov'])-parameter_count(models['F2']))/parameter_count(models['F2'])>.1:
        deterministic_seed(seed);models['Fcov'],brackets['Fcov']=capacity_match('Fcov',view,D,[parameter_count(models['F2'])],target_indices=targets)
    deterministic_seed(seed);models['F1_wide'],brackets['F1_wide']=capacity_match('F1',view,D,[parameter_count(models['Fcov']),parameter_count(models['F2'])],target_indices=targets)
    deterministic_seed(seed);models['F2_wide'],brackets['F2_wide']=capacity_match('F2',view,D,[parameter_count(models['F4'])],target_indices=targets)
    for m in models.values():m.initialization_seed=seed
    return models,brackets

def build_control(catalog,name,mode,seed,transform=None):
    deterministic_seed(seed);ix=catalog.structural_indices if mode=='length' else tuple(range(len(catalog.ids)))
    targets=None if transform is None else tuple(torch.where(transform.score_eligible)[0].tolist());active=None if transform is None else tuple(torch.where(transform.active_values)[0].tolist())
    model=PrefixModel(name,InputView(len(catalog.ids),ix,mode,active_value_indices=active),len(catalog.ids),target_indices=targets);model.initialization_seed=seed;return model

def registered_run_grid():
    runs=[]
    for seed in FIXED_SEEDS:
        for name in ('F1','Fcov','F2','F3','F4','F1_wide','F2_wide'):runs.append({'id':f'pooled.{name}.{seed}','model':name,'mode':'values','seed':seed,'source':None})
        for mode in ('mask_opportunity','pure_mask','length'):
            for name in ('F1','F2','F4'):runs.append({'id':f'pooled.{mode}.{name}.{seed}','model':name,'mode':mode,'seed':seed,'source':None})
        runs.append({'id':f'pooled.shuffled.F4.{seed}','model':'F4','mode':'values','seed':seed,'source':None,'shuffle_training':True})
        runs.append({'id':f'pooled.independent.F4.{seed}','model':'independent_F4','mode':'values','seed':seed,'source':None})
        for source in ('baike','web'):
            for name in ('F1','F2','F4'):runs.append({'id':f'{source}.{name}.{seed}','model':name,'mode':'values','seed':seed,'source':source})
    assert len(runs)==72 and len({r['id'] for r in runs})==72
    return runs

def transform_signature(transform):return hashlib.sha256(json.dumps(transform.to_dict(),sort_keys=True,separators=(',',':')).encode()).hexdigest()

def build_registered_model(catalog,run,transform):
    seed=run['seed'];name=run['model'];mode=run['mode'];deterministic_seed(seed)
    if name=='independent_F4':
        shared,_=build_ladder(catalog,seed,transform);target=parameter_count(shared['F4']);del shared;deterministic_seed(seed)
        model,_=independent_capacity_match(catalog,target,target_indices=tuple(torch.where(transform.score_eligible)[0].tolist()),active_value_indices=tuple(torch.where(transform.active_values)[0].tolist()))
    elif mode=='values':models,_=build_ladder(catalog,seed,transform);model=models[name]
    else:model=build_control(catalog,name,mode,seed,transform)
    model.initialization_seed=seed;model.transform_signature=transform_signature(transform);return model
