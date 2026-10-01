"""Model-free extraction tests: no Torch, Transformers, downloads, or weights."""
from contextlib import contextmanager
from copy import deepcopy
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np

from encoder import (LocalEncoder, cloud_npy_sha256, load_profile,
                     read_source_bytes, retained_token_mask, select_token_cloud,
                     verify_model_files)


class TokenSelectionTests(unittest.TestCase):
    def test_excludes_boundaries_padding_and_literal_special(self):
        ids = [0, 10, 4, 11, 2, 1]
        hidden = np.arange(18, dtype=np.float32).reshape(6, 3)
        cloud, mask = select_token_cloud(
            hidden, ids, [1, 1, 1, 1, 1, 0], [1, 0, 0, 0, 1, 0],
            [0, 1, 2, 4], hidden_size=3)
        np.testing.assert_array_equal(mask, [False, True, False, True, False, False])
        np.testing.assert_array_equal(cloud, hidden[[1, 3]])
        self.assertEqual(cloud.dtype, np.float32)

    def test_empty_content_keeps_two_dimensional_cloud(self):
        cloud, _ = select_token_cloud(np.zeros((2, 3)), [0, 2], [1, 1],
                                     [1, 1], [0, 2], hidden_size=3)
        self.assertEqual(cloud.shape, (0, 3))

    def test_invalid_masks(self):
        for args in [([0, 2], [1], [1, 1]),
                     ([0, 2], [1, 2], [1, 1]),
                     ([0, 2], [1, 1], [1, np.nan]),
                     ([0.0, 2.0], [1, 1], [1, 1])]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                retained_token_mask(*args, [0, 2])

    def test_invalid_hidden_states(self):
        for hidden in [np.zeros((3, 3)), np.zeros((2, 2)),
                       np.full((2, 3), np.nan), np.zeros((2, 3), dtype=int)]:
            with self.subTest(shape=hidden.shape), self.assertRaises(ValueError):
                select_token_cloud(hidden, [0, 2], [1, 1], [1, 1],
                                   [0, 2], hidden_size=3)

    def test_hash_does_not_mutate_input(self):
        cloud = np.arange(12, dtype=np.float32).reshape(4, 3)
        old = cloud.copy()
        self.assertEqual(cloud_npy_sha256(cloud), cloud_npy_sha256(old))
        np.testing.assert_array_equal(cloud, old)


class ManifestTests(unittest.TestCase):
    def test_verified_local_file_and_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / 'model.safetensors'
            path.write_bytes(b'abcd')
            profile = {'files': [{'path': path.name, 'bytes': 4,
                                  'sha256': sha256(b'abcd').hexdigest()}]}
            self.assertEqual(verify_model_files(root, profile)[0], root.resolve())
            path.write_bytes(b'abce')
            with self.assertRaisesRegex(ValueError, 'hash_mismatch'):
                verify_model_files(root, profile)
            path.write_bytes(b'abc')
            with self.assertRaisesRegex(ValueError, 'size_mismatch'):
                verify_model_files(root, profile)

    def test_missing_directory_rejected_without_a_loader(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, 'local_model_directory_required'):
                LocalEncoder(Path(temp) / 'absent')

    def test_unpinned_extra_tokenizer_file_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'added_tokens.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'unlisted_model_directory_file'):
                verify_model_files(root, {'files': []})

    def test_manifest_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            for path in ['../outside', '/tmp/outside']:
                with self.assertRaisesRegex(ValueError, 'model_manifest_path'):
                    verify_model_files(temp, {'files': [{'path': path}]})

    def test_pinned_profile_and_fixture(self):
        profile = load_profile()
        self.assertEqual(profile['revision'], 'e73636d4f797dec63c3081bb6ed5c7b0bb3f2089')
        self.assertEqual(profile['extraction']['max_input_tokens'], 512)
        self.assertTrue(profile['extraction']['use_safetensors'])
        self.assertFalse(profile['extraction']['trust_remote_code'])
        self.assertEqual(len(profile['files']), 6)
        raw = (Path(__file__).parent / 'fixtures' / 'synthetic-zh.txt').read_bytes()
        self.assertEqual(sha256(raw).hexdigest(),
                         'd078ec0651607e3237c0ac6387dcdc25cd5cdf2d629776b8c7865cbeb503322b')


class SourceReadingTests(unittest.TestCase):
    def test_oversized_file_rejected_before_open(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'text.txt'
            path.write_bytes(b'12345')
            with patch.object(Path, 'open', side_effect=AssertionError('must not open')):
                with self.assertRaisesRegex(ValueError, 'source_byte_cap'):
                    read_source_bytes(path, 4)

    def test_bounded_read_catches_growth_after_stat(self):
        stream = BytesIO(b'123456789')
        stream.read = Mock(wraps=stream.read)
        with patch.object(Path, 'stat', return_value=SimpleNamespace(st_size=0)), \
                patch.object(Path, 'open', return_value=stream):
            with self.assertRaisesRegex(ValueError, 'source_byte_cap'):
                read_source_bytes('/fake', 4)
        stream.read.assert_called_once_with(5)

    def test_exact_cap_preserves_raw_newlines(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'text.txt'
            path.write_bytes(b'a\r\nb')
            self.assertEqual(read_source_bytes(path, 4), b'a\r\nb')


class ArrayTensor:
    """Minimal tensor facade so these tests do not import Torch."""
    def __init__(self, value): self.value = np.asarray(value)
    @property
    def shape(self): return self.value.shape
    def __getitem__(self, key): return ArrayTensor(self.value[key])
    def cpu(self): return self
    def numpy(self): return self.value


class FakeTokenizer:
    all_special_ids = [0, 1, 2]
    def __call__(self, text, **kwargs):
        content = list(range(10, 10 + len(text)))
        if not kwargs['truncation']:
            return {'input_ids': [0] + content + [2]}
        assert self.truncation_side == 'right'
        assert kwargs['max_length'] == 512 and kwargs['padding'] is False
        ids = [0] + content[:510] + [2]
        return {'input_ids': ArrayTensor([ids]),
                'attention_mask': ArrayTensor([[1] * len(ids)]),
                'special_tokens_mask': ArrayTensor([[1] + [0] * (len(ids) - 2) + [1]])}


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.profile = deepcopy(load_profile())
        torch = SimpleNamespace(__version__='fake', float32='float32', in_inference=False,
                                set_num_threads=Mock(), use_deterministic_algorithms=Mock())
        @contextmanager
        def inference_mode():
            torch.in_inference = True
            try:
                yield
            finally:
                torch.in_inference = False
        torch.inference_mode = inference_mode
        class FakeModel:
            config = SimpleNamespace(hidden_size=768)
            def to(self, **kwargs):
                assert kwargs == {'device': 'cpu'}
            def eval(self): self.training = False
            def __call__(self, **kwargs):
                assert not self.training and torch.in_inference
                n = kwargs['input_ids'].shape[1]
                return SimpleNamespace(last_hidden_state=ArrayTensor(
                    np.arange(n * 768, dtype=np.float32).reshape(1, n, 768)))
        self.model_loader = Mock(return_value=FakeModel())
        self.tokenizer_loader = Mock(return_value=FakeTokenizer())
        transformers = SimpleNamespace(
            __version__='fake', AutoTokenizer=SimpleNamespace(from_pretrained=self.tokenizer_loader),
            AutoModel=SimpleNamespace(from_pretrained=self.model_loader))
        self.patches = [patch.dict('sys.modules', torch=torch, transformers=transformers),
                        patch('encoder.verify_model_files', return_value=(Path('/fake'), [])),
                        patch.dict('os.environ', {}, clear=False)]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)
        self.encoder = LocalEncoder('/fake')

    def test_loader_safety_settings(self):
        for loader in [self.model_loader, self.tokenizer_loader]:
            settings = loader.call_args.kwargs
            self.assertTrue(settings['local_files_only'])
            self.assertFalse(settings['trust_remote_code'])
            self.assertFalse(settings['token'])
        self.assertTrue(self.model_loader.call_args.kwargs['use_safetensors'])
        self.assertEqual(self.model_loader.call_args.kwargs['dtype'], 'float32')

    def test_actual_truncation_and_short_input(self):
        for length in [0, 5, 510, 600]:
            cloud, metadata = self.encoder.encode('甲' * length)
            tok = metadata['tokenization']
            self.assertEqual(cloud.shape, (min(length, 510), 768))
            self.assertEqual(tok['untruncated_tokens_including_specials'], length + 2)
            self.assertEqual(tok['was_truncated'], length > 510)
            self.assertEqual(tok['tokens_removed_by_truncation'], max(0, length - 510))
            self.assertEqual(metadata['source']['utf8_bytes'], 3 * length)

    def test_source_not_normalized(self):
        text = '甲\r\n乙  丙'
        _, metadata = self.encoder.encode(text)
        self.assertEqual(metadata['source']['utf8_sha256'], sha256(text.encode()).hexdigest())

    def test_nontext_and_oversized_source_rejected(self):
        for text, reason in [(b'bytes', 'text_must'), ('甲' * 349526, 'source_byte_cap')]:
            with self.assertRaisesRegex(ValueError, reason):
                self.encoder.encode(text)


if __name__ == '__main__':
    unittest.main()
