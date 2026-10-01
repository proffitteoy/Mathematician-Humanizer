"""Explicit offline smoke CLI; keep input and detailed output outside repository.

Example: PYTHONPATH=src:. python -m research.linguistic.smoke --models /private/models
 --input /private/original-synthetic-zh.txt --receipt /private/smoke-receipt.json
Input is declared ORIGINAL SYNTHETIC ONLY by this command, never a real author.
"""
import argparse,json,platform,time,resource,hashlib
from collections import Counter
from pathlib import Path
from dataclasses import asdict
from .fixtures import source,full
from .stanza_local import LocalStanza,MODEL_FILES,MODEL_COMMIT
from .adapter import measure
from .schema import schema_document,SENSORS


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--models',required=True);p.add_argument('--input',required=True)
    p.add_argument('--receipt',required=True);p.add_argument('--original-synthetic-only',action='store_true',required=True)
    a=p.parse_args();raw=Path(a.input).read_bytes();text=raw.decode('utf-8',errors='strict')
    before=time.perf_counter();parser=LocalStanza(a.models);loaded=time.perf_counter()
    obs=source(text);parsed=parser.parse(obs);result=measure(obs,full(obs),parsed);finished=time.perf_counter()
    measurements=result['target']['global_measurements'];sequence=result['target']['sequence'];graph=result['target']['graph']
    receipt={'status':'original_synthetic_chinese_raw_text_smoke_not_validation',
      'python':platform.python_version(),'parser_profile':asdict(parser.profile),
      'input_declaration':'original synthetic Chinese prose; raw text kept outside repository',
      'synthetic_input_utf8_sha256':hashlib.sha256(raw).hexdigest(),
      'models_total_bytes':sum(v[0] for v in MODEL_FILES.values()),'model_commit':MODEL_COMMIT,
      'model_loaded_vocabulary':parser.vocabulary,'load_seconds':loaded-before,'parse_and_measure_seconds':finished-loaded,
      'process_peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
      'source_codepoints':len(text),'source_sentence_count':len(parsed.sentences),
      'parsed_sentences':sum(s.status=='ok' for s in parsed.sentences),'failed_sentences':sum(s.status=='failed' for s in parsed.sentences),
      'model_token_count':sum(len(s.tokens) for s in parsed.sentences),'channel_count':len(SENSORS),
      'global_observed_channel_count':sum(v['value'] is not None for v in measurements.values()),
      'global_missing_reasons':dict(Counter(v['missing_reason'] for v in measurements.values() if v['value'] is None)),
      'sequence_row_count':len(sequence),'graph_node_count':len(graph['nodes']),'graph_edge_count':len(graph['edges']),
      'channel_examples':{k:measurements[k] for k in ('zh:upos.PRON','zh:lexical.mattr100','zh:dependency.span_mean','zh:syntax.verb_root_without_subject')},
      'raw_text_uploaded':False,'reference_distributions_fitted':False,'author_distributions_fitted':False,
      'independent_annotation_accuracy_measured':False,'learned_model_integration':False,
      'limitations':['Synthetic smoke cannot establish Chinese-domain accuracy, role attribution or author/human construct validity.',
                     'One automatic analysis, no calibrated confidence or alternate parse distribution.',
                     'Full-model semantic/discourse and empirical-admission gates remain blocked.']}
    Path(a.receipt).write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:receipt[k] for k in ('parsed_sentences','failed_sentences','channel_count','global_observed_channel_count','global_missing_reasons','process_peak_rss_kib')},ensure_ascii=False))

if __name__=='__main__':main()
