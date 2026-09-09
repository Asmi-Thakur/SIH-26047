"""Interview endpoint schemas (Phase 2b — touch interview).

Question content comes from the validated question bank; these models only
describe the wire envelope. Mirrored in frontend/src/types/index.ts.
"""
from pydantic import BaseModel, Field


class ChoiceRead(BaseModel):
    code: str
    label_en: str
    label_hi: str | None = None


class QuestionRead(BaseModel):
    question_id: str
    section: str
    prompt_en: str
    prompt_hi: str | None = None
    input: str  # choice | multi | text
    required: bool = True
    allow_other: bool = False
    choices: list[ChoiceRead] = []


class InterviewNextResponse(BaseModel):
    """GET /interview/{session_id}/next."""

    state: str
    completed: bool
    question: QuestionRead | None = None


class AnswerCreate(BaseModel):
    question_id: str
    input_mode: str | None = Field(default=None, pattern=r"^(touch|voice|manual)$")
    choice_codes: list[str] | None = None
    text: str | None = None


class InterviewAnswerResponse(BaseModel):
    """POST /interview/{session_id}/answer."""

    saved: bool = True
    state: str
    completed: bool
    question: QuestionRead | None = None
    triage: None = None  # deterministic rule engine lands in a later phase
