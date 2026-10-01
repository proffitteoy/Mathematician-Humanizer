"""Post-selection source-endpoint diagnostics; no fitting or test evaluation.

Endpoint flags never enter a model, loss weights or checkpoint selection. These
are properties of the frozen source view, not semantic completeness/true stops.
"""
from __future__ import annotations
from collections import defaultdict
import math,resource,time
import torch
from style_compiler.segmentation import segment
from .contracts import require
from .fit import _prepare_split,_predict,FitStopped
from .models import ConstantPrior,LatestState,make_model,soft_target_cross_entropy


def endpoint_flags(record,target_index):
 spans=segment(record.text)[1];require(0<=target_index<len(spans),'target_index')
 terminal=target_index==len(spans)-1
 if not terminal:return {'terminal_source_unit':False,'plain_character_extensible':False,'closer_or_terminal_extensible':False}
 expected=(spans[target_index].start,spans[target_index].end)
 def extends(suffix):
  after=segment(record.text+suffix)[1]
  return target_index>=len(after) or (after[target_index].start,after[target_index].end)!=expected
 return {'terminal_source_unit':True,'plain_character_extensible':extends('甲'),'closer_or_terminal_extensible':any(extends(x) for x in ('”','！'))}


def summarize_buckets(record_losses):
 result={}
 for name in ('all','interior','terminal_source_unit','plain_character_extensible'):
  groups=[values[name] for values in record_losses if values[name]]
  result[name]={'conditional_record_equal_ce':math.fsum(math.fsum(xs)/len(xs) for xs in groups)/len(groups) if groups else None,'records_with_targets':len(groups),'pairs':sum(map(len,groups))}
 return result


def post_selection_diagnostics(result,train_records,development_records,*,control_hook=None):
 """Evaluate already selected checkpoints with the unchanged frozen transform.

 Only caller-provided TRAIN/development records are accepted. Nothing about the
 endpoint labels is available until _predict has consumed its existing target.
 """
 start=time.monotonic();old_threads=torch.get_num_threads();torch.set_num_threads(2)
 def check():
  if control_hook:control_hook()
  if time.monotonic()-start>1800:raise FitStopped('post_selection_diagnostic_wall_cap')
  if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss>3*1024**2:raise FitStopped('post_selection_diagnostic_rss_cap')
 try:
  splits=[]
  for partition,records in [('train',tuple(train_records)),('development',tuple(development_records))]:
   require(records and all(r.provenance.partition==partition for r in records),'test_endpoint_statistics_sealed')
   splits.append((partition,records,_prepare_split(records,partition,result.transform)))
  arms=[('constant_prior',None,ConstantPrior(result.prior)),('latest_state',None,LatestState(result.prior))]
  for fitted in result.fits:
   model=make_model(fitted.arm,seed=fitted.seed);model.load_state_dict(fitted.best_state);arms.append((fitted.arm,fitted.seed,model))
  reports=[]
  with torch.no_grad():
   for name,seed,model in arms:
    model.eval();metrics={}
    for partition,records,prepared in splits:
     groups=[]
     for item in prepared.eligible_records:
      check();losses=defaultdict(list)
      for target in item.targets:
       check();logits=_predict(model,target,seed or 0,epoch=0)
       loss=soft_target_cross_entropy(logits,target.target).item()
       flags=endpoint_flags(records[item.ordinal],target.target_id[2])
       losses['all'].append(loss);losses['terminal_source_unit' if flags['terminal_source_unit'] else 'interior'].append(loss)
       if flags['plain_character_extensible']:losses['plain_character_extensible'].append(loss)
      groups.append(losses)
     metrics[partition]=summarize_buckets(groups)
    reports.append({'arm':name,'seed':seed,'partitions':metrics})
  return {'status':'post_checkpoint_diagnostic_only','endpoint_flags_in_model_inputs':False,'checkpoint_or_primary_loss_modified':False,'test_endpoint_counts_opened':False,'no_new_fit':True,'reports':reports,'wall_seconds':time.monotonic()-start}
 finally:torch.set_num_threads(old_threads)
