"""Independent bounded paired PHD pilot; no upstream scripts or model remote code."""
import os
os.environ['HF_HOME'] = os.path.join(os.path.dirname(__file__), 'local-hf-cache')
for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '2'
for key in ('HF_HUB_OFFLINE', 'TRANSFORMERS_OFFLINE', 'HF_HUB_DISABLE_TELEMETRY', 'HF_HUB_DISABLE_IMPLICIT_TOKEN'):
    os.environ[key] = '1'
import hashlib
import json
from pathlib import Path
import resource
import sys
import time
import zipfile

import numpy as np
import torch
import transformers
from transformers import RobertaModel, RobertaTokenizer

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'recovered'))
from phd import Config, estimate

SELECTION_HASH = 'a4b31b5982c5107adab88a2fca25989c19df4e3b193ceedea50ba946cce5f1b5'
SEEDS = (20261002, 20261003)

def digest(data):
    return hashlib.sha256(data).hexdigest()

def clean(text):
    # Exact released notebook cleaning: each replace occurs once.
    return text.replace('\n', ' ').replace('  ', ' ')

def main():
    started = time.monotonic()
    os.sched_setaffinity(0, sorted(os.sched_getaffinity(0))[:2])
    torch.set_num_threads(2)
    torch.set_num_interop_threads(1)
    torch.manual_seed(SEEDS[0])
    torch.use_deterministic_algorithms(True)
    raw = (ROOT / 'selection-manifest.json').read_bytes()
    assert digest(raw) == SELECTION_HASH
    selection = json.loads(raw)
    manifest = json.loads((ROOT / 'model-manifest.json').read_text())
    for item in manifest['files']:
        b = (ROOT / 'roberta-base' / item['path']).read_bytes()
        assert len(b) == item['bytes'] and digest(b) == item['sha256']
    del b
    tokenizer = RobertaTokenizer.from_pretrained(ROOT / 'roberta-base', local_files_only=True)
    tokenizer.truncation_side = 'right'
    model = RobertaModel.from_pretrained(ROOT / 'roberta-base', local_files_only=True,
                use_safetensors=True, add_pooling_layer=False, attn_implementation='eager')
    model = model.to(device='cpu', dtype=torch.float32).eval()
    assert model.config.hidden_size == 768

    def encode(ids):
        input_ids = tokenizer.build_inputs_with_special_tokens(ids)
        assert len(input_ids) <= 512
        x = torch.tensor([input_ids], dtype=torch.long)
        with torch.inference_mode():
            h = model(input_ids=x, attention_mask=torch.ones_like(x)).last_hidden_state[0, 1:-1].numpy()
        assert h.shape == (len(ids), 768) and np.isfinite(h).all()
        return h.copy()

    records = []
    for domain in selection['domains']:
        zpath = ROOT / 'private-inputs' / ('human_gpt3_davinci_003_' + domain['domain'] + '.zip')
        assert digest(zpath.read_bytes()) == domain['source_archive_sha256']
        with zipfile.ZipFile(zpath) as z:
            rows = json.loads(z.read(z.namelist()[0]))
        for chosen in domain['selected']:
            row = rows[chosen['index']]
            assert row['split'] == 'train' and digest(row['prefix'].encode()) == chosen['prefix_sha256']
            texts = {'human': row['gold_completion'], 'ai': row['gen_completion']}
            assert digest(texts['human'].encode()) == chosen['gold_sha256']
            assert digest(texts['ai'].encode()) == chosen['gen_sha256']
            ids = {label: tokenizer.encode(clean(text), add_special_tokens=False) for label, text in texts.items()}
            matched_n = min(256, len(ids['human']), len(ids['ai']))
            pair = {'domain': domain['domain'], 'source_index': chosen['index'],
                    'prefix_sha256': chosen['prefix_sha256'], 'matched_n': matched_n, 'texts': {}}
            for label in ('human', 'ai'):
                full_ids = ids[label]
                record = {'source_sha256': digest(texts[label].encode()),
                          'cleaned_sha256': digest(clean(texts[label]).encode()),
                          'untruncated_content_tokens': len(full_ids),
                          'original_window_content_tokens': min(len(full_ids), 510),
                          'original_window_truncated': len(full_ids) > 510,
                          'contains_internal_special_ids': any(x in tokenizer.all_special_ids for x in full_ids),
                          'conditions': {}}
                for condition, count in [('original_window', min(510, len(full_ids))), ('matched_reencoded', matched_n)]:
                    cloud = encode(full_ids[:count])
                    reports = {}
                    for seed in SEEDS:
                        reports['notebook_seed_' + str(seed)] = estimate(cloud, Config(protocol='gptid_notebook_v1', seed=seed))
                    if condition == 'original_window':
                        reports['paper_prose_seed_' + str(SEEDS[0])] = estimate(cloud, Config(protocol='paper_prose_v1', seed=SEEDS[0]))
                    record['conditions'][condition] = {'content_tokens': count,
                        'cloud_float32_c_order_sha256': digest(cloud.tobytes()), 'phd': reports}
                pair['texts'][label] = record
            records.append(pair)
            elapsed = time.monotonic() - started
            rss_kib = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            assert elapsed < 1800, 'wall_time_budget_exceeded'
            assert rss_kib < 3 * 1024 * 1024, 'rss_budget_exceeded'
            result = {'status': 'running', 'selection_sha256': SELECTION_HASH,
                'model_revision': manifest['revision'], 'elapsed_seconds': elapsed,
                'max_rss_kib': rss_kib, 'records': records,
                'runtime': {'torch': torch.__version__, 'transformers': transformers.__version__, 'numpy': np.__version__, 'python': sys.version}}
            (ROOT / 'paired-pilot-results.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
            print(json.dumps({'completed_pairs': len(records), 'domain': domain['domain'], 'elapsed_seconds': elapsed, 'max_rss_kib': rss_kib}), flush=True)
        del rows
    result['status'] = 'completed'
    (ROOT / 'paired-pilot-results.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')

if __name__ == '__main__':
    main()
