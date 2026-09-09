"""Physician-ready summary draft generator (Phase 6).

Turns the canonical case into a readable, sectioned summary the physician
edits and confirms. Deterministic by default (``generated_by: mock``) and
honestly labelled; a key-gated LLM may later produce the same *shape* through
the same contract, but the deterministic draft must always remain the
fallback (ADR-017/§60).

The summary only re-states structured facts already in the case — it never
invents dates, doses or diagnoses. Every section carries its source inline.
"""
from __future__ import annotations


def _line(text: str | None) -> str:
    return (text or "").strip()


def _items(items: list[dict]) -> str:
    if not items:
        return "None recorded"
    return "; ".join(f"{i['text']} [{i['source']}]" for i in items)


def _documents(documents: list[dict]) -> str:
    """Prior investigations line: type + abnormal values, honestly labelled.

    Only OCR/completed documents carry extracted values; a mocked OCR run is
    always labelled so the physician knows the text was simulated.
    """
    if not documents:
        return "None uploaded"
    parts: list[str] = []
    for d in documents:
        label = f"{d.get('file_name')} ({d.get('document_type') or 'document'})"
        flags = d.get("abnormal_values") or []
        if flags:
            flagged = ", ".join(
                f"{f.get('name')} {f.get('value')} {f.get('unit')} "
                f"{str(f.get('status', '')).upper()}"
                for f in flags
            )
            label += f" — {flagged} [document_extracted]"
        if d.get("ocr_mocked"):
            label += " [mocked OCR]"
        parts.append(label)
    return "; ".join(parts)


def generate_summary(case: dict) -> dict[str, str]:
    """Sectioned physician-ready text draft from a canonical case dict."""
    patient = case.get("patient") or {}
    consent = case.get("consent")
    cc = case.get("chief_complaint")
    hpi = case.get("hpi") or {}
    meds = case.get("medications") or {}
    triage = case.get("triage") or {}
    missing = case.get("missing_information") or []

    consent_text = (
        "granted"
        if consent and consent.get("granted")
        else ("declined" if consent else "not recorded")
    )

    encounter = (
        f"Token {patient.get('token') or 'walk-in'} · "
        f"age {patient.get('age') or 'unknown'} · "
        f"language {patient.get('preferred_language') or 'en'} · "
        f"consent {consent_text}"
    )

    chief_complaint = (
        f"{_line(cc.get('text'))}"
        + (f" — onset {_line(cc.get('onset'))}" if cc and cc.get("onset") else "")
        if cc
        else "Not recorded"
    )

    hpi_parts: list[str] = []
    for label, key in (
        ("Location", "location"),
        ("Onset", "onset"),
        ("Constancy", "constancy"),
        ("Severity", "severity"),
        ("Radiation", "radiation"),
        ("Modifiers", "modifiers"),
        ("Associated symptoms", "associated"),
        ("Additional notes", "notes"),
    ):
        value = hpi.get(key)
        if isinstance(value, dict) and value.get("text"):
            hpi_parts.append(f"{label}: {value['text']} [{value['source']}]")
        elif isinstance(value, list) and value:
            hpi_parts.append(
                f"{label}: {_items(value)}"
            )
    hpi_text = " · ".join(hpi_parts) if hpi_parts else "Not recorded"

    surgery = case.get("surgical_history")
    surgical_text = (
        f"{surgery['text']} [{surgery['source']}]" if surgery else "None recorded"
    )

    taking = _line(meds.get("taking"))
    meds_text = "; ".join(i["text"] for i in meds.get("list") or [])
    if meds_text:
        medications = f"Taking medicines: {taking} — {meds_text}"
    elif taking:
        medications = f"Taking medicines: {taking}"
    else:
        medications = "Not recorded"

    ayush = case.get("ayush")
    if isinstance(ayush, dict) and ayush.get("items"):
        ayush_text = "; ".join(
            f"{i.get('field', '')}: {i['text']} [{i.get('source', 'patient_touch')}]"
            if i.get("field")
            else f"{i['text']} [{i.get('source', 'patient_touch')}]"
            for i in ayush["items"]
        )
    else:
        ayush_text = "Not collected"

    rules = triage.get("rules_triggered") or []
    if triage.get("priority") == "urgent":
        triage_text = f"URGENT — red-flag rules: {', '.join(rules)}"
    else:
        triage_text = "Routine — no red-flag rules triggered"

    timeline_lines = [
        f"{e['at']} · {e['kind']} · {e['label']}" + (f" — {e['detail']}" if e.get("detail") else "")
        for e in case.get("timeline") or []
    ]
    timeline_text = "\n".join(timeline_lines) if timeline_lines else "No events"

    missing_text = "; ".join(missing) if missing else "None flagged"

    return {
        "patient_encounter": encounter,
        "chief_complaint": chief_complaint,
        "history_of_present_illness": hpi_text,
        "past_medical_history": _items(case.get("past_history") or []),
        "past_surgical_history": surgical_text,
        "medications": medications,
        "allergies": _items(case.get("allergies") or []),
        "family_history": _items(case.get("family_history") or []),
        "personal_social_history": _items(
            [
                v
                for v in (case.get("personal_history") or {}).values()
                if isinstance(v, dict) and v.get("text")
            ]
        )
        or "None recorded",
        "review_of_systems": _items(case.get("review_of_systems") or []),
        "ayush_history": ayush_text,
        "prior_investigations": _documents(case.get("investigations") or []),
        "timeline": timeline_text,
        "triage_status": triage_text,
        "missing_uncertain_information": missing_text,
    }


__all__ = ["generate_summary"]