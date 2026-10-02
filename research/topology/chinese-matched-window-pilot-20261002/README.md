# Chinese topology-feature pilot: scientific release

The result is a small, inconclusive DEV log-loss improvement from direct slope.
Read [CHINESE_PILOT_REPORT.md](CHINESE_PILOT_REPORT.md) and [METHODS.md](METHODS.md).

This new pilot selected 32 TRAIN and 16 DEV prompt/copy components, matched Chinese
prefix windows, and compared five fixed origin-classification arms. All 20
single-schedule sensitivity results are included. One unavailable TRAIN pair stayed
in every fit with paired missing indicators. This development evidence does not
establish writing quality, independent detection performance or next-unit benefit.

## Contents

- Three unchanged scientific modules and model/instrument pins in `source/`; the
  dependency declaration retains all scientific pins with installer details removed
- A science-only synthetic test subset in `source/test_scientific.py`
- Four allowlisted scientific aggregate JSON files in `results/`
- A public aggregate checker and content-hash manifest

Actual runtime, acquisition, resource, approval, execution and internal review
records are excluded. Raw texts, sample identities, per-sample features/predictions,
coefficients, model weights and caches are not redistributed. This package is a
scientific library excerpt; operational launchers are outside its scope.

## Checks

Public arithmetic and release-integrity check (standard library only):

```sh
PYTHONDONTWRITEBYTECODE=1 python verify_aggregate_release.py
```

Synthetic scientific tests in an environment with the pinned scientific dependencies:

```sh
cd source
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m unittest test_scientific
```

These checks do not reproduce raw linguistic or contextual-embedding measurements.
A full reproduction needs authorized input data, the pinned existing linguistic
instrument and the separately acquired model assets. Aggregate arithmetic checks
alone cannot prove those private measurements or the sequence of original actions.
