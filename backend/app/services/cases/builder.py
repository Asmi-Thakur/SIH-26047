"""Unified clinical case builder (Phase 6).

Assembles ONE canonical case per session from every structured source:
interview answers (touch/voice), uploaded documents, deterministic triage
alerts and consent — following docs/DATA_MODEL.md §1. Every item keeps its
source (provenance) so the physician console can always tell
``patient_reported`` from ``document_extracted`` from ``physician_confirmed``.

This module is deterministic and offline-safe (spec §60): it is a pure
assembly of recorded facts — never a diagnosis.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.clinical.questions.loader import load_bank, question_by_id
from app.clinical.schemas.question import QuestionBank
from app.models.clinical import Answer, Document, TriageAlert
from app.models.intake import Consent, PatientSession
from app.models.patient import Patient
from app.services.summary.generator import generate_summary

SECTION_LABELS: dict[str, str] = {
    "chief_complaint": "Chief complaint",
    "hpi": "History of present illness",
    "past_history": "Past medical history",
    "medications": "Medications",
    "allergies": "Allergies",
    "family_history": "Family history",
    "personal_history": "Personal history",
    "ros": "Review of systems",
}

# question_id prefix -> section name (question ids use short prefixes, e.g.
# ``cc_001`` for the chief_complaint section).
SECTION_PREFIXES: dict[str, str] = {
    "cc": "chief_complaint",
    "hpi": "hpi",
    "ph": "past_history",
    "med": "medications",
    "alg": "allergies",
    "fam": "family_history",
    "per": "personal_history",
    "ros": "ros",
}


def _iso(value: datetime) -> str:
    return value.isoformat()


def _answer_text(answer: Answer | None) -> str | None:
    if answer is None:
        return None
    return (answer.raw_answer or "").strip() or None


def _label_for(bank: QuestionBank, question_id: str, code: str) -> str:
    question = question_by_id(bank, question_id)
    if question:
        for choice in question.choices or []:
            if choice.code == code:
                return choice.label.en
    if code == "other":
        return "Other"
    return code


def _humanize(bank: QuestionBank, answer: Answer) -> str:
    """Readable text for an answer (labels for codes, raw text otherwise)."""
    value = answer.structured_value or {}
    if isinstance(value, dict):
        codes = value.get("codes")
        if isinstance(codes, list) and codes:
            return ", ".join(
                _label_for(bank, answer.question_id, str(c)) for c in codes
            )
        code = value.get("code")
        if isinstance(code, str):
            label = _label_for(bank, answer.question_id, code)
            other = value.get("text")
            return f"{label}: {other}" if other else label
    return (answer.raw_answer or "").strip()


def _item(text: str, source: str, question_id: str | None = None) -> dict:
    item: dict = {"text": text, "source": source}
    if question_id:
        item["question_id"] = question_id
    return item


def _field(answer: Answer | None, bank: QuestionBank) -> dict | None:
    """One HPI-style field: {text, source, confidence} or None."""
    if answer is None:
        return None
    return {
        "text": _humanize(bank, answer),
        "source": answer.source or "patient_touch",
        "confidence": answer.confidence,
    }


def _multi_field(
    bank: QuestionBank,
    answers: list[Answer],
    question_id: str,
) -> list[dict]:
    for answer in answers:
        if answer.question_id == question_id:
            return [_item(_humanize(bank, answer), answer.source or "patient_touch", question_id)]
    return []


async def build_canonical_case(
    db: AsyncSession,
    session: PatientSession,
    *,
    patient: Patient | None,
    consent: Consent | None,
    answers: list[Answer],
    documents: list[Document],
    alerts: list[TriageAlert],
    case_id: uuid.UUID | None = None,
    status: str = "draft",
    draft_version: int = 1,
) -> dict:
    """Assemble the canonical case dict for a session (see DATA_MODEL.md §1)."""
    bank = load_bank()
    by_id: dict[str, Answer] = {a.question_id: a for a in answers}
    reported = "patient_touch"

    def text_of(question_id: str) -> str | None:
        return _answer_text(by_id.get(question_id))

    # --- Chief complaint + HPI ----------------------------------------------
    cc = by_id.get("cc_001")
    chief_complaint = None
    if cc is not None:
        chief_complaint = {
            "code": (cc.structured_value or {}).get("code"),
            "text": _humanize(bank, cc),
            "onset": text_of("hpi_001"),
            "source": cc.source or reported,
            "confidence": cc.confidence,
        }

    hpi: dict = {}
    hpi_fields = [
        ("onset", "hpi_001"),
        ("constancy", "hpi_002"),
        ("severity", "hpi_003"),
        ("location", "hpi_005"),
        ("radiation", "hpi_006"),
        ("notes", "hpi_008"),
    ]
    for key, qid in hpi_fields:
        hpi[key] = _field(by_id.get(qid), bank)
    hpi["associated"] = _multi_field(bank, answers, "hpi_004")
    hpi["modifiers"] = _multi_field(bank, answers, "hpi_007")

    # --- Past / medications / allergies / family / personal / ROS -----------
    past_history: list[dict] = []
    ph = by_id.get("ph_001")
    if ph is not None:
        value = ph.structured_value or {}
        codes = value.get("codes") or []
        for code in codes:
            if code == "none":
                continue
            past_history.append(
                _item(_label_for(bank, "ph_001", str(code)), ph.source or reported, "ph_001")
            )
        other = value.get("text")
        if other:
            past_history.append(_item(f"Other: {other}", ph.source or reported, "ph_001"))
    if not past_history and ph is not None:
        past_history.append(_item("None reported", ph.source or reported, "ph_001"))

    surgery = _field(by_id.get("ph_002"), bank)

    med_taking = text_of("med_001")
    medications: list[dict] = []
    med_notes = by_id.get("med_002")
    if med_notes is not None and (med_notes.raw_answer or "").strip():
        for line in (line.strip() for line in med_notes.raw_answer.splitlines()):
            if line:
                medications.append(_item(line, med_notes.source or reported, "med_002"))

    allergies: list[dict] = []
    alg = by_id.get("alg_001")
    if alg is not None:
        value = alg.structured_value or {}
        codes = value.get("codes") or []
        for code in codes:
            if code == "none":
                continue
            allergies.append(
                _item(_label_for(bank, "alg_001", str(code)), alg.source or reported, "alg_001")
            )
        other = value.get("text")
        if other:
            allergies.append(_item(f"Other: {other}", alg.source or reported, "alg_001"))
    if not allergies and alg is not None:
        allergies.append(_item("No medicine allergy", alg.source or reported, "alg_001"))

    family_history: list[dict] = []
    fam = by_id.get("fam_001")
    if fam is not None:
        value = fam.structured_value or {}
        codes = value.get("codes") or []
        for code in codes:
            if code == "none":
                continue
            family_history.append(
                _item(_label_for(bank, "fam_001", str(code)), fam.source or reported, "fam_001")
            )
    if not family_history and fam is not None:
        family_history.append(_item("None reported", fam.source or reported, "fam_001"))

    personal_history: dict = {}
    for key, qid in (("tobacco", "per_001"), ("alcohol", "per_002")):
        personal_history[key] = _field(by_id.get(qid), bank)

    ros: list[dict] = []
    ros_a = by_id.get("ros_001")
    if ros_a is not None:
        value = ros_a.structured_value or {}
        codes = value.get("codes") or []
        for code in codes:
            if code == "none":
                continue
            ros.append(_item(_label_for(bank, "ros_001", str(code)), ros_a.source or reported, "ros_001"))
        if not ros:
            ros.append(_item("None reported", ros_a.source or reported, "ros_001"))

    # --- AYUSH Dashavidha Pariksha (spec §14) --------------------------------
    # Structured practitioner-relevant observations only — the kiosk never
    # derives an Ayurvedic diagnosis or treatment plan (spec §14.3).
    ayush_questions = [q for q in bank.questions if q.section == "ayush"]
    ayush_entries: list[dict] = []
    for question in ayush_questions:
        answer = by_id.get(question.id)
        if answer is None:
            continue
        text = _humanize(bank, answer)
        if not text or text == "-":
            continue
        entry = _item(text, answer.source or reported, question.id)
        entry["field"] = question.prompt.en
        ayush_entries.append(entry)
    ayush_block = (
        {
            "collected": True,
            "department": "ayush",
            "items": ayush_entries,
            "disclaimer": (
                "Practitioner-relevant history captured for physician review. "
                "The system does not determine an Ayurvedic diagnosis or treatment."
            ),
        }
        if ayush_entries
        else None
    )

    # --- Documents / investigations ------------------------------------------
    document_rows: list[dict] = []
    abnormal_timeline: list[dict] = []
    for d in documents:
        extraction = d.extraction or {}
        row = {
            "document_id": str(d.id),
            "file_name": d.file_name,
            "document_type": d.document_type,
            "processing_status": d.processing_status,
            "uploaded_at": _iso(d.uploaded_at),
            "source": "document_uploaded",
        }
        if d.processing_status == "completed":
            row.update(
                {
                    "ocr_provider": d.ocr_provider,
                    "ocr_mocked": d.ocr_mocked,
                    "page_count": d.page_count,
                    "processed_at": _iso(d.processed_at) if d.processed_at else None,
                    "abnormal_values": extraction.get("abnormal_values") or [],
                    "tests": extraction.get("tests") or [],
                    "medications": extraction.get("medications") or [],
                    "conditions": extraction.get("conditions") or [],
                }
            )
            # Timeline entries for flagged values — only real extracted facts.
            for flag in (extraction.get("abnormal_values") or [])[:5]:
                abnormal_timeline.append(
                    {
                        "at": _iso(d.processed_at) if d.processed_at else _iso(d.uploaded_at),
                        "kind": "document_extracted",
                        "label": d.file_name,
                        "detail": (
                            f"{flag.get('name')} {flag.get('value')} {flag.get('unit')} "
                            f"— {str(flag.get('status', '')).upper()}"
                        ).strip(),
                    }
                )
        document_rows.append(row)
    investigations = [
        row for row in document_rows
        if row["document_type"] in ("lab_report", "imaging_report")
        and row.get("processing_status") == "completed"
    ]

    # --- Triage ------------------------------------------------------------------
    active_urgent = [a for a in alerts if a.priority == "urgent" and a.status == "active"]
    rules: list[str] = []
    for alert in alerts:
        for rule in alert.rules_triggered or []:
            if rule not in rules:
                rules.append(rule)
    triage = {
        "priority": "urgent" if active_urgent else "routine",
        "rules_triggered": rules,
        "alerts": [
            {
                "alert_id": str(a.id),
                "rule_id": (a.rules_triggered or ["unknown"])[0],
                "message": a.message,
                "status": a.status,
                "created_at": _iso(a.created_at),
            }
            for a in alerts
        ],
    }

    # --- Timeline ------------------------------------------------------------------
    timeline: list[dict] = []
    for answer in answers:
        question = question_by_id(bank, answer.question_id)
        timeline.append(
            {
                "at": _iso(answer.created_at),
                "kind": "answer",
                "label": question.prompt.en if question else answer.question_id,
                "detail": _humanize(bank, answer),
            }
        )
    for doc in documents:
        timeline.append(
            {
                "at": _iso(doc.uploaded_at),
                "kind": "document_upload",
                "label": doc.file_name,
                "detail": doc.document_type or (doc.mime_type or "document"),
            }
        )
    timeline.extend(abnormal_timeline)
    for alert in alerts:
        timeline.append(
            {
                "at": _iso(alert.created_at),
                "kind": "triage_alert",
                "label": (alert.rules_triggered or ["triage_alert"])[0],
                "detail": alert.message or alert.priority,
            }
        )
    timeline.sort(key=lambda e: e["at"])

    # --- Missing information / provenance ------------------------------------------
    answered_prefixes = {
        a.question_id.split("_", 1)[0] for a in answers
    }
    answered_sections = {
        SECTION_PREFIXES[p] for p in answered_prefixes if p in SECTION_PREFIXES
    }
    missing: list[str] = []
    for section in SECTION_LABELS:
        if section not in answered_sections:
            missing.append(f"{SECTION_LABELS[section]} not completed")
    if not documents:
        missing.append("No prior documents uploaded for review")
    elif not any(d.processing_status == "completed" for d in documents):
        missing.append("Documents uploaded but not yet processed (no OCR/extraction results)")
    if not rules:
        missing.append("No red-flag symptoms reported")

    provenance = {
        "patient_reported": [a.question_id for a in answers],
        "document_extracted": [
            str(d.id) for d in documents if d.processing_status == "completed"
        ],
        "physician_confirmed": [],
    }

    case = {
        "case_id": str(case_id) if case_id else None,
        "session_id": str(session.id),
        "status": status,
        "draft_version": draft_version,
        "patient": {
            "patient_id": str(patient.id) if patient else None,
            "token": patient.external_token if patient else None,
            "name": patient.name if patient else None,
            "age": patient.age if patient else None,
            "sex": patient.sex if patient else None,
            "preferred_language": patient.preferred_language if patient else None,
        },
        "consent": (
            {
                "granted": consent.granted,
                "purposes": consent.purposes or [],
                "timestamp": _iso(consent.created_at),
            }
            if consent
            else None
        ),
        "chief_complaint": chief_complaint,
        "hpi": hpi,
        "past_history": past_history,
        "surgical_history": surgery,
        "medications": {"taking": med_taking, "list": medications},
        "allergies": allergies,
        "family_history": family_history,
        "personal_history": personal_history,
        "review_of_systems": ros,
        "ayush": ayush_block,
        "documents": document_rows,
        "investigations": investigations,
        "timeline": timeline,
        "triage": triage,
        "missing_information": missing,
        "provenance": provenance,
    }
    return case


async def assemble_case(
    db: AsyncSession,
    session: PatientSession,
    *,
    consent: Consent | None,
    answers: list[Answer],
    documents: list[Document],
    alerts: list[TriageAlert],
    case_id: uuid.UUID | None = None,
    status: str = "draft",
    draft_version: int = 1,
) -> dict:
    """Full assembly: canonical case + physician-ready summary draft."""
    patient = None
    if session.patient_id:
        patient = await db.get(Patient, session.patient_id)

    canonical = await build_canonical_case(
        db,
        session,
        patient=patient,
        consent=consent,
        answers=answers,
        documents=documents,
        alerts=alerts,
        case_id=case_id,
        status=status,
        draft_version=draft_version,
    )
    summary = generate_summary(canonical)
    return {"canonical": canonical, "summary": summary}

__all__ = [
    "build_canonical_case",
    "assemble_case",
    "generate_summary",
    "SECTION_LABELS",
]