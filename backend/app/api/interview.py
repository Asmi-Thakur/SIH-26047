"""Interview endpoints — Phase 2b (touch interview, deterministic).

Serves the next approved question from the question bank and persists answers.
Voice input, adaptive LLM extraction and triage rules land in later phases.
"""
import uuid

from fastapi import APIRouter

from app.api.deps import DbSession
from app.clinical.schemas.question import Question
from app.schemas.interview import (
    AnswerCreate,
    ChoiceRead,
    InterviewAnswerResponse,
    InterviewNextResponse,
    QuestionRead,
)
from app.services.dialogue import engine

router = APIRouter(prefix="/interview", tags=["interview"])


def _question_read(question: Question) -> QuestionRead:
    return QuestionRead(
        question_id=question.id,
        section=question.section,
        prompt_en=question.prompt.en,
        prompt_hi=question.prompt.hi,
        input=question.input,
        required=question.required,
        allow_other=question.allow_other,
        choices=[
            ChoiceRead(code=c.code, label_en=c.label.en, label_hi=c.label.hi)
            for c in (question.choices or [])
        ],
    )


@router.get(
    "/{session_id}/next",
    response_model=InterviewNextResponse,
    summary="Next approved question from the state machine",
)
async def next_question(session_id: uuid.UUID, db: DbSession) -> InterviewNextResponse:
    question, completed, state, _recorded = await engine.peek_next(db, session_id)
    return InterviewNextResponse(
        state=state or engine.COMPLETED_STATE,
        completed=completed,
        question=_question_read(question) if question else None,
    )


@router.post(
    "/{session_id}/answer",
    response_model=InterviewAnswerResponse,
    summary="Submit an answer",
)
async def submit_answer(
    session_id: uuid.UUID, payload: AnswerCreate, db: DbSession
) -> InterviewAnswerResponse:
    question, completed, state = await engine.submit_answer(db, session_id, payload)
    return InterviewAnswerResponse(
        state=state or engine.COMPLETED_STATE,
        completed=completed,
        question=_question_read(question) if question else None,
    )
