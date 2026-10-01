"""Immutable observed-sequence contracts. No raw text or identifiers in repr."""
from __future__ import annotations
from dataclasses import dataclass,field
import hashlib,math,re
from research.linguistic.schema import CHANNEL_IDS,POS,SENSORS

VERSION='observed-sequence-contract/0.1'
EXCLUDED_HISTORY=frozenset(('zh:lexical.content_overlap','zh:lexical.trigram_reuse','zh:syntax.initial_pos_reuse'))
LOCAL_CHANNELS=tuple(k for k in CHANNEL_IDS if k not in EXCLUDED_HISTORY)
TARGET_BINS=POS+('OTHER',)
DEPENDENCY_CHANNELS=frozenset(s.id for s in SENSORS if s.dependency=='dep')
PARTITIONS=frozenset(('train','development','test'))
MISSING_REASONS=frozenset(('zero_denominator','parse_failed','alignment_failed','annotation_unresolved','dependency_unavailable','resource_limit','ineligible_structure','source_region_excluded','boundary_unconfirmed'))

def require(condition,message):
 if not condition:raise ValueError(message)
def digest(text):return hashlib.sha256(text.encode('utf-8')).hexdigest()
def hash_ok(value):return isinstance(value,str) and bool(re.fullmatch('[0-9a-f]{64}',value))
def finite(value):return type(value) in (int,float) and math.isfinite(value)

@dataclass(frozen=True)
class Provenance:
 archive_sha256:str
 source_sha256:str
 record_id:str=field(repr=False)
 component_id:str=field(repr=False)
 partition:str
 source_role:str='top_level'
 source_use:str='observed_parser_output_prediction'
 author_ground_truth:bool=False
 human_origin_ground_truth:bool=False
 def validate(self):
  require(hash_ok(self.archive_sha256) and hash_ok(self.source_sha256),'source_hash')
  require(bool(self.record_id) and bool(self.component_id),'source_identity')
  require(self.partition in PARTITIONS,'partition')
  require(self.source_role=='top_level' and self.source_use=='observed_parser_output_prediction','source_role_or_use')
  require(self.author_ground_truth is False and self.human_origin_ground_truth is False,'unsupported_ground_truth')

@dataclass(frozen=True)
class SensorRow:
 channel_ids:tuple[str,...]
 values:tuple[float|None,...]
 opportunities:tuple[float|None,...]
 missing_reasons:tuple[str|None,...]
 def validate(self):
  require(type(self.channel_ids)is tuple and self.channel_ids==LOCAL_CHANNELS,'local_channel_identity')
  require(all(type(x)is tuple and len(x)==68 for x in (self.values,self.opportunities,self.missing_reasons)),'local_shape')
  for v,o,r in zip(self.values,self.opportunities,self.missing_reasons):
   require(o is None or finite(o) and o>=0,'opportunity')
   if v is None:require(r in MISSING_REASONS,'missing_reason')
   else:require(finite(v) and o is not None and o>0 and r is None,'observed_value_opportunity')

@dataclass(frozen=True)
class ObservedUnit:
 source_index:int
 start:int
 end:int
 row:SensorRow
 target_counts:tuple[int,...]|None
 status:str='ok'
 analysis_status:str='automatic_unvalidated'
 failure_reason:str|None=None
 def validate(self):
  require(type(self.source_index)is int and self.source_index>=0 and type(self.start)is int and type(self.end)is int and 0<=self.start<self.end,'unit_span')
  require(self.status in {'ok','pos_only','failed','excluded'},'unit_status')
  require(self.analysis_status in {'automatic_unvalidated','synthetic_fixture'},'analysis_status')
  self.row.validate()
  if self.status=='pos_only':
   require(all(v is None and r=='dependency_unavailable' for k,v,r in zip(self.row.channel_ids,self.row.values,self.row.missing_reasons) if k in DEPENDENCY_CHANNELS),'pos_only_dependency_values')
  if self.status in {'failed','excluded'}:
   require(self.target_counts is None and all(v is None for v in self.row.values) and self.failure_reason in MISSING_REASONS,'failed_unit_contract')
  else:
   require(self.failure_reason is None,'unexpected_failure_reason')
   require(type(self.target_counts)is tuple and len(self.target_counts)==14 and all(type(x)is int and x>=0 for x in self.target_counts),'target_counts')

@dataclass(frozen=True)
class ObservedRecord:
 provenance:Provenance
 text:str=field(repr=False)
 units:tuple[ObservedUnit,...]
 parser_profile_sha256:str
 measurement_schema_sha256:str
 def validate(self):
  self.provenance.validate()
  require(type(self.text)is str and len(self.text)<=20000 and digest(self.text)==self.provenance.source_sha256,'exact_source_text')
  require(hash_ok(self.parser_profile_sha256) and hash_ok(self.measurement_schema_sha256),'producer_profile')
  require(type(self.units)is tuple and 1<=len(self.units)<=32,'unit_tuple_or_cap')
  cursor=0
  for i,u in enumerate(self.units):
   u.validate();require(u.source_index==i and cursor<=u.start<u.end<=len(self.text),'ordered_source_units');cursor=u.end

@dataclass(frozen=True)
class PredictionPair:
 input_indices:tuple[int,...]
 target_index:int
 input_cutoff:int
 component_start:int
 target_composition:tuple[float,...]|None
 missing_reason:str|None
 @property
 def eligible(self):return self.missing_reason is None

def check_known_split_isolation(records):
 """Verify declared hard groups and exact content, never prove independence."""
 maps=[{}, {}, {}]
 for record in records:
  record.validate();p=record.provenance
  for index,key in enumerate((p.record_id,p.component_id,p.source_sha256)):
   old=maps[index].setdefault(key,p.partition)
   require(old==p.partition,'cross_partition_known_dependency')
 return True
