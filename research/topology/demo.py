"""Synthetic numerical checks only; no language or provenance claims."""
import json
import numpy as np
from phd import Config, estimate

rng = np.random.default_rng(20261001)
cases = {
    'uniform_square_2d': rng.uniform(size=(256, 2)),
    'uniform_cube_3d': rng.uniform(size=(256, 3)),
    'constant_degeneracy_control': np.zeros((100, 3)),
}
print(json.dumps({'scope': 'synthetic numerical smoke checks; not a text experiment',
                  'results': {name: estimate(x, Config()) for name, x in cases.items()}},
                 ensure_ascii=False, indent=2, allow_nan=False))
