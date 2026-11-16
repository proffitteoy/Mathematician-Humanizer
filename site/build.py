"""Build the stateless Worker from this exact checkout; no network or model calls."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from math_reader.document import parse_document
from math_reader.graph import reconstruct
from math_exposition.prompts import CONTROLLER, PROMPTS, PROMPT_VERSION
from math_exposition.workflow import statistical_feedback
from style_compiler import __version__
from style_compiler.editorial import DISPLAY_ENV, DISPLAY_MATH_LIMIT, PRESENTATION_PATTERNS, PROTECTED


def committed_bytes(commit, path):
    return subprocess.run(["git", "show", f"{commit}:{path}"], cwd=ROOT,
                          check=True, capture_output=True).stdout


def ranges(predicate):
    result, start = [], None
    for cp in range(0x110001):
        selected = cp < 0x110000 and predicate(chr(cp))
        if selected and start is None:
            start = cp
        elif not selected and start is not None:
            result.append([start, cp - 1])
            start = None
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "site")
    args = parser.parse_args()
    output = args.output.resolve()
    if unicodedata.unidata_version != "15.0.0":
        raise ValueError("Build with Unicode 15.0.0 to preserve the frozen measurement instrument")
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()
    paths = {"skill": "SKILL.md", "style": "references/mathematician-style.md",
             "statistics": "references/statistical-style.md", "license": "references/upstream-LICENSE.txt",
             "example": "examples/rewrite.md", "understanding": "references/mathematical-understanding.md"}
    pinned = {path: committed_bytes(commit, path) for path in paths.values()}
    documents = {key: pinned[path].decode("utf-8") for key, path in paths.items()}
    hashes = {path: hashlib.sha256(raw).hexdigest() for path, raw in pinned.items()}
    manifest = json.loads(committed_bytes(commit, "research/manifest.json"))
    raw = committed_bytes(commit, "research/results.json")
    if hashlib.sha256(raw).hexdigest() != manifest["inputs"]["results.json"]["sha256"]:
        raise ValueError("Frozen research identity changed")
    research = json.loads(raw)["chinese_surface"]
    supported = {r["feature_id"] for r in research["development_audit"]["features"] if r["inspection_supported"]}
    references = {r["feature_id"]: {s: r["train_domains"][s]["human_q10_q90"] for s in ("baike", "web")}
                  for r in research["model"]["features"] if r["train_inspection_eligible"] and r["feature_id"] in supported}
    data = {"version": __version__, "commit": commit, "repository": "https://github.com/proffitteoy/Mathematician-Humanizer",
            "paths": paths, "documents": documents, "hashes": hashes, "controller": CONTROLLER,
            "prompts": PROMPTS, "prompt_version": PROMPT_VERSION, "references": references,
            "reference_sha256": hashlib.sha256(raw).hexdigest(),
            "instrument": statistical_feedback("")["measurement"],
            "ln_ranges": ranges(lambda c: unicodedata.category(c)[0] in "LN"),
            "space_ranges": ranges(str.isspace), "digit_ranges": ranges(str.isdigit),
            "protected_pattern": PROTECTED.pattern, "display_math_limit": DISPLAY_MATH_LIMIT,
            "display_env_pattern": DISPLAY_ENV.pattern, "presentation_patterns": PRESENTATION_PATTERNS}
    output.mkdir(parents=True, exist_ok=True)
    (output / "dist/server").mkdir(parents=True, exist_ok=True)
    (output / "dist/.openai").mkdir(parents=True, exist_ok=True)
    hosting_path = output / ".openai/hosting.json"
    if not hosting_path.exists():
        hosting_path.parent.mkdir(parents=True, exist_ok=True)
        hosting_path.write_text(json.dumps({"project_id": "appgprj_6ac4a1336bac81918aad9da3e140ebf2", "capabilities": ["mcp"]}, indent=2)+"\n", encoding="utf-8")
    hosting = json.loads(hosting_path.read_text(encoding="utf-8"))
    if hosting.get("project_id") != "appgprj_6ac4a1336bac81918aad9da3e140ebf2" or "mcp" not in hosting.get("capabilities", []):
        raise ValueError("Use the existing Mathematician Humanizer Site identity and MCP capability")
    html = (ROOT / "site/index.html").read_text(encoding="utf-8").replace("__SOURCE_SHA__", commit).replace("__SOURCE_SHORT__", commit[:7]).replace("__VERSION__", __version__)
    source = (ROOT / "site/worker.mjs").read_text(encoding="utf-8")
    source = source.replace("// BUILD_DATA", "const DATA = " + json.dumps(data, ensure_ascii=False) + ";\nconst HTML = " + json.dumps(html, ensure_ascii=False) + ";", 1)
    (output / "dist/server/index.js").write_text(source, encoding="utf-8", newline="\n")
    (output / "dist/.openai/hosting.json").write_text(json.dumps(hosting, indent=2)+"\n", encoding="utf-8")
    if output != ROOT / "site":
        for path in paths.values():
            dest = output / "upstream" / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(pinned[path])
    provenance = {"repository": data["repository"], "commit": commit, "version": data["version"],
                  "prompt_version": PROMPT_VERSION, "unicode_version": unicodedata.unidata_version, "sha256": hashes}
    (output / "source-manifest.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2)+"\n", encoding="utf-8", newline="\n")
    paper = {"text": committed_bytes(commit, "examples/argument.tex").decode(), "format": "latex", "source": "fixture"}
    doc = parse_document(**paper)
    annotations = json.loads(committed_bytes(commit, "examples/argument.annotations.json"))
    fixtures = [{"text": text, "expected": statistical_feedback(text)} for text in ["", "\ufeff甲。\r\n乙乙。😀", "A. Smith has 3.14.\n甲乙！丙丙丙？", "\u001c甲。\n\U0002ebf0乙。", "。\n".join("甲" * (i+1) for i in range(25)),
        "😀你可能会问，为什么要投影？这不是技巧，而是关键。\n$$a=b$$\n\\[c=d\\]\n$e=f$\n\\begin{equation}g=h\\end{equation}",
        "```tex\n$$code$$\n你可能会问，为什么？\n```\n> 这不是判断，而是引文。\n若 $x>0$，有 $x^2>0$。"]]
    goldens = {"statistics": fixtures, "example": {"paper": paper, "document": doc, "annotations": annotations, "graph": reconstruct(doc, annotations)},
               "parsing": [{"paper": {"text": text, "format": fmt, "source": "fixture"}, "expected": parse_document(text, fmt, "fixture")}
                           for text, fmt in [("\ufeff😀\r\n"+paper["text"], "latex"), ("# Results\n```tex\nTheorem fake\n```\n**Theorem 1.** X.\nProof. Y.\n# Next\nZ.", "markdown"), ("定理1：结论。\n证明：理由。", "text")]]}
    (output / "goldens.json").write_text(json.dumps(goldens, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    if output != ROOT / "site":
        (output / "data.json").write_text(json.dumps(data, ensure_ascii=False, allow_nan=False), encoding="utf-8", newline="\n")
        for name in ("worker.mjs", "test.mjs", "index.html", "build.mjs"):
            shutil.copyfile(ROOT / "site" / name, output / name)
        (output / "package.json").write_text(json.dumps({"name": "mathematician-humanizer-mcp", "version": __version__, "private": True, "type": "module", "scripts": {"build": "node build.mjs", "test": "node --test test.mjs"}}, indent=2)+"\n", encoding="utf-8")
        (output / "README.md").write_text(
            f"# Mathematician Humanizer v2\n\nStateless Site MCP Worker, version {__version__}.\n\n"
            f"Exported from {data['repository']}/tree/{commit}. The canonical source and Python/Worker parity tests live in site/ in that repository.\n\n"
            "Run `node build.mjs` then `node --test test.mjs`. The build verifies pinned upstream hashes and does not fetch source.\n\n"
            "Nine tools cover source parsing, exact source windows, evidence-bound DAG/MAR, staged tasks, separate audits, actual surface measurement and the three compatibility entries. Paper calls must carry original text or ordered chunks; manuscripts are not stored.\n\n"
            "Presentation feedback counts standalone math blocks (default limit: 3) and flags staged questions or habitual not-X-but-Y turns. Inline equations are preferred; real questions, substantive contrasts and protected mathematics require contextual review.\n\n"
            "No proof certification, background model calls or author/quality scores. PDF and fixed linguistic parsers remain local. Full upstream MIT notice is preserved under upstream/references/.\n", encoding="utf-8", newline="\n")
    print(json.dumps({"output": str(output), "version": data["version"], "source_commit": commit, "documents": len(paths)}))


if __name__ == "__main__":
    main()
