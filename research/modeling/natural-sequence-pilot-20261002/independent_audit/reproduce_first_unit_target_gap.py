#!/usr/bin/env python3
"""Synthetic reproducer for all-unit versus supervised-target component support."""
import hashlib
import json
from pathlib import Path
import sys
import torch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
torch.set_num_threads(2)
from audit_synthetic_checks import tiny_catalog, record
from experimental_natural.transforms import fit_transform
from experimental_natural.schema import make_model_packet
from experimental_natural.models import PrefixModel, InputView
from experimental_natural.objectives import family_loss

records = []
for i in range(50):
    values = torch.tensor([[float(i + 1), 1., 1., 1.], [float('nan'), 2., 3., 4.]])
    for arm in ('human', 'chatgpt'):
        records.append(record(q=f'q{i}', component=f'component{i}', arm=arm, values=values))
transform = fit_transform(records, tiny_catalog())
model = PrefixModel('F4', InputView(4, (0, 1, 2, 3)), 4)
losses = []
observed_target_count = 0
for r in records:
    target, observed = transform.target(r.values[1])
    observed_target_count += int(observed[0])
    loss, _ = family_loss(model(make_model_packet(r, 1, transform)), target, observed, transform.families)
    losses.append(loss)
torch.stack(losses).mean().backward()
output_gradient = float(model.head[-1].weight.grad[0].abs().sum())
receipt = {
    'kind': 'synthetic_first_unit_only_target_support_reproducer',
    'issue_reproduced': bool(transform.score_eligible[0]) and observed_target_count == 0 and output_gradient == 0,
    'channel0_recorded_component_support': transform.component_support[0],
    'channel0_score_eligible': bool(transform.score_eligible[0]),
    'channel0_observed_supervised_targets': observed_target_count,
    'channel0_output_weight_absolute_gradient': output_gradient,
    'natural_bodies_read': 0, 'optimizer_steps': 0,
    'transform_source_sha256': hashlib.sha256((ROOT / 'experimental_natural/transforms.py').read_bytes()).hexdigest(),
}
(Path(__file__).parent / 'FIRST_UNIT_TARGET_GAP_RECEIPT.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps(receipt, indent=2))
