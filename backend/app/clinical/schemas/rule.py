"""Triage rule content models (ADR-010: rules are content, not code).

Rules live in backend/app/clinical/rules/rules.json and are evaluated
deterministically against structured answers — never by an LLM (spec §13).
"""
from pydantic import BaseModel, Field


class SymptomRef(BaseModel):
    """A symptom expected in a named answer bucket.

    Buckets are the sources of structured symptom codes:
    ``chief_complaint`` (cc_001 code), ``associated`` (hpi_004 codes),
    ``severity`` (hpi_003 code).
    """

    bucket: str
    symptom: str


class TriageRule(BaseModel):
    id: str = Field(pattern=r"^[A-Z][A-Z0-9_]+$")
    priority: str = "urgent"
    # Satisfied when every ref matches (and any_of, when present, has ≥1 match).
    all_of: list[SymptomRef] | None = None
    any_of: list[SymptomRef] | None = None
    message_en: str
    message_hi: str | None = None


class RuleBank(BaseModel):
    version: int = 1
    rules: list[TriageRule]
