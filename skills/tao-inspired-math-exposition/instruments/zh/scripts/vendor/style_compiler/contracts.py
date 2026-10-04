"""Versioned input contracts. Missing metadata never silently becomes a label."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import math
from typing import Any

DOCUMENT_VERSION = "document/1.0.0"
BUNDLE_VERSION = "measurement-bundle/1.0.0"
FEATURE_VERSION = "character-core/1.0.0"
COHORTS = {"H_G", "A_G", "A_H", "H_U", "A_U", "A_C", "unknown", "synthetic_test"}
PERSONAL_COHORTS = {"H_U", "A_U"}


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def require_nonempty(value: Any, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a nonempty string")


@dataclass(frozen=True)
class Context:
    language: str
    genre: str
    topic: str
    task: str

    def __post_init__(self) -> None:
        for key, value in asdict(self).items():
            require_nonempty(value, key)

    def key(self) -> tuple[str, ...]:
        return (self.language, self.genre, self.topic, self.task)


@dataclass(frozen=True)
class Provenance:
    cohort: str
    source_id: str
    rights_basis: str
    rights_verified: bool
    is_synthetic: bool
    author_id: str | None = None
    generator_id: str | None = None
    provenance_verified: bool = False
    assistance_status: str = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.cohort not in COHORTS:
            raise ValueError(f"Unsupported cohort {self.cohort!r}")
        for key in ("source_id", "rights_basis"):
            require_nonempty(getattr(self, key), key)
        for key in ("rights_verified", "is_synthetic", "provenance_verified"):
            if type(getattr(self, key)) is not bool:
                raise ValueError(f"{key} must be boolean")
        for key in ("author_id", "generator_id"):
            value = getattr(self, key)
            if value is not None:
                require_nonempty(value, key)
        if self.cohort == "synthetic_test" and not self.is_synthetic:
            raise ValueError("Synthetic-test provenance must set is_synthetic=true")
        if self.assistance_status not in {"unassisted", "assisted", "unknown", "not_applicable"}:
            raise ValueError("Invalid assistance_status")


@dataclass(frozen=True)
class Leakage:
    work_id: str
    lineage_id: str
    content_group_id: str
    near_duplicate_group_id: str
    prompt_family_id: str | None = None

    def __post_init__(self) -> None:
        for key, value in asdict(self).items():
            if key != "prompt_family_id" or value is not None:
                require_nonempty(value, key)


@dataclass(frozen=True)
class Document:
    document_id: str
    text: str
    context: Context
    provenance: Provenance
    leakage: Leakage
    schema_version: str = DOCUMENT_VERSION

    def __post_init__(self) -> None:
        require_nonempty(self.document_id, "document_id")
        if not isinstance(self.text, str):
            raise ValueError("text must be a string")
        if self.schema_version != DOCUMENT_VERSION:
            raise ValueError("Unsupported document schema version")
        if self.provenance.cohort in PERSONAL_COHORTS:
            raise ValueError("Personalization is disabled; personal author corpora are out of scope")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Document:
        if not isinstance(data, dict):
            raise ValueError("Document JSON must be an object")
        allowed = {"document_id", "text", "context", "provenance", "leakage", "schema_version"}
        if set(data) - allowed:
            raise ValueError(f"Unknown document fields: {sorted(set(data) - allowed)}")
        if data.get("schema_version") != DOCUMENT_VERSION:
            raise ValueError("Input must explicitly declare document/1.0.0")
        try:
            return cls(**{**data, "context": Context(**data["context"]),
                         "provenance": Provenance(**data["provenance"]),
                         "leakage": Leakage(**data["leakage"])})
        except (KeyError, TypeError) as exc:
            raise ValueError(f"Invalid document contract: {exc}") from exc

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Measurement:
    feature_id: str
    value: float | None
    unit: str
    level: str
    eligible_count: int
    status: str
    null_reason: str | None
    eligible_for_comparison: bool
    comparison_reason: str | None
    raw_numerator: float | None = None
    denominator: float | None = None
    reliability_tier: str = "raw_observed"
    measurement_method: str = "deterministic_character_proxy"
    uncertainty: dict[str, Any] = field(default_factory=lambda: {
        "measurement_interval": None,
        "reference_prediction_interval": None,
        "reason": "No validated measurement-error model or matched reference distribution",
    })
    span_evidence: list[dict[str, int]] = field(default_factory=list)
    conditional_reference_id: str | None = None

    def __post_init__(self) -> None:
        if self.status not in {"observed", "zero_observed", "unavailable"}:
            raise ValueError("Invalid measurement status")
        if self.value is None:
            if self.status != "unavailable" or not self.null_reason:
                raise ValueError("Missing values need unavailable status and a reason")
            if self.eligible_for_comparison:
                raise ValueError("Missing values cannot be comparison eligible")
        elif not math.isfinite(self.value) or self.status == "unavailable":
            raise ValueError("Observed values must be finite")
        if self.status == "zero_observed" and self.value != 0:
            raise ValueError("zero_observed requires an observed zero")
        if self.eligible_count < 0:
            raise ValueError("eligible_count must be nonnegative")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
