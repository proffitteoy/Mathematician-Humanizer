#!/usr/bin/env python3
"""Display one empirically joint-conditioned reference; never score a text."""
import argparse
import hashlib
import json
from pathlib import Path

EXPECTED_SHA256 = "e9b5c98fa2655b897c296af985fe1dc32a13c2b92bc6146e26685ea87929fb27"
REFERENCE = Path(__file__).resolve().parents[1] / "references" / "human-joint-reference.json"
BANDS = ("reference", "lower_single_han_share", "middle_single_han_share", "upper_single_han_share")


def load_card(source, band):
    raw = REFERENCE.read_bytes()
    if hashlib.sha256(raw).hexdigest() != EXPECTED_SHA256:
        raise ValueError("Reference bytes differ from the declared source snapshot")
    data = json.loads(raw)
    if data.get("schema") != "source-conditioned-human-joint-reference/1":
        raise ValueError("Unsupported reference schema")
    s = data["sources"][source]
    card = s["reference"] if band == "reference" else s["bands"][band]
    n = len(data["features"])
    for key in ("mean", "q10", "q25", "median", "q75", "q90", "standard_deviation"):
        if len(card[key]) != n:
            raise ValueError(f"Dimension mismatch: {key}")
    for key in ("covariance", "correlation"):
        if len(card[key]) != n or any(len(row) != n for row in card[key]):
            raise ValueError(f"Matrix dimension mismatch: {key}")
    return {"source_condition": source, "neighbourhood": band,
            "measurement": data["measurement"], "measurement_definitions": data["measurement_definitions"],
            "features": data["features"],
            "band_definition": s["band_definition"], "card": card,
            "limitations": data["limitations"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", choices=("baike", "web"))
    parser.add_argument("band", choices=BANDS, nargs="?", default="reference")
    parser.add_argument("--json", action="store_true", help="Emit the complete selected card including covariance")
    args = parser.parse_args()
    try:
        r = load_card(args.source, args.band)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f"Cannot read reference: {exc}\n")
    if args.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return
    c, features = r["card"], r["features"]
    print(f'{args.source} / {args.band}: {c["components"]} observed components')
    print("All dimensions refer to the same subset. Marginal ranges are not a joint acceptance region.")
    for i, f in enumerate(features):
        print(f'{f["id"]} [{f["unit"]}]: median={c["median"][i]:.6g}; '
              f'q25–q75={c["q25"][i]:.6g}–{c["q75"][i]:.6g}; '
              f'q10–q90={c["q10"][i]:.6g}–{c["q90"][i]:.6g}')
    print("Selected within-subset correlations (absolute r >= 0.4; descriptive, not causal):")
    pairs = [(abs(c["correlation"][i][j]), i, j, c["correlation"][i][j])
             for i in range(len(features)) for j in range(i + 1, len(features))
             if c["correlation"][i][j] is not None and abs(c["correlation"][i][j]) >= 0.4]
    for _, i, j, value in sorted(pairs, reverse=True):
        print(f'{features[i]["id"]} / {features[j]["id"]}: r={value:.4f}')
    if not pairs:
        print("None at this display threshold; full matrices remain available with --json.")
    print("Means, all correlations and covariance are available with --json; no writing score is computed.")


if __name__ == "__main__":
    main()
