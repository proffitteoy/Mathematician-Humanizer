"""Independent alpha=1 H0/MST scaling estimator; no encoder or detector.

Published mathematical construction: Tulchinskii et al., NeurIPS 2023.
Source/protocol differences and inference limits are documented in README.md.
"""
from dataclasses import dataclass, asdict
import numpy as np
import scipy
from scipy.spatial.distance import cdist


@dataclass(frozen=True)
class Config:
    protocol: str = 'paper_prose_v1'
    seed: int = 20261001
    reruns: int = 3
    max_cloud_points: int = 512
    slope_margin: float = 0.001


def mst_edges(distance):
    """Dense Prim, retaining legitimate zero-length edges (including duplicates)."""
    d = np.asarray(distance, dtype=float)
    if d.ndim != 2 or d.shape[0] != d.shape[1] or len(d) < 1:
        raise ValueError('distance_matrix_shape')
    if not np.all(np.isfinite(d)) or np.any(d < 0):
        raise ValueError('distance_matrix_values')
    if not np.allclose(d, d.T, rtol=1e-12, atol=1e-14) or not np.allclose(np.diag(d), 0):
        raise ValueError('distance_matrix_symmetry_or_diagonal')
    n = len(d)
    used = np.zeros(n, dtype=bool)
    best = np.full(n, np.inf)
    best[0] = 0
    edges = []
    for step in range(n):
        candidates = np.where(used, np.inf, best)
        v = int(np.argmin(candidates))
        if not np.isfinite(candidates[v]):
            raise ValueError('disconnected_distance_matrix')
        if step:
            edges.append(float(best[v]))
        used[v] = True
        best = np.minimum(best, d[v])
    return np.asarray(edges)


def sample_sizes(n, protocol):
    if protocol == 'paper_prose_v1':
        # Explicit endpoint convention: nearest integer, eight positions, 40 to n.
        sizes = np.rint(np.linspace(40, n, 8)).astype(int).tolist()
    elif protocol == 'gptid_notebook_v1':
        step = (n - 40) // 7
        if step <= 0:
            return []
        sizes = list(range(40, n - step, step))
    elif protocol == 'gptid_class_defaults_v1':
        sizes = list(range(50, 512, 40))
    else:
        raise ValueError('unknown_protocol')
    return sizes


def draws(n, size, protocol):
    if protocol == 'paper_prose_v1':
        return 7
    if protocol == 'gptid_notebook_v1':
        return 3 if n <= 2 * size else 9
    return 3 if n <= 2 * size else 7


def make_plan(n, sizes, config):
    children = np.random.SeedSequence(config.seed).spawn(config.reruns)
    result = []
    for child in children:
        rng = np.random.default_rng(child)
        result.append([[rng.choice(n, size=s, replace=False).tolist()
                        for _ in range(draws(n, s, config.protocol))] for s in sizes])
    return result


def _validate_plan(plan, n, sizes, config):
    if len(plan) != config.reruns:
        raise ValueError('plan_reruns')
    for run in plan:
        if len(run) != len(sizes):
            raise ValueError('plan_scales')
        for size, subsets in zip(sizes, run):
            if len(subsets) != draws(n, size, config.protocol):
                raise ValueError('plan_draws')
            for ids in subsets:
                if len(ids) != size or any(type(i) is not int or not 0 <= i < n for i in ids):
                    raise ValueError('plan_indices')
                if len(set(ids)) != size:
                    raise ValueError('plan_replacement')


def estimate(points, config=Config(), plan=None):
    """Return one document-cloud estimate and diagnostics, never an AI likelihood.

    plan is an optional nested integer-index schedule [rerun][scale][draw][index].
    Dispersion across reruns is conditional Monte Carlo variation, not a CI.
    """
    if type(config.reruns) is not int or not 1 <= config.reruns <= 32:
        raise ValueError('reruns_out_of_bounds')
    if type(config.seed) is not int or config.seed < 0:
        raise ValueError('invalid_seed')
    if type(config.max_cloud_points) is not int or not 50 <= config.max_cloud_points <= 2048:
        raise ValueError('resource_cap_out_of_bounds')
    if not np.isfinite(config.slope_margin) or not 0 < config.slope_margin < 0.5:
        raise ValueError('invalid_slope_margin')
    x = np.asarray(points, dtype=float)
    if x.ndim != 2 or x.shape[1] < 1:
        raise ValueError('point_cloud_shape')
    if not np.all(np.isfinite(x)):
        raise ValueError('point_cloud_nonfinite')
    n = len(x)
    report = {'schema': 'phd-replication/0.1', 'status': 'unavailable', 'dimension': None,
              'alpha': 1.0, 'metric': 'euclidean', 'n_points': n,
              'ambient_dimension': x.shape[1], 'config': asdict(config),
              'plan_source': 'caller_supplied' if plan is not None else 'seeded_local_rng',
              'uncertainty_scope': 'conditional Monte Carlo dispersion, not a population confidence interval',
              'numpy_version': np.__version__, 'scipy_version': scipy.__version__}
    if n < 50:
        return dict(report, reason='fewer_than_50_points')
    if n > config.max_cloud_points:
        return dict(report, reason='resource_cap')
    sizes = sample_sizes(n, config.protocol)
    report['sample_sizes'] = sizes
    if len(set(sizes)) < 4 or len(set(sizes)) != len(sizes) or min(sizes) < 2 or max(sizes) > n:
        return dict(report, reason='invalid_or_insufficient_sampling_grid')
    unique_n = int(len(np.unique(x, axis=0)))
    report['distinct_points'] = unique_n
    if unique_n == 1:
        return dict(report, reason='zero_or_nonfinite_mst_energy')
    if unique_n < min(sizes):
        return dict(report, reason='insufficient_distinct_points')
    if plan is None:
        plan = make_plan(n, sizes, config)
    _validate_plan(plan, n, sizes, config)
    distance = cdist(x, x, metric='euclidean')
    if not np.all(np.isfinite(distance)):
        return dict(report, reason='distance_overflow')
    all_runs = []
    lx = np.log(np.asarray(sizes, dtype=float))
    centered = lx - lx.mean()
    for run in plan:
        medians, energies = [], []
        for subsets in run:
            vals = []
            for ids in subsets:
                vals.append(float(mst_edges(distance[np.ix_(ids, ids)]).sum()))
            energies.append(vals)
            medians.append(float(np.median(vals)))
        if np.any(np.asarray(medians) <= 0) or not np.all(np.isfinite(medians)):
            return dict(report, reason='zero_or_nonfinite_mst_energy', completed_runs=all_runs)
        ly = np.log(medians)
        slope = float(centered @ (ly - ly.mean()) / (centered @ centered))
        intercept = float(ly.mean() - slope * lx.mean())
        resid = ly - (intercept + slope * lx)
        total = float(((ly - ly.mean()) ** 2).sum())
        r2 = None if total == 0 else float(1 - (resid @ resid) / total)
        all_runs.append({'slope': slope, 'intercept': intercept, 'r_squared': r2,
                         'median_energies': medians, 'draw_energies': energies})
    slopes = np.asarray([r['slope'] for r in all_runs])
    mean = float(slopes.mean())
    report.update(runs=all_runs, mean_slope=mean,
                  slope_range=[float(slopes.min()), float(slopes.max())],
                  slope_sd=float(slopes.std(ddof=1)) if len(slopes) > 1 else None,
                  formula='1 / (1 - mean(rerun slopes))',
                  distinct_points=int(len(np.unique(x, axis=0))))
    if not np.isfinite(mean) or mean < 0 or mean >= 1 - config.slope_margin:
        return dict(report, reason='slope_outside_stable_profile')
    if np.any(slopes < 0) or np.any(slopes >= 1 - config.slope_margin):
        return dict(report, reason='a_rerun_outside_stable_profile')
    return dict(report, status='ok', reason=None, dimension=float(1 / (1 - mean)),
                rerun_dimensions=[float(1 / (1 - s)) for s in slopes],
                claim='finite-cloud scaling estimate; not an intrinsic human-style constant')
