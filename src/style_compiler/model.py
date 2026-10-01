"""Experimental population reference model, gated on eligible real data.

This is a transparent ridge residual baseline, not the hierarchical model in the
research protocol. No origin classifier, author model, probability, likelihood
ratio, calibrated percentile, or automatic intervention target is provided.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass
import hashlib
import json
import math
from typing import Any
from .contracts import BUNDLE_VERSION, FEATURE_VERSION, Document
from .features import extract
from .leakage import Partition, connected_groups, validate_partition


@dataclass(frozen=True)
class ModelSpec:
    feature_ids: tuple[str, ...] = ("F013", "F016", "F024")
    ridge: float = 1.0
    covariance_shrinkage: float = .2
    min_documents: int = 36
    min_independent_groups: int = 12
    min_context_groups: int = 4

    def __post_init__(self) -> None:
        if not self.feature_ids or len(set(self.feature_ids)) != len(self.feature_ids):
            raise ValueError("Model features must be nonempty and unique")
        if not math.isfinite(self.ridge) or self.ridge <= 0:
            raise ValueError("A positive finite ridge penalty is required")
        if not 0 < self.covariance_shrinkage <= 1:
            raise ValueError("covariance_shrinkage must lie in (0,1]")
        if any(type(value) is not int for value in (self.min_documents, self.min_independent_groups, self.min_context_groups)):
            raise ValueError("Support thresholds must be integers")
        if self.min_documents < 3 or self.min_independent_groups < 3 or self.min_context_groups < 2:
            raise ValueError("Support policy must require at least 3 documents/groups and 2 context groups")


def eligibility_reasons(document: Document) -> list[str]:
    p = document.provenance
    reasons = []
    if p.is_synthetic or p.cohort == "synthetic_test":
        reasons.append("Synthetic fixtures are ineligible for empirical reference fitting")
    if p.cohort not in {"H_G", "A_G", "A_H", "A_C"}:
        reasons.append("Only non-personal, explicitly labeled research cohorts are eligible")
    if not p.rights_verified:
        reasons.append("Rights basis has not been verified")
    if not p.provenance_verified:
        reasons.append("Source/provenance has not been verified")
    if p.cohort == "H_G" and (not p.author_id or p.assistance_status != "unassisted"):
        reasons.append("H_G requires a nonempty caller-supplied author ID and assistance_status='unassisted'; these declarations do not authenticate a person or verify assistance history")
    if p.cohort in {"A_G", "A_H", "A_C"} and (not p.generator_id or not document.leakage.prompt_family_id):
        reasons.append("Generated cohorts need a generator snapshot ID and prompt-family ID")
    return reasons


def _numpy():
    try:
        import numpy as np
    except ImportError as exc:
        raise RuntimeError("Optional modeling capability unavailable: install style-compiler[model]") from exc
    return np


def _weighted_ridge(x, y, weights, penalty: float):
    """Numerical primitive; synthetic-array tests verify algebra, not validity."""
    np = _numpy()
    x, y, weights = np.asarray(x, float), np.asarray(y, float), np.asarray(weights, float)
    if x.ndim != 2 or y.ndim != 2 or len(x) != len(y) or len(x) != len(weights):
        raise ValueError("Incompatible design dimensions")
    if not np.isfinite(x).all() or not np.isfinite(y).all() or not np.isfinite(weights).all() or (weights <= 0).any():
        raise ValueError("Nonfinite observations or nonpositive weights")
    regularizer = np.eye(x.shape[1]) * penalty
    regularizer[0, 0] = 0  # The intercept is unpenalized.
    return np.linalg.solve(x.T @ (weights[:, None] * x) + regularizer,
                           x.T @ (weights[:, None] * y))


def _intersect_components(groups: list[list[str]], selected_ids: set[str]) -> list[list[str]]:
    """Retain full-corpus connectivity when selecting a cohort or partition."""
    return [selected for group in groups if (selected := [item for item in group if item in selected_ids])]


def fit_population_model(documents: list[Document], partition: Partition, *,
                         cohort: str, spec: ModelSpec | None = None) -> dict[str, Any]:
    """Fit on the training partition only, or return an explicit abstention.

    Callers must supply a corpus reviewed for rights, provenance and derivative
    relationships. Flags are declarations, not automatic proof. Full corpus IDs
    are required to revalidate the split before any transformations are fitted.
    """
    spec = spec or ModelSpec()
    validate_partition(documents, partition)
    base = {"schema_version": "population-model/1.0.0", "status": "unavailable",
            "maturity": "experimental", "cohort": cohort, "spec": asdict(spec),
            "model": None, "calibration": None, "author_profile": None,
            "limitations": ["Not a hierarchical count/proportion measurement model",
                            "Fixed regularization and support gates are provisional, not validated",
                            "No uncertainty interval, source probability, percentile, or causal effect"]}
    if cohort not in {"H_G", "A_G", "A_H", "A_C"}:
        return base | {"reason": "Requested cohort is not eligible for population fitting"}
    if not {"author", "prompt"}.issubset(partition.holdout_axes):
        return base | {"reason": "This baseline requires declared author and prompt-family separation"}
    train = [d for d in documents if partition.assignments[d.document_id] == "train" and d.provenance.cohort == cohort]
    invalid = {d.document_id: eligibility_reasons(d) for d in train if eligibility_reasons(d)}
    if invalid:
        return base | {"reason": "Ineligible training provenance", "excluded": invalid}
    if not train:
        return base | {"reason": "No eligible real training documents supplied"}
    bundles = [extract(d) for d in train]
    unsupported = {bundle["document_id"]: [f for f in spec.feature_ids
                    if f not in bundle["features"] or not bundle["features"][f]["eligible_for_comparison"]]
                   for bundle in bundles}
    unsupported = {key: value for key, value in unsupported.items() if value}
    if unsupported:
        return base | {"reason": "Selected features lack comparison support; no imputation performed", "excluded": unsupported}
    selected_ids = {d.document_id for d in train}
    # Preserve paths through other cohorts: dropping bridge documents must not
    # manufacture new independent components.
    full_groups = connected_groups(documents, partition.holdout_axes, partition.near_duplicate_threshold)
    groups = _intersect_components(full_groups, selected_ids)
    if len(train) < spec.min_documents or len(groups) < spec.min_independent_groups:
        return base | {"reason": "Insufficient independent eligible training support",
                       "training_documents": len(train), "independent_groups": len(groups)}
    contexts = sorted({d.context.key() for d in train})
    group_for = {item: gi for gi, group in enumerate(groups) for item in group}
    support = []
    for context in contexts:
        rows = [i for i, d in enumerate(train) if d.context.key() == context]
        ng = len({group_for[train[i].document_id] for i in rows})
        if ng < spec.min_context_groups:
            return base | {"reason": "Insufficient independent groups in a genre/topic/task/language stratum",
                           "context": list(context), "independent_groups": ng}
        lengths = [bundles[i]["counts"]["content_chars"] for i in rows]
        support.append({"context": list(context), "n": len(rows), "groups": ng,
                        "length_min": min(lengths), "length_max": max(lengths)})
    # Exact joint-context dummy variables, plus continuous log content length.
    raw_lengths = [math.log1p(b["counts"]["content_chars"]) for b in bundles]
    np = _numpy()
    weights = np.asarray([1 / len(groups[group_for[d.document_id]]) for d in train])
    # Each leakage component has total weight one; this does not erase within-
    # component dependence or substitute for cluster-aware uncertainty intervals.
    length_center = float(np.average(raw_lengths, weights=weights))
    length_scale = float(np.sqrt(np.average((np.asarray(raw_lengths) - length_center) ** 2, weights=weights)))
    if not length_scale:
        return base | {"reason": "Length variation absent; conditional length response is not identifiable"}
    x = np.asarray([[1., (raw_lengths[i] - length_center) / length_scale]
                    + [float(d.context.key() == c) for c in contexts[1:]] for i, d in enumerate(train)])
    y = np.asarray([[b["features"][f]["value"] for f in spec.feature_ids] for b in bundles])
    center = np.average(y, weights=weights, axis=0)
    scale = np.sqrt(np.average((y - center) ** 2, weights=weights, axis=0))
    if (scale == 0).any():
        return base | {"reason": "A selected training feature is constant; predeclare a reduced feature model"}
    z = (y - center) / scale
    beta = _weighted_ridge(x, z, weights, spec.ridge)
    residuals = z - x @ beta
    covariance = (residuals.T @ (weights[:, None] * residuals)) / weights.sum()
    if (np.diag(covariance) <= 1e-14).any():
        return base | {"reason": "Residual variance is not identifiable for a selected feature"}
    alpha = spec.covariance_shrinkage
    covariance = (1 - alpha) * covariance + alpha * np.diag(np.diag(covariance))
    manifest = sorted((d.document_id, b["text_sha256"]) for d, b in zip(train, bundles))
    model = {"feature_schema_version": FEATURE_VERSION,
             "projection": "all_input_unicode_LN/1.0.0", "feature_ids": list(spec.feature_ids), "contexts": [list(c) for c in contexts],
             "feature_center": center.tolist(), "feature_scale": scale.tolist(),
             "length_center": length_center, "length_scale": length_scale,
             "coefficients": beta.tolist(), "residual_covariance": covariance.tolist(),
             "covariance_source": "pooled population training residuals; never an author covariance",
             "conditioning": ["language", "genre", "topic", "task", "log1p(content_chars)"],
             "training_documents": len(train), "independent_groups": len(groups),
             "training_manifest_sha256": hashlib.sha256(json.dumps(manifest, ensure_ascii=False).encode()).hexdigest(),
             "support": support}
    return base | {"status": "fitted_experimental", "reason": None, "model": model}


def _quadratic_residual(residual, covariance) -> float:
    """Finite SPD quadratic form; a synthetic-array test is not a corpus fit."""
    np = _numpy()
    residual, covariance = np.asarray(residual, float), np.asarray(covariance, float)
    if residual.ndim != 1 or covariance.shape != (len(residual), len(residual)):
        raise ValueError("Invalid residual or covariance dimensions")
    if not np.isfinite(residual).all() or not np.isfinite(covariance).all():
        raise ValueError("Nonfinite residual or covariance")
    if not np.allclose(covariance, covariance.T, rtol=1e-10, atol=1e-12):
        raise ValueError("Covariance must be symmetric")
    try:
        np.linalg.cholesky(covariance)
        distance = float(residual @ np.linalg.solve(covariance, residual))
    except np.linalg.LinAlgError as exc:
        raise ValueError("Covariance must be positive definite") from exc
    if not math.isfinite(distance) or distance < -1e-10:
        raise ValueError("Invalid numerical distance")
    return max(0., distance)


def assess(bundle: dict, fitted: dict) -> dict:
    result = {"status": "unavailable", "distance_squared": None, "percentile": None,
              "human_probability": None, "author_probability": None, "calibrated": False}
    if not isinstance(bundle, dict) or not isinstance(fitted, dict):
        return result | {"reason": "Bundle and model must be objects"}
    model = fitted.get("model")
    if fitted.get("status") != "fitted_experimental" or not isinstance(model, dict):
        return result | {"reason": "No fitted eligible population model"}
    try:
        if (fitted.get("schema_version") != "population-model/1.0.0"
                or bundle.get("schema_version") != BUNDLE_VERSION
                or bundle.get("feature_schema_version") != FEATURE_VERSION
                or model.get("feature_schema_version") != FEATURE_VERSION
                or model.get("projection") != "all_input_unicode_LN/1.0.0"
                or bundle.get("segmentation", {}).get("projection") != model.get("projection")):
            raise ValueError("Unsupported or mismatched measurement/model version or projection")
        context = [bundle["context"][key] for key in ("language", "genre", "topic", "task")]
        support = next((s for s in model["support"] if s["context"] == context), None)
        length = bundle["counts"]["content_chars"]
        if type(length) is not int or length < 0:
            raise ValueError("Invalid content length")
        if support is None or not support["length_min"] <= length <= support["length_max"]:
            return result | {"reason": "Out-of-support context or length; no extrapolation"}
        features = [bundle["features"].get(f) for f in model["feature_ids"]]
        if any(f is None or f["eligible_for_comparison"] is not True or f["value"] is None for f in features):
            return result | {"reason": "Missing or insufficient features; distance subspace is frozen"}
        np = _numpy()
        center, scale = np.asarray(model["feature_center"], float), np.asarray(model["feature_scale"], float)
        beta = np.asarray(model["coefficients"], float)
        values = np.asarray([f["value"] for f in features], float)
        if (center.shape != values.shape or scale.shape != values.shape or values.ndim != 1
                or not len(values) or not np.isfinite(values).all() or not np.isfinite(center).all()
                or not np.isfinite(scale).all() or (scale <= 0).any()):
            raise ValueError("Invalid/nonfinite feature values or training scales")
        if (not math.isfinite(model["length_center"]) or not math.isfinite(model["length_scale"])
                or model["length_scale"] <= 0):
            raise ValueError("Invalid length scaling")
        contexts = model["contexts"]
        if not contexts or context not in contexts or any(len(c) != 4 for c in contexts):
            raise ValueError("Invalid context design")
        x = np.asarray([1., (math.log1p(length) - model["length_center"]) / model["length_scale"]]
                       + [float(context == c) for c in contexts[1:]])
        if beta.shape != (len(x), len(values)) or not np.isfinite(beta).all():
            raise ValueError("Invalid coefficients")
        expected_z = x @ beta
        residual = (values - center) / scale - expected_z
        distance = _quadratic_residual(residual, model["residual_covariance"])
        expected = expected_z * scale + center
        if not np.isfinite(expected).all():
            raise ValueError("Nonfinite conditional mean")
    except (KeyError, TypeError, ValueError, RuntimeError) as exc:
        return result | {"reason": f"Invalid or unavailable assessment input: {exc}"}
    return result | {"status": "uncalibrated_description", "reason": None,
                     "distance_squared": distance, "feature_ids": model["feature_ids"],
                     "conditional_mean": expected.tolist(),
                     "warning": "A population residual distance is neither quality nor authorship evidence"}
