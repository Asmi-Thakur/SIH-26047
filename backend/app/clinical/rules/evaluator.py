"""Deterministic triage evaluation over structured answers (spec §13).

Rules never run on free text or LLM output — only on structured symptom
codes captured by the question bank. Buckets map question ids to semantic
groups of symptoms:

- ``chief_complaint`` ← cc_001 (single code)
- ``associated``      ← hpi_004 (multi codes)
- ``severity``        ← hpi_003 (single code)

Extend ``BUCKETS_BY_QUESTION`` as new structured questions arrive.
"""
from dataclasses import dataclass

from app.clinical.rules.loader import load_rules
from app.clinical.schemas.rule import RuleBank, TriageRule
from app.models.clinical import Answer

# question_id -> semantic symptom bucket
BUCKETS_BY_QUESTION: dict[str, str] = {
    "cc_001": "chief_complaint",
    "hpi_004": "associated",
    "hpi_003": "severity",
}


@dataclass(frozen=True)
class RuleMatch:
    rule_id: str
    priority: str
    message_en: str


def symptom_presence(recorded: dict[str, Answer]) -> dict[str, set[str]]:
    """Flatten recorded answers into {bucket: {symptom codes}}."""
    presence: dict[str, set[str]] = {bucket: set() for bucket in set(BUCKETS_BY_QUESTION.values())}
    for question_id, bucket in BUCKETS_BY_QUESTION.items():
        answer = recorded.get(question_id)
        if answer is None or not answer.structured_value:
            continue
        value = answer.structured_value
        if isinstance(value, dict):
            codes = value.get("codes") or ([value["code"]] if value.get("code") else [])
            if isinstance(codes, list):
                presence[bucket].update(str(c) for c in codes if c)
    return presence


def _ref_satisfied(presence: dict[str, set[str]], bucket: str, symptom: str) -> bool:
    return symptom in presence.get(bucket, set())


def _rule_satisfied(presence: dict[str, set[str]], rule: TriageRule) -> bool:
    all_of = rule.all_of or []
    any_of = rule.any_of or []
    if not all_of and not any_of:
        return False
    all_ok = all(_ref_satisfied(presence, ref.bucket, ref.symptom) for ref in all_of)
    if not all_ok:
        return False
    if not any_of:
        return True
    return any(_ref_satisfied(presence, ref.bucket, ref.symptom) for ref in any_of)


def evaluate(recorded: dict[str, Answer]) -> list[RuleMatch]:
    """Run all rules over a session's recorded answers."""
    bank: RuleBank = load_rules()
    presence = symptom_presence(recorded)
    matches: list[RuleMatch] = []
    for rule in bank.rules:
        if _rule_satisfied(presence, rule):
            matches.append(RuleMatch(rule.id, rule.priority, rule.message_en))
    return matches
