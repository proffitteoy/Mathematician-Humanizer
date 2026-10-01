"""Pinned, local-only XLM-R extraction for research; no downloads or detector.

The lightweight validation and token-selection functions need only NumPy.
Torch/Transformers are imported only when LocalEncoder is constructed.
"""
from hashlib import sha256
from io import BytesIO
from importlib.metadata import PackageNotFoundError, version
import json
import os
from pathlib import Path
import platform
import sys

import numpy as np


PROFILE_PATH = Path(__file__).with_name('encoder-profile.json')


def load_profile():
    """Load the checked-in, single supported extraction profile."""
    return json.loads(PROFILE_PATH.read_text(encoding='utf-8'))


def verify_model_files(model_dir, profile):
    """Check every pinned artifact before asking a loader to inspect the model.

    The path must already be a local directory; a Hub name is not accepted.
    This does not grant trust to arbitrary caller-supplied profiles.
    """
    root = Path(model_dir).expanduser().resolve()
    if not root.is_dir():
        raise ValueError('local_model_directory_required')
    expected = {item['path'] for item in profile['files']}
    # Added tokenizer/config files could silently change an otherwise pinned load.
    if any(path.name not in expected for path in root.iterdir() if path.is_file()):
        raise ValueError('unlisted_model_directory_file')
    verified = []
    for item in profile['files']:
        relative = Path(item['path'])
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('model_manifest_path')
        path = root / relative
        if not path.is_file() or path.stat().st_size != item['bytes']:
            raise ValueError('model_file_missing_or_size_mismatch:' + item['path'])
        digest = sha256()
        with path.open('rb') as stream:
            for block in iter(lambda: stream.read(1 << 20), b''):
                digest.update(block)
        if digest.hexdigest() != item['sha256']:
            raise ValueError('model_file_hash_mismatch:' + item['path'])
        verified.append(dict(item))
    return root, verified


def _package_version(name):
    try:
        return version(name)
    except PackageNotFoundError:
        return None


def retained_token_mask(token_ids, attention_mask, special_tokens_mask, special_ids):
    """Exclude padding, tokenizer-marked specials, and explicit special IDs."""
    ids = np.asarray(token_ids)
    attention = np.asarray(attention_mask)
    special = np.asarray(special_tokens_mask)
    if ids.ndim != 1 or attention.shape != ids.shape or special.shape != ids.shape:
        raise ValueError('token_mask_shape')
    if not np.issubdtype(ids.dtype, np.integer):
        raise ValueError('token_ids_not_integer')
    if not np.isin(attention, [0, 1]).all() or not np.isin(special, [0, 1]).all():
        raise ValueError('token_mask_not_binary')
    return attention.astype(bool) & ~special.astype(bool) & ~np.isin(ids, special_ids)


def select_token_cloud(hidden, token_ids, attention_mask, special_tokens_mask,
                       special_ids, hidden_size=768):
    hidden = np.asarray(hidden)
    mask = retained_token_mask(token_ids, attention_mask, special_tokens_mask, special_ids)
    if hidden.ndim != 2 or hidden.shape != (len(mask), hidden_size):
        raise ValueError('hidden_state_shape')
    if not np.issubdtype(hidden.dtype, np.floating) or not np.isfinite(hidden).all():
        raise ValueError('hidden_state_not_finite_float')
    return np.ascontiguousarray(hidden[mask]), mask


def cloud_npy_sha256(cloud):
    """Hash the NumPy serialization without writing or publishing a cloud file."""
    stream = BytesIO()
    np.save(stream, cloud, allow_pickle=False)
    return sha256(stream.getvalue()).hexdigest()


def read_source_bytes(path, cap):
    """Reject large files before allocation and bound reads if the file grows."""
    path = Path(path)
    if path.stat().st_size > cap:
        raise ValueError('source_byte_cap')
    with path.open('rb') as stream:
        raw = stream.read(cap + 1)
    if len(raw) > cap:
        raise ValueError('source_byte_cap')
    return raw


class LocalEncoder:
    """One model, one text at a time, CPU float32, final-layer token states.

    Sets process-level offline flags and Torch determinism/thread settings.
    Construct in a dedicated process if a host application needs other settings.
    """

    def __init__(self, model_dir):
        self.profile = load_profile()
        self.root, self.verified_files = verify_model_files(model_dir, self.profile)
        for key in ('HF_HUB_OFFLINE', 'TRANSFORMERS_OFFLINE',
                    'HF_HUB_DISABLE_IMPLICIT_TOKEN', 'HF_HUB_DISABLE_TELEMETRY'):
            os.environ[key] = '1'
        import torch
        import transformers
        from transformers import AutoModel, AutoTokenizer

        self.torch = torch
        self.transformers = transformers
        cfg = self.profile['extraction']
        torch.set_num_threads(cfg['threads'])
        torch.use_deterministic_algorithms(cfg['deterministic_algorithms'])
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.root, local_files_only=True, trust_remote_code=False, token=False)
        self.tokenizer.truncation_side = cfg['truncation_side']
        self.model = AutoModel.from_pretrained(
            self.root, local_files_only=True, trust_remote_code=False, token=False,
            use_safetensors=True, add_pooling_layer=False,
            attn_implementation=cfg['attn_implementation'], dtype=torch.float32)
        self.model.to(device='cpu')
        self.model.eval()
        if self.model.config.hidden_size != cfg['hidden_size']:
            raise ValueError('model_hidden_size_mismatch')

    def encode(self, text):
        """Return (cloud, metadata); never infer provenance or writing quality."""
        if not isinstance(text, str):
            raise ValueError('text_must_be_unicode_string')
        raw = text.encode('utf-8')
        cfg = self.profile['extraction']
        if len(raw) > cfg['max_source_utf8_bytes']:
            raise ValueError('source_byte_cap')
        # Counting the untruncated encoding makes truncation an observed fact.
        full = self.tokenizer(
            text, add_special_tokens=True, truncation=False,
            return_attention_mask=False, return_token_type_ids=False, verbose=False)
        full_count = len(full['input_ids'])
        encoded = self.tokenizer(
            text, add_special_tokens=True, truncation=True,
            max_length=cfg['max_input_tokens'], padding=False,
            return_tensors='pt', return_special_tokens_mask=True)
        special = encoded.pop('special_tokens_mask')[0].cpu().numpy()
        with self.torch.inference_mode():
            hidden = self.model(**encoded).last_hidden_state[0].cpu().numpy()
        cloud, mask = select_token_cloud(
            hidden, encoded['input_ids'][0].cpu().numpy(),
            encoded['attention_mask'][0].cpu().numpy(), special,
            self.tokenizer.all_special_ids, cfg['hidden_size'])
        input_count = int(encoded['input_ids'].shape[1])
        if input_count > cfg['max_input_tokens'] or input_count > full_count:
            raise ValueError('tokenizer_length_inconsistency')
        metadata = {
            'schema': 'topology-encoder-extraction/1',
            'profile_id': self.profile['profile_id'],
            'profile_sha256': sha256(PROFILE_PATH.read_bytes()).hexdigest(),
            'model_repo': self.profile['model_repo'],
            'revision': self.profile['revision'],
            'model_files': self.verified_files,
            'extraction': dict(cfg),
            'context_policy': self.profile['context_policy'],
            'source': {'utf8_sha256': sha256(raw).hexdigest(),
                       'utf8_bytes': len(raw), 'codepoints': len(text)},
            'tokenization': {
                'untruncated_tokens_including_specials': full_count,
                'input_tokens_including_specials_and_padding': input_count,
                'retained_tokens': int(mask.sum()),
                'excluded_special_or_padding_tokens': int((~mask).sum()),
                'truncation_configured': True,
                'was_truncated': full_count > input_count,
                'tokens_removed_by_truncation': full_count - input_count},
            'cloud': {'shape': list(cloud.shape), 'dtype': str(cloud.dtype),
                      'npy_sha256': cloud_npy_sha256(cloud)},
            'runtime': {'python': platform.python_version(),
                        'machine': platform.machine(),
                        'torch': self.torch.__version__,
                        'transformers': self.transformers.__version__,
                        'numpy': np.__version__,
                        'scipy': _package_version('scipy'),
                        'tokenizers': _package_version('tokenizers'),
                        'safetensors': _package_version('safetensors')},
        }
        return cloud, metadata


def main():
    import argparse
    from phd import Config, estimate
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-dir', required=True, type=Path,
                        help='Existing local directory matching encoder-profile.json')
    parser.add_argument('--text-file', required=True, type=Path)
    parser.add_argument('--output', type=Path,
                        help='JSON diagnostics only; cloud arrays are never saved')
    args = parser.parse_args()
    # read_bytes preserves CRLF rather than applying universal-newline conversion.
    cap = load_profile()['extraction']['max_source_utf8_bytes']
    try:
        raw = read_source_bytes(args.text_file, cap)
    except ValueError as exc:
        parser.error(str(exc))
    cloud, report = LocalEncoder(args.model_dir).encode(raw.decode('utf-8'))
    report['phd'] = estimate(cloud, Config())
    content = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    if args.output:
        args.output.write_text(content, encoding='utf-8')
    else:
        sys.stdout.write(content)


if __name__ == '__main__':
    main()
