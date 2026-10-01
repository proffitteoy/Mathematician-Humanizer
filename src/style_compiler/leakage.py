"""Hard derivative grouping plus explicitly declared outer holdout axes."""
from __future__ import annotations
from dataclasses import dataclass, asdict
import hashlib
import re
import unicodedata
from .contracts import Document

HARD_FIELDS = ("work_id", "lineage_id", "content_group_id", "near_duplicate_group_id")
AXES = {"author", "prompt", "source", "topic", "generator"}


def normalized_text(text: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text).casefold())


def _axis(document: Document, axis: str) -> str | None:
    return {"author": document.provenance.author_id,
            "prompt": document.leakage.prompt_family_id,
            "source": document.provenance.source_id,
            "topic": document.context.topic,
            "generator": document.provenance.generator_id}[axis]


def _shingles(text: str, width: int = 5) -> set[str]:
    text = normalized_text(text)
    return {text[i:i + width] for i in range(len(text) - width + 1)} if len(text) >= width else {text}


def connected_groups(documents: list[Document], holdout_axes: tuple[str, ...] = ("author", "prompt"),
                     near_duplicate_threshold: float = .85) -> list[list[str]]:
    """Union hard relationships and the explicitly requested stress-test axes.

    The strict default prevents author and prompt-family overlap simultaneously.
    Crossed designs can become unsplittable: that is reported, never weakened.
    Topic/source/generator are separate optional stress tests, not silently unioned.
    Exact normalized duplicates and lexical 5-character shingle near-duplicates
    are checked in addition to supplied lineage. Semantic duplicate review is
    still required; this lexical screen does not prove independence.
    """
    if set(holdout_axes) - AXES:
        raise ValueError("Unknown holdout axis")
    if not 0 < near_duplicate_threshold <= 1:
        raise ValueError("near_duplicate_threshold must lie in (0,1]")
    ids = [d.document_id for d in documents]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate document IDs")
    parent = list(range(len(documents)))

    def root(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a: int, b: int) -> None:
        a, b = root(a), root(b)
        if a != b:
            parent[max(a, b)] = min(a, b)

    seen: dict[tuple[str, str], int] = {}
    for i, document in enumerate(documents):
        links = [(key, getattr(document.leakage, key)) for key in HARD_FIELDS]
        links += [("axis:" + axis, _axis(document, axis)) for axis in holdout_axes]
        links += [("exact_text", normalized_text(document.text))]
        for namespace, value in links:
            if value is None:
                # AI has no human author, and human writing need not have a prompt.
                # Missing applicable IDs are rejected by the fitting eligibility gate.
                continue
            key = (namespace, value)
            if key in seen:
                union(i, seen[key])
            seen[key] = i
    shingles = [_shingles(d.text) for d in documents]
    for i, left in enumerate(shingles):
        for j in range(i):
            right = shingles[j]
            total = len(left | right)
            if total and len(left & right) / total >= near_duplicate_threshold:
                union(i, j)
    groups: dict[int, list[str]] = {}
    for i, document in enumerate(documents):
        groups.setdefault(root(i), []).append(document.document_id)
    return sorted((sorted(group) for group in groups.values()), key=lambda g: tuple(g))


@dataclass(frozen=True)
class Partition:
    schema_version: str
    assignments: dict[str, str]
    groups: list[list[str]]
    holdout_axes: tuple[str, ...]
    seed: str
    near_duplicate_threshold: float
    warnings: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


def split_documents(documents: list[Document], *, holdout_axes: tuple[str, ...] = ("author", "prompt"),
                    seed: str = "style-compiler-v1", train_fraction: float = .7,
                    near_duplicate_threshold: float = .85) -> Partition:
    if not 0 < train_fraction < 1:
        raise ValueError("train_fraction must lie in (0,1)")
    groups = connected_groups(documents, holdout_axes, near_duplicate_threshold)
    if len(groups) < 2:
        raise ValueError("Infeasible split: fewer than two independent leakage components; do not relax silently")
    ordered = sorted(groups, key=lambda g: hashlib.sha256((seed + "\0" + "\0".join(g)).encode()).hexdigest())
    # Split components, not sentences or individual documents. Counts may differ
    # markedly when components have different sizes; report the actual sizes.
    cut = min(len(ordered) - 1, max(1, round(len(ordered) * train_fraction)))
    assignments = {doc_id: "train" if index < cut else "test"
                   for index, group in enumerate(ordered) for doc_id in group}
    partition = Partition("partition/1.0.0", assignments, groups, tuple(holdout_axes), seed,
                          near_duplicate_threshold,
                          ("Lexical near-duplicate screen requires semantic/lineage review",
                           "Component allocation does not guarantee balanced context coverage"))
    validate_partition(documents, partition)
    return partition


def validate_partition(documents: list[Document], partition: Partition) -> None:
    if partition.schema_version != "partition/1.0.0":
        raise ValueError("Unsupported partition schema version")
    if not isinstance(partition.assignments, dict):
        raise ValueError("Partition assignments must be an object")
    ids = {d.document_id for d in documents}
    if set(partition.assignments) != ids:
        raise ValueError("Partition must cover exactly the supplied documents")
    if not set(partition.assignments.values()) <= {"train", "dev", "test"}:
        raise ValueError("Unknown partition label")
    actual_groups = connected_groups(documents, partition.holdout_axes, partition.near_duplicate_threshold)
    if sorted(sorted(group) for group in partition.groups) != actual_groups:
        raise ValueError("Stored partition groups do not match recomputed corpus components")
    for group in actual_groups:
        if len({partition.assignments[item] for item in group}) != 1:
            raise ValueError(f"Leakage across partition boundary: {group}")
