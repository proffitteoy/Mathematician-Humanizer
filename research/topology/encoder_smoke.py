"""Reproduce the checked-in constructed-Chinese pipeline smoke diagnostics."""
import argparse
from hashlib import sha256
import json
from pathlib import Path

from encoder import LocalEncoder
from phd import Config, estimate


ROOT = Path(__file__).parent


def run(model_dir):
    raw = (ROOT / 'fixtures' / 'synthetic-zh.txt').read_bytes()
    if sha256(raw).hexdigest() != 'd078ec0651607e3237c0ac6387dcdc25cd5cdf2d629776b8c7865cbeb503322b':
        raise ValueError('synthetic_fixture_hash_mismatch')
    encoder = LocalEncoder(model_dir)
    text = raw.decode('utf-8')
    cloud, extraction = encoder.encode(text)
    repeated, second = encoder.encode(text)
    if extraction['cloud']['npy_sha256'] != second['cloud']['npy_sha256']:
        raise ValueError('same_process_encoder_repeat_mismatch')
    short_cloud, short = encoder.encode('编码检查。')
    short_phd = estimate(short_cloud, Config())
    if short_phd['reason'] != 'fewer_than_50_points':
        raise ValueError('short_control_did_not_abstain')
    long_cloud, long = encoder.encode(text * 3)
    if not long['tokenization']['was_truncated'] or \
            long['tokenization']['input_tokens_including_specials_and_padding'] != 512 or \
            not 0 < len(long_cloud) <= 510:
        raise ValueError('long_control_truncation_mismatch')
    return {
        'schema': 'topology-encoder-smoke/1',
        'scope': 'Constructed Chinese pipeline check; not natural-text or human/AI validation',
        'fixture': {'path': 'fixtures/synthetic-zh.txt',
                    'origin': 'Assistant-constructed technical prose for this pipeline smoke test',
                    'source_synthetic': True, 'real_author_label': None},
        'extraction': extraction,
        'same_process_repeat': {'cloud_sha256_equal': True, 'shape': list(repeated.shape)},
        'phd': estimate(cloud, Config()),
        'controls': {
            'short_constructed': {
                'definition': 'Literal constructed text: 编码检查。',
                'source': short['source'], 'tokenization': short['tokenization'],
                'cloud': short['cloud'], 'phd': short_phd},
            'repeated_for_truncation': {
                'definition': 'fixtures/synthetic-zh.txt concatenated three times',
                'source': long['source'], 'tokenization': long['tokenization'],
                'cloud': long['cloud'],
                'purpose': 'Verify actual truncation and retained-token limits only'}},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-dir', required=True, type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    content = json.dumps(run(args.model_dir), ensure_ascii=False,
                         indent=2, allow_nan=False) + '\n'
    if args.output:
        args.output.write_text(content, encoding='utf-8')
    else:
        print(content, end='')


if __name__ == '__main__':
    main()
