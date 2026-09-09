"""Loads and validates the question-bank JSON content (ADR-010).

The bank is content, not code: edit backend/app/clinical/questions/bank/*.json
and the engine picks the changes up on next load (module cache cleared in
tests via ``clear_bank_cache``).
"""
import json
from functools import lru_cache
from pathlib import Path

from app.clinical.schemas.question import Question, QuestionBank

_BANK_DIR = Path(__file__).parent / "bank"
_BANK_FILE = _BANK_DIR / "questions.json"


@lru_cache(maxsize=1)
def load_bank() -> QuestionBank:
    """Load (once) and validate the question bank."""
    if not _BANK_FILE.exists():
        raise FileNotFoundError(f"Question bank not found: {_BANK_FILE}")
    raw = json.loads(_BANK_FILE.read_text(encoding="utf-8"))
    return QuestionBank.model_validate(raw)


def clear_bank_cache() -> None:
    """Drop the cached bank (used by tests after editing content)."""
    load_bank.cache_clear()


def question_by_id(bank: QuestionBank, question_id: str) -> Question | None:
    return next((q for q in bank.questions if q.id == question_id), None)


def applicable_questions(
    bank: QuestionBank,
    section: str,
    complaint: str | None,
    department: str | None = None,
) -> list[Question]:
    """Questions of a section that apply given the context.

    - ``for_complaints``: only applies when the recorded complaint is listed
      (unconditional questions always apply).
    - ``department_for``: only applies when the session department matches
      (unlisted questions are department-agnostic) — spec §14 AYUSH gate.
    """
    result = []
    for q in bank.questions:
        if q.section != section:
            continue
        if q.for_complaints and complaint not in q.for_complaints:
            continue
        if q.department_for and department not in q.department_for:
            continue
        result.append(q)
    return result
