#!/usr/bin/env python3
"""Read-only compatibility check against published frozen source (no model import).

Only public source files and manifests are read. No private configuration,
feature cache, record, checkpoint, TEST data, or optimizer is accessed.
"""
import argparse
import ast
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

import run_nuisance_phase as runner


def function_node(path, name):
    tree=ast.parse(path.read_text())
    return next(n for n in tree.body if isinstance(n, (ast.FunctionDef,ast.ClassDef)) and n.name==name)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--source-root',type=Path,required=True)
    args=parser.parse_args()
    root=args.source_root
    base_blob=(root/'STAGED_SOURCE_MANIFEST.json').read_bytes()
    control_blob=(root/'CONTROL_SOURCE_MANIFEST.json').read_bytes()
    if hashlib.sha256(base_blob).hexdigest()!=runner.BASE_SOURCE_MANIFEST_SHA256:
        raise AssertionError('Wrong frozen 20-file source manifest')
    if hashlib.sha256(control_blob).hexdigest()!=runner.CONTROL_SOURCE_MANIFEST_SHA256:
        raise AssertionError('Wrong existing control source manifest')
    base,control=json.loads(base_blob),json.loads(control_blob)
    assert len(base['files'])==20
    for name,sha in control['files'].items():
        assert hashlib.sha256((root/name).read_bytes()).hexdigest()==sha,name
    module=root/'experimental_natural'
    grid_node=function_node(module/'plan.py','registered_run_grid')
    context={'FIXED_SEEDS':(1701,1702,1703)}
    exec(compile(ast.Module(body=[grid_node],type_ignores=[]),'frozen registry','exec'),context)
    registry={r['id']:r for r in context['registered_run_grid']()}
    for rid in runner.CONTROL_ORDER:runner.validate_registry(rid,registry)
    # Evaluate only pure dataclass metadata/properties, never tensor operations.
    view_node=function_node(module/'models.py','InputView')
    context={'dataclass':dataclass}
    exec(compile(ast.Module(body=[view_node],type_ignores=[]),'frozen typed view','exec'),context)
    for mode, values, opportunity in (('mask_opportunity',False,True),('pure_mask',False,False),('length',True,False)):
        view=context['InputView'](3,(0,1),mode)
        assert view.has_values is values and view.has_opportunity is opportunity
    control_builder=ast.unparse(function_node(module/'plan.py','build_control'))
    assert "catalog.structural_indices if mode == 'length'" in control_builder
    assert 'transform.score_eligible' in control_builder
    assert 'InputView(' in control_builder
    config_node=function_node(module/'train.py','TrainingConfig')
    context={'dataclass':dataclass}
    exec(compile(ast.Module(body=[config_node],type_ignores=[]),'frozen optimizer config','exec'),context)
    config=context['TrainingConfig']()
    assert (config.max_epochs,config.patience,config.learning_rate,config.weight_decay,config.batch_questions)==(100,10,.001,.001,32)
    staged=function_node(module/'staged_training.py','train_one_staged')
    args=set(staged.args.kwonlyargs[i].arg for i in range(len(staged.args.kwonlyargs)))
    assert {'phase_started_unix','phase_cpu_baseline','run_cpu_limit_seconds','bindings','resume','reconciled_cpu_seconds','source','shuffle_training'}<=args
    assert 'score_indices' not in args
    print(json.dumps({'status':'passed','frozen20_verified':True,'existing_control_source_verified':True,
                      'registered_recipes_verified':list(runner.CONTROL_ORDER),
                      'full_output_eligibility_and_length_selection_unchanged':True,
                      'typed_view_modes_unchanged':True,'default_optimizer_100epochs_patience10':True,
                      'staged_api_compatible':True,'torch_imported':False,
                      'empirical_data_reads':0,'optimizer_updates':0},indent=2))


if __name__=='__main__':main()
