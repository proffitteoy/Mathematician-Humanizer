"""Document measurements → component-weighted descriptive TRAIN/DEV summaries."""
from collections import defaultdict
import math
import random
import statistics

from .features import quantile


def _moments(values):
    if not values:
        return {"components": 0, "mean": None, "median": None, "q10": None, "q90": None}
    return {"components": len(values), "mean": statistics.mean(values),
            "median": quantile(values, .5), "q10": quantile(values, .1),
            "q90": quantile(values, .9)}


def summarize(records: list[dict], *, bootstrap_draws: int = 400, seed: int = 0) -> dict:
    """Average within components, then weight components equally; never pool sources.

    Pair HUMAN and CHATGPT only within a declared source, component and partition.
    Labels are supplied source conditions, not verified authorship. TEST exports
    are rejected; missing values never become zero.
    """
    if not records:
        raise ValueError("No observations supplied")
    if type(bootstrap_draws) is not int or not 0 <= bootstrap_draws <= 10000:
        raise ValueError("bootstrap_draws must be an integer between 0 and 10000")
    seen, component_splits, grouped = set(), {}, defaultdict(list)
    profile, units = None, None
    for row in records:
        if not isinstance(row, dict) or row.get("schema") != "style-observation/1":
            raise ValueError("Each row must declare style-observation/1")
        for key in ("id", "component_id", "source", "condition", "profile"):
            if not isinstance(row.get(key), str) or not row[key].strip():
                raise ValueError(f"{key} must be a nonempty string")
        if row["id"] in seen:
            raise ValueError("Duplicate observation id")
        seen.add(row["id"])
        split, component = row.get("split"), row["component_id"]
        if split not in ("TRAIN", "DEV"):
            raise ValueError("Only TRAIN/DEV exports are accepted; TEST stays outside this command")
        if component in component_splits and component_splits[component] != split:
            raise ValueError("A component crosses TRAIN/DEV partitions")
        component_splits[component] = split
        features, row_units = row.get("features"), row.get("units")
        if not isinstance(features, dict) or not features:
            raise ValueError("features must be a nonempty map of numbers or null")
        if not isinstance(row_units, dict) or set(row_units) != set(features):
            raise ValueError("units must describe exactly the measured features")
        if any(not isinstance(key, str) or not key.strip() for key in features):
            raise ValueError("Feature ids must be nonempty strings")
        if any(not isinstance(unit, str) or not unit.strip() for unit in row_units.values()):
            raise ValueError("Feature units must be nonempty strings")
        if profile is None:
            profile, units = row["profile"], row_units
        if row["profile"] != profile or row_units != units:
            raise ValueError("Measurement profiles, feature sets and units must match")
        for value in features.values():
            if value is not None and (type(value) not in (int, float) or not math.isfinite(value)):
                raise ValueError("Feature values must be finite numbers or null")
        grouped[split, row["source"], row["condition"], component].append(features)

    means = {}
    for key, rows in sorted(grouped.items()):
        means[key] = {
            feature: statistics.mean(values) if values else None
            for feature in sorted(units)
            for values in [[row[feature] for row in rows if row[feature] is not None]]
        }
    partitions = {}
    for split in sorted(set(component_splits.values())):
        sources = {}
        for source in sorted({key[1] for key in means if key[0] == split}):
            conditions = {}
            for condition in sorted({key[2] for key in means if key[:2] == (split, source)}):
                keys = [key for key in means if key[:3] == (split, source, condition)]
                conditions[condition] = {"documents": sum(len(grouped[key]) for key in keys),
                                         "components": len(keys), "features": {}}
                for feature in sorted(units):
                    values = [means[key][feature] for key in keys if means[key][feature] is not None]
                    conditions[condition]["features"][feature] = _moments(values) | {
                        "missing_documents": sum(row[feature] is None for key in keys for row in grouped[key]),
                        "unavailable_components": len(keys) - len(values),
                    }
            contrasts = {}
            if {"HUMAN", "CHATGPT"} <= set(conditions):
                components = sorted({key[3] for key in means if key[:2] == (split, source)})
                for feature in sorted(units):
                    differences = []
                    for component in components:
                        human = means.get((split, source, "HUMAN", component), {}).get(feature)
                        generated = means.get((split, source, "CHATGPT", component), {}).get(feature)
                        if human is not None and generated is not None:
                            differences.append(human - generated)
                    ci = None
                    if len(differences) >= 2 and bootstrap_draws:
                        rng = random.Random(f"{seed}/{split}/{source}/{feature}")
                        boot = [statistics.mean(rng.choices(differences, k=len(differences)))
                                for _ in range(bootstrap_draws)]
                        ci = [quantile(boot, .025), quantile(boot, .975)]
                    contrasts[feature] = {"paired_components": len(differences),
                                          "human_minus_chatgpt": statistics.mean(differences) if differences else None,
                                          "exploratory_ci95": ci}
            sources[source] = {"conditions": conditions, "paired_contrasts": contrasts}
        partitions[split] = sources
    return {"schema": "style-statistics/1", "profile": profile, "units": units,
            "observations": len(records), "bootstrap_draws": bootstrap_draws, "seed": seed,
            "partitions": partitions,
            "interpretation": "Component-equal descriptive statistics and exploratory paired intervals; not causal editing effects, authorship verification or quality scores."}
