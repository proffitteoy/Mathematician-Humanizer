import copy
import hashlib
from pathlib import Path
import tempfile
import unittest

from math_reader.document import parse_document, read_document, validate_document
from math_reader.graph import reconstruct


PAPER = r"""\section{Least squares}
\begin{definition}\label{d}Let $A\in\mathbb R^{m\times n}$, $b\in\mathbb R^m$ and $M=\operatorname{im}A$.\end{definition}
\begin{lemma}\label{p}There is a unique closest vector $y_*\in M$ to $b$.\end{lemma}
\begin{proof}Orthogonal decomposition gives $\|b-y\|^2=\|b-y_*\|^2+\|y-y_*\|^2$.\end{proof}
\begin{lemma}\label{k}If $Ax_*=y_*$, then $Ax=y_*$ iff $x-x_*\in\ker A$.\end{lemma}
\begin{proof}Subtract $Ax_*$ from $Ax$ and use linearity.\end{proof}
\begin{theorem}\label{t}The least-squares minimizers are $x_*+\ker A$.\end{theorem}
\begin{proof}Use Lemmas \ref{p} and \ref{k}.\end{proof}
\begin{remark}This unrelated remark is not a prerequisite.\end{remark}
"""


def anchor(document, quote=None):
    quote = quote if quote is not None else document["text"]
    start = document["text"].index(quote)
    return {"document_id": document["document_id"], "start": start, "end": start + len(quote), "quote": quote}


def annotations(document):
    nodes = {n["id"]: n for n in document["nodes"]}
    ev = anchor(document)
    return {"document_id": document["document_id"], "main_theorems": ["n6"], "nodes": [], "reading_coverage": [ev],
        "edges": [{"from": a, "to": b, "kind": kind, "role": role, "basis": "reconstruction", "evidence": [ev]}
                  for a, b, kind, role in [("n1", "n2", "definition", "The image is a finite dimensional subspace"),
                      ("n1", "n4", "definition", "Linearity gives the kernel identity"),
                      ("n2", "n6", "reduction", "All optimal coefficients must map to the unique projection"),
                      ("n4", "n6", "construction", "The fiber over the projection is a translate of the kernel")]],
        "claims": [{"kind": "mathematical_motivation", "text": "Separate the optimal image from its coefficient fiber",
                    "nodes": ["n2", "n4", "n6"], "basis": "reconstruction", "evidence": [ev]}],
        "arguments": {"n6": {"statement": anchor(document, nodes["n6"]["text"]),
            "hypotheses": [anchor(document, nodes["n1"]["text"])],
            "conclusion": anchor(document, "The least-squares minimizers are $x_*+\\ker A$."),
            "obstruction": {"text": "The optimal vector need not specify unique coefficients", "evidence": [ev]},
            "mechanism": {"text": "Project onto the image and then compute the fiber", "evidence": [ev]},
            "idea": {"text": "Separate optimization in the image from kernel freedom", "evidence": [ev]},
            "status": "reviewed"}},
        "coverage": {n: {"status": "reviewed", "evidence": [ev]} for n in ("n1", "n2", "n4", "n6")}}


class DocumentTests(unittest.TestCase):
    def test_pdf_extracted_text_keeps_page_map_and_file_hash(self):
        try:
            from pypdf import PdfWriter
            from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
        except ImportError:
            self.skipTest("Install optional PDF dependency")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "paper.pdf"
            writer = PdfWriter()
            font = writer._add_object(DictionaryObject({NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")}))
            for body in (b"Theorem 1. A result.", b"Proof. A justification."):
                page = writer.add_blank_page(width=200, height=100)
                page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})})
                stream = DecodedStreamObject()
                stream.set_data(b"BT /F1 12 Tf 10 50 Td (" + body + b") Tj ET")
                page[NameObject("/Contents")] = writer._add_object(stream)
            writer.write(path)
            doc = read_document(path)
            self.assertEqual(doc["source_sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
            self.assertEqual(len(doc["pages"]), 2)
            for page in doc["pages"]:
                self.assertTrue(doc["text"][page["start"]:page["end"]].strip())
            self.assertIn("Proof.", doc["text"][doc["pages"][1]["start"]:])
            validate_document(doc)

    def test_pdf_page_offsets_and_empty_extraction_warning(self):
        try:
            from pypdf import PdfWriter
        except ImportError:
            self.skipTest("Install optional PDF dependency")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "paper.pdf"
            writer = PdfWriter()
            writer.add_blank_page(width=72, height=72)
            # An image-only or blank PDF must not silently become a successful empty document.
            writer.write(path)
            with self.assertRaisesRegex(ValueError, "nonempty document"):
                read_document(path)

    def test_latex_original_offsets_labels_and_references(self):
        text = "\ufeff😀\r\n" + PAPER.replace("\n", "\r\n")
        doc = parse_document(text)
        self.assertEqual(doc["document_id"], hashlib.sha256(text.encode()).hexdigest())
        for node in doc["nodes"]:
            self.assertEqual(text[node["start"]:node["end"]], node["text"])
        self.assertEqual(doc["reference_candidates"][0]["possible_targets"], ["n2"])
        self.assertTrue(all(c["status"] == "reference_only" for c in doc["reference_candidates"]))

    def test_comments_code_and_custom_environments(self):
        text = (r"\newtheorem{result}{Theorem}" + "\n% " + r"\begin{lemma}fake\end{lemma}" + "\n"
                + r"\begin{verbatim}\begin{lemma}fake\end{lemma}\end{verbatim}"
                + r"\begin{result}Actual $x=1$.\end{result}")
        doc = parse_document(text)
        self.assertEqual(len(doc["nodes"]), 1)
        self.assertEqual(doc["nodes"][0]["kind"], "theorem")

    def test_markdown_excludes_fences_and_keeps_sections(self):
        doc = parse_document("# Results\n```tex\nTheorem fake\n```\n**Theorem 1.** X.\nProof. Y.\n# Next\nZ.", "markdown")
        self.assertEqual([n["kind"] for n in doc["nodes"]], ["theorem", "proof"])
        self.assertEqual(doc["nodes"][0]["section"], "Results")
        self.assertNotIn("Next", doc["nodes"][1]["text"])

    def test_incomplete_tex_and_no_structure_are_explicit(self):
        self.assertTrue(parse_document(r"\begin{lemma}incomplete")["warnings"])
        self.assertEqual(parse_document("Plain mathematics.", "text")["nodes"], [])

    def test_tampered_structure_or_identity_rejected(self):
        doc = parse_document(PAPER)
        doc["nodes"][0]["start"] += 1
        with self.assertRaisesRegex(ValueError, "mismatch"):
            validate_document(doc)

    def test_chinese_heading_without_space(self):
        doc = parse_document("定理1：结论。\n证明：理由。", "text")
        self.assertEqual([n["kind"] for n in doc["nodes"]], ["theorem", "proof"])

    def test_citations_and_bibliography_are_source_anchored_not_dependencies(self):
        text = (r"\section{Context}Use \cite[Theorem 2]{original}."
                + r"\begin{thebibliography}{9}\bibitem{original}An original work.\end{thebibliography}")
        doc = parse_document(text)
        self.assertEqual(doc["citations"][0]["keys"], ["original"])
        self.assertEqual(doc["bibliography"][0]["key"], "original")
        self.assertEqual(doc["sections"][0]["title"], "Context")
        for entry in doc["citations"] + doc["bibliography"]:
            self.assertEqual(text[entry["start"]:entry["end"]], entry["text"])
        self.assertEqual(doc["reference_candidates"], [])

    def test_file_input_preserves_crlf_and_bom(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "paper.tex"
            raw = ("\ufeff" + PAPER.replace("\n", "\r\n")).encode()
            path.write_bytes(raw)
            self.assertEqual(read_document(path)["text"].encode(), raw)


class GraphTests(unittest.TestCase):
    def setUp(self):
        self.doc = parse_document(PAPER)
        self.data = annotations(self.doc)

    def test_theorem_driven_order_excludes_unrelated_nodes(self):
        result = reconstruct(self.doc, self.data)
        self.assertEqual(result["prerequisite_order"], ["n1", "n2", "n4", "n6"])
        self.assertIn("n8", result["excluded_nodes"])
        self.assertEqual(result["findings"], [])
        self.assertEqual(result["mathematical_validity"], "not_certified")

    def test_cycles_even_outside_target_are_rejected(self):
        ev = anchor(self.doc)
        for a, b in [("n7", "n8"), ("n8", "n7")]:
            self.data["edges"].append({"from": a, "to": b, "kind": "application", "role": "test", "basis": "reconstruction", "evidence": [ev]})
        with self.assertRaisesRegex(ValueError, "cycle"):
            reconstruct(self.doc, self.data)

    def test_unknown_duplicate_self_edges_and_empty_role(self):
        for changes in ({"from": "missing"}, {"from": "n2", "to": "n2"}, {"role": ""}, {"basis": "guessed"}):
            data = copy.deepcopy(self.data)
            data["edges"][0].update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                reconstruct(self.doc, data)

    def test_quote_and_source_drift_rejected(self):
        for changes in ({"quote": "invented"}, {"start": -1}, {"end": True}, {"document_id": "wrong"}):
            data = copy.deepcopy(self.data)
            data["edges"][0]["evidence"][0].update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                reconstruct(self.doc, data)

    def test_historical_and_author_attribution_need_more_than_reconstruction(self):
        self.data["claims"][0].update(kind="author_motivation")
        ids = {f["id"] for f in reconstruct(self.doc, self.data)["findings"]}
        self.assertIn("unsupported_attribution", ids)
        self.data["claims"][0].update(kind="historical_origin", basis="explicit_source")
        ids = {f["id"] for f in reconstruct(self.doc, self.data)["findings"]}
        self.assertIn("primary_source_not_checked", ids)

    def test_original_work_can_be_registered_as_exact_external_evidence(self):
        external = parse_document("This construction predates the current paper.", "text", "original work")
        self.data["external_sources"] = [external]
        self.data["claims"][0].update(kind="historical_origin", basis="explicit_source",
                                      evidence=[anchor(self.doc), anchor(external)])
        self.assertEqual(reconstruct(self.doc, self.data)["findings"], [])

    def test_missing_mar_or_review_is_not_success(self):
        self.data["arguments"] = {}
        self.data["coverage"].pop("n4")
        ids = {f["id"] for f in reconstruct(self.doc, self.data)["findings"]}
        self.assertEqual(ids, {"missing_argument_record", "missing_proof_review"})

    def test_unread_middle_is_not_hidden_by_reading_ends(self):
        text = self.doc["text"]
        self.data["reading_coverage"] = [anchor(self.doc, text[:20]), anchor(self.doc, text[-20:])]
        result = reconstruct(self.doc, self.data)
        self.assertEqual(result["unread_ranges"], [{"start": 20, "end": len(text) - 20}])
        self.assertIn("incomplete_source_reading", {f["id"] for f in result["findings"]})

    def test_manual_assumptions_and_local_proof_steps(self):
        ev = anchor(self.doc)
        self.data["nodes"] = [{"id": "step1", "kind": "proof", "anchor": ev}]
        self.data["edges"].append({"from": "step1", "to": "n6", "kind": "application", "role": "Local proof step", "basis": "reconstruction", "evidence": [ev]})
        self.data["coverage"]["step1"] = {"status": "gap", "evidence": [ev], "note": "local step not checked"}
        result = reconstruct(self.doc, self.data)
        self.assertIn("step1", result["prerequisite_order"])
        self.assertIn("proof_gap", {f["id"] for f in result["findings"]})
