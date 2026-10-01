"""Pure boundary/pair and train-only transformation helpers. No parser or fit IO."""
from __future__ import annotations
from dataclasses import dataclass
import math,unicodedata
from style_compiler.segmentation import segment
from research.linguistic.schema import POS
from .contracts import (LOCAL_CHANNELS,EXCLUDED_HISTORY,SensorRow,PredictionPair,
 ObservedRecord,require,finite)


def local_row(vectors):
 """Consume actual frozen linguistic channel identity, never relabel toy data."""
 ids=tuple(vectors['channel_ids'])
 from research.linguistic.schema import CHANNEL_IDS
 require(ids==CHANNEL_IDS,'linguistic_schema_order')
 keep=[i for i,k in enumerate(ids) if k not in EXCLUDED_HISTORY]
 row=SensorRow(LOCAL_CHANNELS,tuple(vectors['values'][i] for i in keep),
  tuple(vectors['opportunities'][i] for i in keep),tuple(vectors['missing_reasons'][i] for i in keep))
 row.validate();return row


def lexical_pos_counts(tokens):
 """Primitive observed POS counts with the existing lexical denominator."""
 from research.linguistic.adapter import lexical
 from research.linguistic.schema import ALL_POS
 result=[0]*14
 for t in tokens:
  require(t.upos in ALL_POS,'unsupported_pos')
  if lexical(t):result[POS.index(t.upos) if t.upos in POS else 13]+=1
 return tuple(result)


def closed_boundary(text,target_index,spans=None):
 """Whitespace after a known source-unit endpoint, not a terminal at EOF."""
 units=segment(text)[1] if spans is None else spans
 require(type(target_index)is int and 1<=target_index<len(units),'target_index')
 before,target=units[target_index-1],units[target_index]
 gap=text[before.end:target.start]
 if not gap or not gap.isspace():return False
 prefix=segment(text[:target.start])[1]
 return [(s.start,s.end) for s in prefix]==[(s.start,s.end) for s in units[:target_index]]


def pair_ledger(record:ObservedRecord):
 """One row for every original candidate. Failures are barriers, not removals."""
 record.validate();spans=segment(record.text)[1]
 require(len(spans)>=len(record.units),'source_unit_count')
 require([(u.start,u.end) for u in record.units]==[(s.start,s.end) for s in spans[:len(record.units)]],'source_unit_span_alignment')
 rows=[]
 for target in range(4,len(record.units)):
  reason=None;previous=record.units[:target];start=0
  for u in previous:
   if u.status in {'failed','excluded'}:start=u.source_index+1
  indices=tuple(range(start,target));counts=record.units[target].target_counts
  if not closed_boundary(record.text,target,spans):reason='boundary_unconfirmed'
  elif len(indices)<4:reason='insufficient_contiguous_prefix'
  elif record.units[target].status in {'failed','excluded'}:reason=record.units[target].failure_reason
  elif counts is None or sum(counts)==0:reason='zero_lexical_target'
  q=tuple(c/sum(counts) for c in counts) if reason is None else None
  rows.append(PredictionPair(indices,target,spans[target].start,
   spans[start].start if indices else spans[target].start,q,reason))
 return tuple(rows)


def prefix_lengths(record,pair):
 require(pair.eligible,'ineligible_pair')
 return (math.log1p(len(pair.input_indices)),math.log1p(pair.input_cutoff-pair.component_start))

@dataclass(frozen=True)
class TrainTransform:
 value_mean:tuple[float,...]
 value_scale:tuple[float,...]
 opportunity_mean:tuple[float,...]
 opportunity_scale:tuple[float,...]
 train_record_count:int
 value_support_records:tuple[int,...]
 opportunity_support_records:tuple[int,...]
 value_observation_count:tuple[int,...]
 opportunity_observation_count:tuple[int,...]
 value_center:tuple[float,...]
 value_mean_offset:tuple[float,...]
 opportunity_center:tuple[float,...]
 opportunity_mean_offset:tuple[float,...]
 def encode(self,row):
  row.validate();features=[]
  for i,(v,o) in enumerate(zip(row.values,row.opportunities)):
   features.extend((0.0 if v is None or self.value_scale[i]==0 else ((v-self.value_center[i])-self.value_mean_offset[i])/self.value_scale[i],
    float(v is not None),0.0 if o is None or self.opportunity_scale[i]==0 else ((math.log1p(o)-self.opportunity_center[i])-self.opportunity_mean_offset[i])/self.opportunity_scale[i],float(o is not None)))
  require(len(features)==272 and all(finite(x) for x in features),'encoded_shape_or_numeric')
  return tuple(features)


def fit_train_transform(records):
 """Stable train-only record-equal moments; no arbitrary variance epsilon.

 Center first at an actually observed value, then compute each record's mean
 offset and centered variance. Combine within/between-record variance equally.
 Exact constant and all-missing channels have scale0; encoding stays zero in all
 partitions. Caller owns separate approval for any empirical transform fit.
 """
 records=tuple(records);require(bool(records),'empty_training_records')
 for r in records:r.validate();require(r.provenance.partition=='train','transform_requires_train_only')
 moments=[];support_records=[];observation_counts=[];centering=[]
 for mode in ('value','opportunity'):
  means=[];scales=[];supports=[];observations=[];centers=[];offsets=[]
  for j in range(68):
   groups=[]
   for r in records:
    items=[u.row.values[j] if mode=='value' else (None if u.row.opportunities[j] is None else math.log1p(u.row.opportunities[j])) for u in r.units]
    items=[x for x in items if x is not None]
    if items:groups.append(items)
   if not groups: center=offset=mean=var=0.0
   else:
    center=groups[0][0]
    if all(x==center for items in groups for x in items):offset=var=0.0;mean=center
    else:
     ds=[[x-center for x in items] for items in groups]
     require(all(finite(x) for xs in ds for x in xs),'nonfinite_train_offsets')
     dm=[math.fsum(xs)/len(xs) for xs in ds]
     offset=math.fsum(dm)/len(dm);mean=center+offset
     try:
      within=[math.fsum((x-m)**2 for x in xs)/len(xs) for xs,m in zip(ds,dm)]
      var=math.fsum(v+(m-offset)**2 for v,m in zip(within,dm))/len(dm)
     except OverflowError:raise ValueError('nonfinite_train_variance') from None
     require(finite(mean) and finite(var) and var>=0,'nonfinite_train_moments')
   supports.append(len(groups));observations.append(sum(map(len,groups)))
   means.append(mean);scales.append(math.sqrt(var) if var>0 else 0.0);centers.append(center);offsets.append(offset)
  moments.extend((tuple(means),tuple(scales)));support_records.append(tuple(supports));observation_counts.append(tuple(observations));centering.extend((tuple(centers),tuple(offsets)))
 return TrainTransform(*moments,len(records),*support_records,*observation_counts,*centering)
