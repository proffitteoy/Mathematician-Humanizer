"""Local measurement, statistical summaries and skill reference compilation."""
import argparse
import importlib.metadata
import json
from pathlib import Path
import sys

from .contracts import Context, Document, Leakage, Provenance, text_hash
from .features import extract
from .editorial import lint
from .profiles import compile_profiles
from .statistics import summarize


def _read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _write(value, output):
    rendered = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if output:
        with Path(output).open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(rendered)
    else:
        sys.stdout.write(rendered)


def analyze(path: Path, models: Path | None = None):
    raw = path.read_bytes()
    text = raw.decode("utf-8")  # Preserve BOM and CRLF in offsets and hashes.
    identity = text_hash(text)
    document = Document(identity, text, Context("zh", "unknown", "unknown", "analysis"),
                        Provenance("unknown", str(path), "caller-supplied local file", False, False),
                        Leakage(identity, identity, identity, identity))
    result = {"schema": "style-analysis/1", "surface": extract(document),
              "linguistic": {"status": "unavailable", "reason": "Supply --models for the pinned local Chinese parser"}}
    if models is not None:
        from .surface import SourceObservation, SourceView, Interval, make_projection
        from .linguistic.adapter import measure
        from .linguistic.stanza_local import LocalStanza

        observation = SourceObservation(SourceView(identity, path.name, 0, 0,
            "local-file/1", 0, "", "unclassified", identity, len(text)), text)
        projection = make_projection(observation.source,
            (Interval(0, len(text)),) if text else (), annotation_profile="whole-local-file/1")
        parsed = LocalStanza(models).parse(observation)
        result["linguistic"] = measure(observation, projection, parsed)
    return result


def main(argv=None):
    # Redirected Windows streams can default to a legacy code page. JSON is UTF-8.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("analyze", help="Measure an unchanged UTF-8 Chinese text file")
    command.add_argument("input", type=Path)
    command.add_argument("--models", type=Path, help="Existing pinned Stanza model directory")
    command.add_argument("-o", "--output", type=Path)
    command = commands.add_parser("summarize", help="Summarize measured TRAIN/DEV JSONL, grouped by source and component")
    command.add_argument("input", type=Path)
    command.add_argument("--bootstrap-draws", type=int, default=400)
    command.add_argument("--seed", type=int, default=0)
    command.add_argument("-o", "--output", type=Path)
    command = commands.add_parser("compile", help="Rebuild the Mathematician Humanizer style cards from frozen research summaries")
    command.add_argument("--research", type=Path, default=Path("research"))
    command.add_argument("--skill", type=Path, default=Path("."), help="Skill directory containing SKILL.md (default: current directory)")
    command.add_argument("-o", "--output", type=Path, help="Optional build receipt; defaults to stdout")
    command = commands.add_parser("check", help="Compare original and candidate; protect code, formulas and explicit locks")
    command.add_argument("original", type=Path)
    command.add_argument("candidate", type=Path)
    command.add_argument("--locks", type=Path, help="JSON array of exact immutable strings")
    command.add_argument("-o", "--output", type=Path)
    command = commands.add_parser("read-paper", help="Extract unchanged mathematical statements and reference candidates")
    command.add_argument("input", type=Path)
    command.add_argument("--format", choices=("auto", "latex", "markdown", "text", "pdf"), default="auto")
    command.add_argument("-o", "--output", type=Path)
    command = commands.add_parser("reconstruct", help="Check evidence-bound proof annotations and compute prerequisites")
    command.add_argument("document", type=Path)
    command.add_argument("annotations", type=Path)
    command.add_argument("--target", action="append", help="Result node id; repeat for multiple targets")
    command.add_argument("-o", "--output", type=Path)
    command = commands.add_parser("prepare-explanation", help="Prepare a versioned mathematical understanding stage")
    command.add_argument("stage", choices=("structure", "proof", "motivation", "literature", "exposition", "mathematical_audit", "editorial"))
    command.add_argument("document", type=Path)
    command.add_argument("--annotations", type=Path)
    command.add_argument("--reader", default="unspecified")
    command.add_argument("--known-node", action="append")
    command.add_argument("--baseline", type=Path)
    command.add_argument("--candidate", type=Path)
    command.add_argument("--audit", type=Path)
    command.add_argument("--research", type=Path, default=Path("research"))
    command.add_argument("-o", "--output", type=Path)
    command = commands.add_parser("audit-exposition", help="Run separate mathematical-record, protection and statistical audits")
    command.add_argument("document", type=Path)
    command.add_argument("annotations", type=Path)
    command.add_argument("baseline", type=Path)
    command.add_argument("candidate", type=Path)
    command.add_argument("--review", type=Path)
    command.add_argument("--language", choices=("zh", "en"), default="zh")
    command.add_argument("--genre", default="math_exposition")
    command.add_argument("--reader", default="unspecified")
    command.add_argument("--research", type=Path, default=Path("research"))
    command.add_argument("--reference-source", choices=("baike", "web"))
    command.add_argument("-o", "--output", type=Path)
    args = parser.parse_args(argv)
    try:
        if getattr(args, "output", None) and args.output.exists():
            raise ValueError("Output already exists; choose a new receipt path")
        if args.command == "analyze":
            result = analyze(args.input, args.models)
        elif args.command == "summarize":
            records = []
            for number, line in enumerate(args.input.read_text(encoding="utf-8-sig").splitlines(), 1):
                if line.strip():
                    try:
                        records.append(json.loads(line))
                    except ValueError as exc:
                        raise ValueError(f"Invalid JSON on line {number}: {exc}") from exc
            result = summarize(records, bootstrap_draws=args.bootstrap_draws, seed=args.seed)
        elif args.command == "compile":
            result = compile_profiles(args.research, args.skill)
        elif args.command == "read-paper":
            from math_reader.document import read_document
            result = read_document(args.input, args.format)
        elif args.command == "reconstruct":
            from math_reader.graph import reconstruct
            result = reconstruct(_read_json(args.document), _read_json(args.annotations), args.target)
        elif args.command == "prepare-explanation":
            from math_exposition.workflow import prepare_stage
            result = prepare_stage(args.stage, _read_json(args.document),
                _read_json(args.annotations) if args.annotations else None, args.reader, args.known_node,
                args.baseline.read_bytes().decode("utf-8") if args.baseline else None,
                args.candidate.read_bytes().decode("utf-8") if args.candidate else None,
                _read_json(args.audit) if args.audit else None, args.research)
        elif args.command == "audit-exposition":
            from math_exposition.workflow import audit_exposition
            result = audit_exposition(_read_json(args.document), _read_json(args.annotations),
                args.baseline.read_bytes().decode("utf-8"), args.candidate.read_bytes().decode("utf-8"),
                args.language, args.genre, args.reader, args.research, args.reference_source,
                _read_json(args.review) if args.review else None)
        else:
            locks = _read_json(args.locks) if args.locks else []
            if not isinstance(locks, list):
                raise ValueError("Locks must be a JSON array")
            result = lint(args.original.read_bytes(), args.candidate.read_bytes(), locks)
        _write(result, getattr(args, "output", None))
        if args.command == "check" and result["blockers"]:
            return 2
        if args.command == "audit-exposition" and not result["editorial_revision_allowed"]:
            return 2
        if args.command == "reconstruct" and result["findings"]:
            return 2
        return 0
    except (TypeError, ValueError, KeyError, RuntimeError, OSError, ImportError, importlib.metadata.PackageNotFoundError) as exc:
        parser.exit(2, f"style-compiler: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
