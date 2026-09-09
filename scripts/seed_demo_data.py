#!/usr/bin/env python3
"""MediKiosk demo seed — 3 synthetic cases (run with the py3.12 backend venv).

Creates exactly three representative demo journeys through the REAL services
(the same code paths the API uses — no HTTP server required):

  1. URGENT   — chest pain + breathlessness → deterministic red-flag triage
  2. ROUTINE  — fever + cough, a processed lab report (mock OCR), document flow
  3. AYUSH    — joint pain with the Dashavidha Pariksha structured section

Everything is SYNTHETIC (spec §35/§61): tokens A-901/A-902/A-903, "Demo"
patients. The script is repeatable: each run removes its previous demo rows
and re-creates them, so a judge can reset and replay the same story.

Usage (from the repository root):
    backend/.venv/bin/python scripts/seed_demo_data.py
    backend/.venv/bin/python scripts/seed_demo_data.py --db "sqlite+aiosqlite:///./demo.db"
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from sqlalchemy import delete, select  # noqa: E402

import app.models  # noqa: F401,E402 — imports every model module
from app.config import get_settings  # noqa: E402
from app.db import Base as AppBase  # noqa: E402

DEMO_TOKENS = ["A-901", "A-902", "A-903"]


async def _wipe_demo_rows(db) -> int:
    """Delete any previous demo sessions (matched by the demo tokens)."""
    from app.models.clinical import Answer, Document
    from app.models.intake import Consent, PatientSession
    from app.models.patient import Patient
    from app.models.platform import AuditLog

    patients = (
        (await db.execute(select(Patient).where(Patient.external_token.in_(DEMO_TOKENS))))
        .scalars()
        .all()
    )
    if not patients:
        return 0

    session_rows = (
        (
            await db.execute(
                select(PatientSession).where(PatientSession.patient_id.in_([p.id for p in patients]))
            )
        )
        .scalars()
        .all()
    )
    session_ids = [s.id for s in session_rows]
    if not session_ids:
        await db.execute(delete(Patient).where(Patient.id.in_([p.id for p in patients])))
        await db.commit()
        return 0

    # Children first (fhir exports / versions reference the case + session).
    from app.models.case import CaseSummary, CaseVersion
    from app.models.platform import FhirExport

    case_ids = [
        row[0]
        for row in (
            await db.execute(select(CaseSummary.id).where(CaseSummary.session_id.in_(session_ids)))
        ).all()
    ]
    if case_ids:
        await db.execute(delete(CaseVersion).where(CaseVersion.case_summary_id.in_(case_ids)))
    await db.execute(delete(CaseSummary).where(CaseSummary.session_id.in_(session_ids)))
    await db.execute(delete(FhirExport).where(FhirExport.session_id.in_(session_ids)))
    await db.execute(delete(Answer).where(Answer.session_id.in_(session_ids)))
    await db.execute(delete(Document).where(Document.session_id.in_(session_ids)))
    await db.execute(delete(Consent).where(Consent.session_id.in_(session_ids)))
    await db.execute(
        delete(AuditLog).where(
            AuditLog.entity_id.in_(session_ids) | AuditLog.entity_id.in_(case_ids)
        )
    )
    await db.execute(delete(PatientSession).where(PatientSession.id.in_(session_ids)))
    await db.execute(delete(Patient).where(Patient.id.in_([p.id for p in patients])))
    await db.commit()
    return len(session_ids)


async def _make_session(db, *, token, name, age, sex, language, department=None):
    """Create a demo session exactly like POST /sessions + consent would."""
    from app.models.patient import Patient
    from app.models.intake import PatientSession, Consent
    from app.models.platform import AuditLog
    from app.db.base import utcnow

    patient = Patient(
        external_token=token,
        name=name,
        age=age,
        sex=sex,
        preferred_language=language,
    )
    db.add(patient)
    await db.flush()

    intake = PatientSession(
        patient_id=patient.id,
        department=department,
        is_demo=True,
        state="identity",
    )
    db.add(intake)
    await db.flush()

    db.add(
        Consent(
            session_id=intake.id,
            granted=True,
            purposes=["clinical_intake", "document_processing", "record_sharing"],
            consent_text_version="demo-v1",
        )
    )
    db.add(
        AuditLog(
            actor_type="system",
            action="SESSION_CREATED",
            entity_type="session",
            entity_id=intake.id,
            details={"session_id": str(intake.id), "demo_seed": True, "at": utcnow().isoformat()},
        )
    )
    db.add(
        AuditLog(
            actor_type="patient",
            action="CONSENT_GRANTED",
            entity_type="consent",
            entity_id=intake.id,
            details={"session_id": str(intake.id)},
        )
    )
    await db.commit()
    return intake.id


async def _run_interview(db, session_id, answers):
    """Drive the deterministic engine with the scripted answers."""
    from app.schemas.interview import AnswerCreate
    from app.services.dialogue.engine import peek_next, submit_answer

    for question_id, payload in answers:
        question, completed, _, _recorded = await peek_next(db, session_id)
        assert not completed, f"interview completed early, expected {question_id}"
        assert question is not None and question.id == question_id, (
            f"expected {question_id}, got {question.id if question else None}"
        )
        await submit_answer(
            db,
            session_id,
            AnswerCreate(
                question_id=question_id,
                input_mode="touch",
                choice_codes=payload.get("choice_codes"),
                text=payload.get("text"),
            ),
        )


async def seed(db_url: str | None) -> None:
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    url = db_url or get_settings().database_url
    print(f"Seeding demo data into {url.split('@')[-1]} ...")
    engine = create_async_engine(url)

    async with engine.begin() as conn:
        await conn.run_sync(AppBase.metadata.create_all)

    maker = async_sessionmaker(engine, expire_on_commit=False)

    from app.clinical.questions.loader import clear_bank_cache
    from app.services.cases.service import get_or_create_summary
    from app.services.documents.store import create_document
    from app.services.ocr.service import reprocess_document

    clear_bank_cache()

    async with maker() as db:
        removed = await _wipe_demo_rows(db)
        if removed:
            print(f"  removed {removed} previous demo session(s)")

        # ------------------------------------------------------------------
        # Case 1 — URGENT: chest pain + breathlessness (deterministic triage)
        # ------------------------------------------------------------------
        urgent = await _make_session(
            db, token="A-901", name="Demo Patient (Urgent)", age=58, sex="male", language="en"
        )
        await _run_interview(
            db,
            urgent,
            [
                ("cc_001", {"choice_codes": ["chest_pain"]}),
                ("hpi_001", {"choice_codes": ["1_3_days"]}),
                ("hpi_002", {"choice_codes": ["continuous"]}),
                ("hpi_003", {"choice_codes": ["severe"]}),
                ("hpi_004", {"choice_codes": ["breathlessness", "sweating"]}),
                ("hpi_005", {"text": "centre of the chest"}),
                ("hpi_006", {"choice_codes": ["left_arm"]}),
                ("hpi_007", {"choice_codes": ["worse_walking", "better_rest"]}),
                ("hpi_008", {"text": ""}),
                ("ph_001", {"choice_codes": ["hypertension"]}),
                ("ph_002", {"choice_codes": ["no"]}),
                ("med_001", {"choice_codes": ["yes"]}),
                ("med_002", {"text": "Amlodipine 5 mg once daily"}),
                ("alg_001", {"choice_codes": ["none"]}),
                ("fam_001", {"choice_codes": ["heart_disease"]}),
                ("per_001", {"choice_codes": ["past"]}),
                ("per_002", {"choice_codes": ["never"]}),
                ("ros_001", {"choice_codes": ["none"]}),
            ],
        )
        print("  [ok] A-901 urgent chest pain + breathlessness (red-flag triage)")

        # ------------------------------------------------------------------
        # Case 2 — ROUTINE: fever + cough + a processed lab report (mock OCR)
        # ------------------------------------------------------------------
        routine = await _make_session(
            db, token="A-902", name="Demo Patient (Fever)", age=27, sex="female", language="hi"
        )
        await _run_interview(
            db,
            routine,
            [
                ("cc_001", {"choice_codes": ["fever"]}),
                ("hpi_001", {"choice_codes": ["1_3_days"]}),
                ("hpi_002", {"choice_codes": ["continuous"]}),
                ("hpi_003", {"choice_codes": ["moderate"]}),
                ("hpi_004", {"choice_codes": ["fever"]}),
                ("hpi_008", {"text": ""}),
                ("ph_001", {"choice_codes": ["none"]}),
                ("ph_002", {"choice_codes": ["no"]}),
                ("med_001", {"choice_codes": ["yes"]}),
                ("med_002", {"text": "Paracetamol 500 mg as needed"}),
                ("alg_001", {"choice_codes": ["none"]}),
                ("fam_001", {"choice_codes": ["none"]}),
                ("per_001", {"choice_codes": ["never"]}),
                ("per_002", {"choice_codes": ["never"]}),
                ("ros_001", {"choice_codes": ["fever", "fatigue"]}),
            ],
        )
        print("  [ok] A-902 routine fever + cough")

        settings = get_settings()
        Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
        lab_content = _render_demo_lab_report_png()
        doc = await create_document(
            db, routine, "demo_lab_report.png", "image/png", lab_content, settings
        )
        await reprocess_document(db, doc.id)
        await db.refresh(doc)
        print(
            "  [ok] A-902 lab report uploaded + OCR-processed via",
            f"{doc.ocr_provider} ({'simulated — mocked: true' if doc.ocr_mocked else 'REAL OCR'})",
        )

        # ------------------------------------------------------------------
        # Case 3 — AYUSH: joint pain + Dashavidha Pariksha
        # ------------------------------------------------------------------
        ayush = await _make_session(
            db,
            token="A-903",
            name="Demo Patient (AYUSH)",
            age=45,
            sex="female",
            language="en",
            department="ayush",
        )
        await _run_interview(
            db,
            ayush,
            [
                ("cc_001", {"choice_codes": ["joint_pain"]}),
                ("hpi_001", {"choice_codes": ["months"]}),
                ("hpi_002", {"choice_codes": ["intermittent"]}),
                ("hpi_003", {"choice_codes": ["moderate"]}),
                ("hpi_004", {"choice_codes": ["none"]}),
                ("hpi_005", {"text": "both knees, worse on stairs"}),
                ("hpi_007", {"choice_codes": ["worse_walking"]}),
                ("hpi_008", {"text": ""}),
                ("ph_001", {"choice_codes": ["none"]}),
                ("ph_002", {"choice_codes": ["no"]}),
                ("med_001", {"choice_codes": ["no"]}),
                ("med_002", {"text": ""}),
                ("alg_001", {"choice_codes": ["none"]}),
                ("fam_001", {"choice_codes": ["none"]}),
                ("per_001", {"choice_codes": ["never"]}),
                ("per_002", {"choice_codes": ["never"]}),
                ("ros_001", {"choice_codes": ["none"]}),
                ("ay_001", {"choice_codes": ["good"]}),
                ("ay_002", {"choice_codes": ["moderate"]}),
                ("ay_003", {"choice_codes": ["all_foods"]}),
                ("ay_004", {"choice_codes": ["regular"]}),
                ("ay_005", {"choice_codes": ["disturbed"]}),
                ("ay_006", {"choice_codes": ["regular"]}),
                ("ay_007", {"choice_codes": ["low"]}),
                ("ay_008", {"choice_codes": ["sturdy"]}),
                ("ay_009", {"choice_codes": ["calm"]}),
                ("ay_010", {"choice_codes": ["normal"]}),
                ("ay_011", {"text": "mostly vegetarian diet"}),
            ],
        )
        print("  [ok] A-903 AYUSH joint pain + Dashavidha Pariksha")

        # Pre-create the physician case rows so the dashboard shows complete
        # cases immediately (the API also creates them lazily on first read).
        for session_id, label in ((urgent, "A-901"), (routine, "A-902"), (ayush, "A-903")):
            await get_or_create_summary(db, session_id)
            print(f"  [ok] {label} unified case created (draft v1)")

        print(
            "Demo seed complete: 3 synthetic cases — "
            "A-901 urgent, A-902 routine (with lab), A-903 AYUSH."
        )
    await engine.dispose()


def _render_demo_lab_report_png() -> bytes:
    """Render a synthetic printed lab report as a real PNG (Pillow).

    The image is genuinely OCR-readable, so with the real PaddleOCR engine
    installed the demo exercises true OCR; otherwise the labelled mock runs.
    """
    import io

    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGB", (1000, 420), "white")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
    except Exception:
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 28)
        except Exception:
            font = ImageFont.load_default()
    lines = [
        "Demo Diagnostics Laboratory",
        "Patient: Demo Patient (A-902)   Date: 2026-08-28",
        "Glucose 145 mg/dL (Ref 70-140) HIGH",
        "Haemoglobin 13.5 g/dL (Ref 13-17)",
        "Creatinine 1.1 mg/dL (Ref 0.7-1.3)",
    ]
    y = 30
    for line in lines:
        draw.text((40, y), line, font=font, fill="black")
        y += 70
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed MediKiosk synthetic demo data")
    parser.add_argument("--db", default=None, help="database URL override (default: settings)")
    args = parser.parse_args()
    asyncio.run(seed(args.db))
