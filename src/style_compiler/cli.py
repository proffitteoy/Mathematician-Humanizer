"""Local-only JSON CLI. Never downloads text, models, or sends generation calls."""
from __future__ import annotations
import argparse
from dataclasses import replace
import json
from pathlib import Path
import sys
from .contracts import Document
from .features import extract
from .leakage import Partition, split_documents
from .model import fit_population_model
from .planner import propose_paragraph_break, apply_reviewed_plan


def _read(path: str):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write(value, output: str | None):
    rendered = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if output:
        Path(output).write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command, help_text in (("extract", "Measure one document JSON"),
                               ("split", "Create a leakage-screened partition of document JSONL"),
                               ("fit", "Fit a real-data-gated experimental population model"),
                               ("plan", "Propose one review-gated paragraph-boundary edit"),
                               ("apply", "Apply the exact reviewed structural candidate")):
        cmd = sub.add_parser(command, help=help_text)
        cmd.add_argument("input", help="Local input path")
        cmd.add_argument("-o", "--output")
        if command == "split":
            cmd.add_argument("--holdout-axes", default="author,prompt")
            cmd.add_argument("--seed", default="style-compiler-v1")
        if command == "fit":
            cmd.add_argument("--partition", required=True)
            cmd.add_argument("--cohort", required=True, choices=["H_G", "A_G", "A_H", "A_C"])
        if command == "plan":
            cmd.add_argument("--max-sentences", type=int, required=True)
            cmd.add_argument("--protect", action="append", default=[])
        if command == "apply":
            cmd.add_argument("--plan", required=True)
            cmd.add_argument("--semantic-review-approved", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command in {"split", "fit"}:
            documents = [Document.from_dict(json.loads(line)) for line in Path(args.input).read_text(encoding="utf-8").splitlines() if line.strip()]
            if args.command == "split":
                result = split_documents(documents, holdout_axes=tuple(a for a in args.holdout_axes.split(",") if a), seed=args.seed).to_dict()
            else:
                raw = _read(args.partition)
                partition = Partition(**raw)
                result = fit_population_model(documents, partition, cohort=args.cohort)
        else:
            document = Document.from_dict(_read(args.input))
            if args.command == "extract":
                result = extract(document)
            elif args.command == "plan":
                result = propose_paragraph_break(document, max_sentences=args.max_sentences, protected_strings=tuple(args.protect))
            else:
                result = replace(document, text=apply_reviewed_plan(document, _read(args.plan),
                                 semantic_review_approved=args.semantic_review_approved)).to_dict()
        _write(result, args.output)
    except (TypeError, ValueError, RuntimeError, OSError, json.JSONDecodeError) as exc:
        parser.exit(2, f"style-compiler: {exc}\n")
    return 0
