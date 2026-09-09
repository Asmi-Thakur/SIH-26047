"""Interview state machine (Phase 2b) — deterministic, no AI.

Progress is derived from the answers actually recorded, not from free-form
LLM state: for each section in order, every *applicable* question (chief
complaint filters via ``for_complaints``) must be answered before moving on.

Session state column mirrors progress for dashboards/resume:

- ``identity`` / ``consent`` -> not started (consent must be recorded first)
- otherwise the section currently being asked
- ``documents`` once every section is complete (OCR/docs milestone is Phase 4)

Consent gating: the interview cannot begin until a consent decision row
exists (granted *or* declined) — see spec §P03.
"""
import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clinical.questions.loader import applicable_questions, load_bank
from app.services.triage.alerts import create_alerts_for_answers
from app.clinical.schemas.question import Question, QuestionBank
from app.models.clinical import Answer
from app.models.intake import Consent, PatientSession
from app.schemas.interview import AnswerCreate

SECTION_ORDER = [
    "chief_complaint",
    "hpi",
    "past_history",
    "medications",
    "allergies",
    "family_history",
    "personal_history",
    "ros",
    "ayush",  # spec §14 — questions gated to department: ayush sessions
]

COMPLETED_STATE = "documents"

# Inputs that capture free text rather than choice codes.
_TEXT_INPUTS = {"text"}


def _error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"status": "error", "code": code, "message": message},
    )


async def _require_session(db: AsyncSession, session_id: uuid.UUID) -> PatientSession:
    session = await db.get(PatientSession, session_id)
    if session is None:
        raise _error(404, "session_not_found", f"No session found for {session_id}")
    return session


async def _require_consent(db: AsyncSession, session_id: uuid.UUID) -> None:
    consent = (
        await db.execute(select(Consent).where(Consent.session_id == session_id))
    ).scalar_one_or_none()
    if consent is None:
        raise _error(
            409,
            "consent_required",
            "Record a consent decision before starting the interview.",
        )


async def _recorded(db: AsyncSession, session_id: uuid.UUID) -> dict[str, Answer]:
    rows = (
        await db.execute(select(Answer).where(Answer.session_id == session_id))
    ).scalars()
    return {a.question_id: a for a in rows}


def _chief_complaint_code(recorded: dict[str, Answer]) -> str | None:
    cc = recorded.get("cc_001")
    if cc is None or not cc.structured_value:
        return None
    code = cc.structured_value.get("code")
    return code if isinstance(code, str) else None


def _progress(
    bank: QuestionBank,
    recorded: dict[str, Answer],
    department: str | None = None,
) -> tuple[str | None, bool]:
    """Return (current_section_or_None_if_complete, completed)."""
    complaint = _chief_complaint_code(recorded)
    for section in SECTION_ORDER:
        applicable = applicable_questions(bank, section, complaint, department)
        unanswered = [q for q in applicable if q.id not in recorded]
        if unanswered:
            return section, False
    return COMPLETED_STATE, True


async def _sync_state(
    db: AsyncSession,
    session: PatientSession,
    current: str | None,
    completed: bool,
) -> None:
    target = COMPLETED_STATE if completed else current
    if session.state != target:
        session.state = target
        await db.commit()
        await db.refresh(session)


async def peek_next(
    db: AsyncSession, session_id: uuid.UUID
) -> tuple[Question | None, bool, str | None, dict[str, Answer]]:
    """Return the next question to ask (no side effects beyond state sync)."""
    session = await _require_session(db, session_id)
    await _require_consent(db, session_id)

    bank = load_bank()
    recorded = await _recorded(db, session_id)
    current, completed = _progress(bank, recorded, session.department)
    await _sync_state(db, session, current, completed)

    if completed:
        return None, True, COMPLETED_STATE, recorded

    assert current is not None
    question = _first_unanswered(
        bank, current, _chief_complaint_code(recorded), recorded, session.department
    )
    return question, False, current, recorded


def _first_unanswered(
    bank: QuestionBank,
    section: str,
    complaint: str | None,
    recorded: dict[str, Answer],
    department: str | None = None,
) -> Question | None:
    for q in applicable_questions(bank, section, complaint, department):
        if q.id not in recorded:
            return q
    return None


async def submit_answer(
    db: AsyncSession, session_id: uuid.UUID, payload: AnswerCreate
) -> tuple[Question | None, bool, str | None]:
    """Persist one answer and return the follow-up question.

    Deterministic ordering: only the expected next question may be answered.
    """
    session = await _require_session(db, session_id)
    await _require_consent(db, session_id)

    bank = load_bank()
    recorded = await _recorded(db, session_id)
    current, completed = _progress(bank, recorded, session.department)
    if completed:
        raise _error(409, "interview_complete", "The interview is already complete.")

    assert current is not None
    expected = _first_unanswered(
        bank, current, _chief_complaint_code(recorded), recorded, session.department
    )
    if expected is None or expected.id != payload.question_id:
        raise _error(
            409,
            "question_not_current",
            f"Expected question {expected.id if expected else '<none>'}, "
            f"got {payload.question_id}.",
        )

    structured, raw = _build_answer_value(bank, expected, payload)
    db.add(
        Answer(
            session_id=session_id,
            question_id=payload.question_id,
            input_mode=payload.input_mode or "touch",
            raw_answer=raw,
            structured_value=structured,
            source="patient_touch",
        )
    )
    await db.commit()

    recorded = await _recorded(db, session_id)
    # Deterministic red-flag screening runs as answers land (spec §13).
    await create_alerts_for_answers(db, session_id, recorded)
    current, completed = _progress(bank, recorded, session.department)
    await _sync_state(db, session, current, completed)

    if completed:
        return None, True, COMPLETED_STATE

    assert current is not None
    follow_up = _first_unanswered(
        bank, current, _chief_complaint_code(recorded), recorded, session.department
    )
    return follow_up, False, current


def _build_answer_value(
    bank: QuestionBank, question: Question, payload: AnswerCreate
) -> tuple[dict, str]:
    """Translate touch payload into structured JSON + readable raw text."""
    if question.input in _TEXT_INPUTS:
        text = (payload.text or "").strip()
        return {"text": text}, text

    allowed = _allowed_codes(question)
    if question.input == "multi":
        codes = payload.choice_codes or []
        unknown = [c for c in codes if c not in allowed]
        if unknown:
            raise _error(422, "unknown_choice", f"Unknown choices: {unknown}")
        labels = [_choice_label(question, c) for c in codes]
        return {"codes": codes}, ", ".join(labels) or "-"

    # single choice
    code = (payload.choice_codes or [None])[0]
    if code is None:
        raise _error(422, "choice_required", f"Question {question.id} needs a choice.")
    if code not in allowed:
        raise _error(422, "unknown_choice", f"Unknown choice: {code}")
    label = _choice_label(question, code)
    if code == "other" and payload.text:
        return {"code": code, "text": payload.text.strip()}, f"{label}: {payload.text.strip()}"
    return {"code": code}, label


def _allowed_codes(question: Question) -> list[str]:
    codes = [c.code for c in question.choices or []]
    if question.allow_other:
        codes.append("other")
    return codes


def _choice_label(question: Question, code: str) -> str:
    for choice in question.choices or []:
        if choice.code == code:
            return choice.label.en
    if code == "other":
        return "Other"
    # Unknown code — keep it visible for the physician rather than dropping it.
    return code
