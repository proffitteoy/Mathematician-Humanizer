"""Consume the independent PH0 report without an encoder or implicit download."""
import math
from .contracts import Measurement, TopologySnapshot, require, finite


TOPOLOGY_CHANNELS = ('dimension', 'mean_slope', 'slope_sd', 'mean_r_squared', 'log_points')


def from_phd_report(report, *, prefix_end, input_prefix_end, representation_id):
    require(report.get('schema') == 'phd-replication/0.1', 'unknown_topology_schema')
    require(report.get('alpha') == 1.0 and report.get('metric') == 'euclidean',
            'unsupported_topology_geometry')
    profile = report.get('config', {}).get('protocol')
    require(profile in {'paper_prose_v1', 'gptid_notebook_v1', 'gptid_class_defaults_v1'},
            'unknown_topology_profile')
    status = report.get('status')
    require(status in {'ok', 'unavailable'}, 'invalid_topology_report_status')
    reason = report.get('reason')
    if status == 'ok':
        dim, slope, n = report.get('dimension'), report.get('mean_slope'), report.get('n_points')
        require(finite(dim) and finite(slope) and 0 <= slope < 1 and
                type(n) is int and n >= 50, 'invalid_topology_estimate')
        require(math.isclose(dim, 1 / (1 - slope), rel_tol=1e-9), 'inconsistent_topology_dimension')
        r2 = [r['r_squared'] for r in report.get('runs', []) if r.get('r_squared') is not None]
        vals = (dim, slope, report.get('slope_sd'), sum(r2) / len(r2) if r2 else None,
                math.log1p(n))
        reason = None
    else:
        require(isinstance(reason, str) and bool(reason), 'topology_unavailable_reason_required')
        vals = (None,) * 5
    features = Measurement(tuple(vals), tuple(1.0 if v is not None else None for v in vals),
                           tuple(None if v is not None else 'numerical_unavailable' for v in vals))
    result = TopologySnapshot(prefix_end, input_prefix_end, representation_id, profile,
                              features, status, reason)
    result.validate()
    return result
