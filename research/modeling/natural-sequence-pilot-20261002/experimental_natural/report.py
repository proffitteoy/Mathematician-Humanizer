"""Aggregate-only public serializer; never serialize arbitrary private records."""
import dataclasses,json,math
from pathlib import Path
FORBIDDEN={'raw_text','prompt','prompt_text','text','question','answer','component','question_id','answer_id','component_id','source_id','source_ID','source_span','offset','offset_bytes','path','cache_path','cache_sha256','record','records','predictions','parsed_annotation','graph','hash','per_document','per_sample','document_id','unit_values','values','source_hash','annotation_hash','projection_hash','source_sha256','annotation_sha256','text_sha256','original_text_sha256','pair_id','question_family_id','inference_cluster','source_sentence_index','source_block_index','row_order','original_position','candidate_original_index','global_measurements','global_vector','prefix_values','prefix_observed','prefix_opportunity','prefix_opportunity_known'}
TOP_LEVEL={'scope','status','support','endpoints','negative_controls','missingness','unrun_stages','fit_counts','capacity_brackets','resource_summary','quality_claim','discourse_graph_status'}
def validate_public(value):
    if dataclasses.is_dataclass(value):raise ValueError('Private typed records cannot be exported')
    if isinstance(value,dict):
        for k,v in value.items():
            if k in FORBIDDEN:raise ValueError('Private per-record field blocked: '+k)
            validate_public(v)
    elif isinstance(value,(list,tuple)):
        for v in value:validate_public(v)
    elif value is None or isinstance(value,(str,bool,int)):pass
    elif isinstance(value,float):
        if not math.isfinite(value):raise ValueError('Nonfinite public number')
    else:raise TypeError('Unsupported public object')
def export_report(path,report):
    if set(report)-TOP_LEVEL:raise ValueError('Unexpected report section')
    validate_public(report);Path(path).write_text(json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n')
