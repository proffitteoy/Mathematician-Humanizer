#!/usr/bin/env python3
"""Freeze owned example bytes and run literal guards, never semantic validation."""
import argparse
import hashlib
import json
from pathlib import Path


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def freeze(examples_path, output_path):
    raw = examples_path.read_bytes()
    data = json.loads(raw)
    if data.get("schema") != "style-compiler-owned-examples/1":
        raise ValueError("Unsupported examples schema")
    rows = data.get("examples", [])
    if not rows or len({row["id"] for row in rows}) != len(rows):
        raise ValueError("Examples must have unique, nonempty IDs")
    facts = {fact["id"] for fact in data["content_ledger"]}
    frozen = []
    for row in rows:
        text = row["text"]
        missing = [s for s in data.get("immutable_literals", []) if s not in text]
        if missing:
            raise ValueError(f'{row["id"]}: missing literal guards: {missing}')
        if set(row["semantic_self_check"]["facts_present"]) != facts:
            raise ValueError(f'{row["id"]}: incomplete stated self-check ledger')
        frozen.append({"id": row["id"], "source_condition": row["source_condition"],
                       "text_sha256": sha256(text.encode("utf-8")),
                       "utf8_bytes": len(text.encode("utf-8")),
                       "unicode_codepoints": len(text)})
    lock = {"schema": "style-compiler-example-freeze/1",
            "input_filename": examples_path.name, "input_sha256": sha256(raw),
            "checks": "Exact literals and stated ledger IDs only; not semantic equivalence, truth, quality, or human validation.",
            "examples": frozen}
    with output_path.open("x", encoding="utf-8") as f:
        json.dump(lock, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return lock


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("examples", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(freeze(args.examples, args.output), ensure_ascii=False, indent=2))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(1, f"Cannot freeze: {exc}\n")


if __name__ == "__main__":
    main()
