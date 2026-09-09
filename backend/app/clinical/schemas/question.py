"""Question-bank content models (ADR-010: questions are content, not code).

Content lives in backend/app/clinical/questions/bank/*.json and is validated
against these models by the loader. The interview engine (services/dialogue)
serves only questions from this bank — never free-form LLM output.
"""
from pydantic import BaseModel, Field


class TextPair(BaseModel):
    """Bilingual prompt/label. ``hi`` is optional; UI falls back to ``en``."""

    en: str
    hi: str | None = None


class QuestionChoice(BaseModel):
    code: str
    label: TextPair


class Question(BaseModel):
    """One interview question.

    - ``input``: choice | multi | text (touch Phase 2b; voice_or_choice later).
    - ``for_complaints``: if set, the question is only applicable when the
      patient's chief complaint code is in this list (SOCRATES-style
      conditional HPI, spec §11–12).
    - ``choices`` required for choice/multi inputs.
    - ``allow_other``: free-text "Other" is captured for choice inputs.
    """

    id: str = Field(pattern=r"^[a-z][a-z0-9_]+$")
    section: str
    prompt: TextPair
    input: str = "choice"  # choice | multi | text
    required: bool = True
    for_complaints: list[str] | None = None
    # Optional department gate (spec §14): when set, the question only applies
    # to sessions whose department matches (e.g. "ayush" for Dashavidha).
    department_for: list[str] | None = None
    choices: list[QuestionChoice] | None = None
    allow_other: bool = False


class QuestionBank(BaseModel):
    version: int = 1
    sections: list[str]
    questions: list[Question]
