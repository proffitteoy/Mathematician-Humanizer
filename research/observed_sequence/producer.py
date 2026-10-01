"""Explicit sentence-local producer, never invoked automatically or on import.

The caller supplies an already initialized, hash-verified LocalStanza-compatible
backend. This module downloads nothing. Natural extraction needs a separately
reviewed run manifest; the scaffolding tests use only an original fake backend.
"""
from __future__ import annotations
from dataclasses import asdict
import hashlib,json
from research.linguistic.contracts import SentenceParse,Token
from research.linguistic.adapter import _aggregate,vectors
from research.linguistic.schema import SENSORS,SCHEMA_VERSION
from research.linguistic.unicode_scripts import UNICODE_VERSION,SCRIPTS_SHA256
from style_compiler.segmentation import segment
from .contracts import ObservedRecord,ObservedUnit,Provenance,digest,require
from .prepare import local_row,lexical_pos_counts


def _fingerprint(obj):return hashlib.sha256(json.dumps(obj,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()

class SentenceLocalProducer:
 def __init__(self,backend,*,analysis_status='automatic_unvalidated'):
  backend.profile.validate()
  require(analysis_status in {'automatic_unvalidated','synthetic_fixture'},'analysis_status')
  self.backend=backend;self.analysis_status=analysis_status
  self.parser_profile_sha256=_fingerprint(asdict(backend.profile))
  self.measurement_schema_sha256=_fingerprint({'version':SCHEMA_VERSION,'sensors':[asdict(x) for x in SENSORS],'unicode_version':UNICODE_VERSION,'unicode_scripts_sha256':SCRIPTS_SHA256,'history_inputs':'none; three history channels excluded'})
  self.cache={};self.parser_calls=0

 def _sentence(self,text,source_hash,span,*,use_cache):
  piece=text[span.start:span.end]
  key=(source_hash,self.parser_profile_sha256,span.index,span.start,span.end,digest(piece))
  if use_cache and key in self.cache:return self.cache[key]
  if len(piece)>512:
   result=SentenceParse(span.index,span.start,span.end,(),'failed','resource_limit',self.analysis_status)
  else:
   try:
    # This is the only text supplied to the parser. No next unit or document.
    self.parser_calls+=1;doc=self.backend.pipeline(piece)
    require(len(doc.sentences)==1,'parser_split')
    words=doc.sentences[0].words;require(0<len(words)<=512,'token_resource_limit')
    tokens=[]
    for w in words:
     require(type(w.id)is int and type(w.start_char)is int and type(w.end_char)is int,'alignment_failed')
     require(piece[w.start_char:w.end_char]==w.text,'alignment_failed')
     feats=tuple(tuple(x.split('=',1)) for x in w.feats.split('|')) if w.feats else ()
     tokens.append(Token(w.id,span.start+w.start_char,span.start+w.end_char,w.text,w.upos,w.head,w.deprel,feats))
    result=SentenceParse(span.index,span.start,span.end,tuple(tokens),analysis_status=self.analysis_status)
    result.validate(text,span)
   except (ValueError,RuntimeError,IndexError,TypeError):
    # Exception strings can contain source text; do not record or echo them.
    result=SentenceParse(span.index,span.start,span.end,(),'failed','parse_failed',self.analysis_status)
  if use_cache:self.cache[key]=result
  return result

 def _unit(self,text,source_hash,span,*,use_cache):
  parsed=self._sentence(text,source_hash,span,use_cache=use_cache)
  feature_rows=_aggregate([parsed],{span.index:0},prior=[])
  unit=ObservedUnit(span.index,span.start,span.end,local_row(vectors(feature_rows)),
   None if parsed.status=='failed' else lexical_pos_counts(parsed.tokens),parsed.status,parsed.analysis_status,parsed.reason)
  unit.validate();return unit

 def record(self,text,provenance:Provenance,*,use_cache=True):
  provenance.validate();require(digest(text)==provenance.source_sha256 and len(text)<=20000,'exact_source_text')
  spans=segment(text)[1][:32]
  result=ObservedRecord(provenance,text,tuple(self._unit(text,provenance.source_sha256,s,use_cache=use_cache) for s in spans),self.parser_profile_sha256,self.measurement_schema_sha256)
  result.validate();return result

 def prefix_units(self,text,provenance:Provenance,cutoff,*,use_cache=True):
  """Re-segment the visible prefix, not a sliced full-document parse/graph.

  The caller must supply a boundary-eligible cutoff from the frozen pair ledger.
  The full-source hash is identity metadata; parser text is only each visible unit.
  Use use_cache=False for independent parser/prefix equivalence audits.
  """
  provenance.validate();require(digest(text)==provenance.source_sha256,'exact_source_text')
  require(type(cutoff)is int and 0<cutoff<=len(text),'prefix_cutoff')
  visible=text[:cutoff];require(visible[-1].isspace(),'boundary_unconfirmed')
  spans=segment(visible)[1];require(1<=len(spans)<=32,'prefix_units_cap')
  require(visible[spans[-1].end:].isspace(),'visible_closure_whitespace')
  probe=segment(visible+'甲')[1][:len(spans)]
  require([(x.start,x.end) for x in probe]==[(x.start,x.end) for x in spans],'prefix_fragment_not_closed')
  return tuple(self._unit(visible,provenance.source_sha256,s,use_cache=use_cache) for s in spans)

 def audit_prefix(self,text,provenance,cutoff):
  """Fresh strict-prefix parses and local rows for private independent readback."""
  # Run the public boundary validation, without using any cached parse result.
  provenance.validate();require(digest(text)==provenance.source_sha256,'exact_source_text')
  require(type(cutoff)is int and 0<cutoff<=len(text),'prefix_cutoff')
  visible=text[:cutoff];require(visible[-1].isspace(),'boundary_unconfirmed')
  spans=segment(visible)[1];require(1<=len(spans)<=32,'prefix_units_cap')
  require(visible[spans[-1].end:].isspace(),'visible_closure_whitespace')
  probe=segment(visible+'甲')[1][:len(spans)]
  require([(x.start,x.end) for x in probe]==[(x.start,x.end) for x in spans],'prefix_fragment_not_closed')
  parsed=[];units=[]
  for span in spans:
   sentence=self._sentence(visible,provenance.source_sha256,span,use_cache=False);parsed.append(sentence)
   rows=_aggregate([sentence],{span.index:0},prior=[])
   units.append(ObservedUnit(span.index,span.start,span.end,local_row(vectors(rows)),None if sentence.status=='failed' else lexical_pos_counts(sentence.tokens),sentence.status,sentence.analysis_status,sentence.reason))
  return tuple(parsed),tuple(units)
