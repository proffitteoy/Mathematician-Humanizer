"""Synthetic formula equivalence and read-only protected-file audit."""
import argparse
import importlib.util
import json
import random
import sys
from pathlib import Path
from native_adapter import adapt_html, measure, sha256, content_chars, quantile, ranks


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--instrument-repo',required=True,type=Path)
    p.add_argument('--workspace',required=True,type=Path)
    p.add_argument('--frozen-manifest',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path)
    args=p.parse_args()
    sys.path.insert(0,str(args.instrument_repo/'src'))
    from style_compiler.features import extract, quantile as original_quantile, ranks as original_ranks
    from style_compiler.segmentation import content_chars as original_chars
    spec=importlib.util.spec_from_file_location('fixture_helper',args.instrument_repo/'tests/helpers.py')
    fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
    rng=random.Random(20261002)
    n=100
    for i in range(n):
        lengths=[rng.randrange(1,100) for _ in range(rng.randrange(4,25))]
        text=''.join('甲'*length+('。' if j%2 else '！') for j,length in enumerate(lengths))
        native=measure(text,adapt_html('<p>'+text+'</p>',text))['features']
        legacy=extract(fixture.document(text))['features']
        for fid,old in legacy.items():
            assert native['NP'+fid[1:]]['value']==old['value'],fid
        assert ranks(lengths)==original_ranks(lengths)
        assert all(quantile(lengths,q)==original_quantile(lengths,q) for q in (0,.1,.25,.5,.75,.9,1))
    chars='甲乙a A １２3😀𠮷é\r\n!?'
    assert content_chars(chars)==original_chars(chars)
    formulas=[]
    for name in ('src/style_compiler/segmentation.py','src/style_compiler/features.py','research/surface/adapter.py'):
        raw=(args.instrument_repo/name).read_bytes()
        formulas.append({'path':name,'sha256':sha256(raw)})
    frozen=json.loads(args.frozen_manifest.read_text())
    names=[
      'm4_chinese_paired_20261002/raw/qazh_chatgpt.jsonl',
      'm4_chinese_paired_20261002/raw/qazh_davinci.jsonl',
      'm4_chinese_paired_20261002/public/predeclared_protocol.json',
      'm4_chinese_paired_20261002/public/SCHEMA_AMENDMENT_1.md',
      'm4_chinese_paired_20261002/private/freeze_manifest.json',
      'm4_chinese_paired_20261002/private/components_and_splits.json',
      'm4_chinese_paired_20261002/private/cohort_identity_views.jsonl']
    checks=[]
    for name in names:
        b=(args.workspace/name).read_bytes();expected=frozen[name]
        assert len(b)==expected['bytes'] and sha256(b)==expected['sha256'],name
        checks.append({'logical_artifact':Path(name).name,'sha256':expected['sha256'],'unchanged':True})
    receipt={'status':'passed','synthetic_matching_operand_cases':n,'features_per_case':8,
             'claim':'Exact formula equivalence only when native and legacy boundaries/operands match; no general legacy instrument equivalence',
             'unicode_LN_equivalence':True,'rank_and_linear_quantile_equivalence':True,
             'instrument_files':formulas,'instrument_local_snapshot_revision':'2c3eeb0bcf3020fcba36f13b2bc6bab490b3f1ae',
             'requested_repository_base':'9539f5da7ed7546d9888bc596fef39d2662f32ad',
             'newer_remote_instrument_equivalence_checked':False,
             'protected_M4_artifacts':checks,'protected_M4_artifact_count':len(checks),
             'protected_scope':'Existing raw bodies, protocol/amendment, frozen manifest, cohort identities and split assignment; not a claim about unrelated concurrently produced files',
             'model_fitting':False,'parser_models_loaded':False}
    args.output.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':'passed','synthetic_matching_operand_cases':n,'protected_M4_artifact_count':len(checks)}))


if __name__=='__main__': main()
