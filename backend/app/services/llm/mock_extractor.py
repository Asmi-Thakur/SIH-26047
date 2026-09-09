"""Deterministic mock clinical extractor (DEMO_MODE).

Turns free-text patient narration into structured fields using keyword
patterns, so the demo shows *structured* extraction (spec: clinical AI
behaviour) without any API key. Real LLM providers replace this class; the
service keeps the same structured contract. Always demo/heuristic — never a
diagnosis.
"""
from __future__ import annotations

import re

# Normalised symptom vocabulary (en + hi keywords -> canonical code/label).
SYMPTOMS: list[tuple[tuple[str, ...], str]] = [
    (("chest pain", "सीने में दर्द", "छाती में दर्द", "सीना दर्द"), "chest_pain"),
    (("dizzy", "dizziness", "chakkar", "चक्कर", "घबराहट"), "dizziness"),
    (("headache", "सिरदर्द"), "headache"),
    (("fever", "बुखार", "बुख़ार"), "fever"),
    (("short of breath", "breathless", "सांस लेने में तकलीफ", "साँस फूलना"), "breathlessness"),
    (("nausea", "जी मिचलाना", "मतली"), "nausea"),
    (("vomiting", "उल्टी"), "vomiting"),
    (("weakness", "कमज़ोरी", "कमजोरी"), "weakness"),
]

CONDITIONS: list[tuple[tuple[str, ...], str]] = [
    (("diabetes", "sugar", "shugra", "डायबिटीज़", "शुगर", "मधुमेह"), "diabetes"),
    (("hypertension", "high blood pressure", "उच्च रक्तचाप", "बीपी"), "hypertension"),
    (("thyroid", "थायरॉइड"), "thyroid"),
    (("asthma", "दमा", "अस्थमा"), "asthma"),
    (("heart disease", "हृदय रोग"), "heart_disease"),
]

MEDICINES: list[tuple[str, str]] = [
    ("metformin", "Metformin"),
    ("insulin", "Insulin"),
    ("amlodipine", "Amlodipine"),
    ("atenolol", "Atenolol"),
    ("paracetamol", "Paracetamol"),
    ("aspirin", "Aspirin"),
    ("thyroxine", "Thyroxine"),
    ("salbutamol", "Salbutamol"),
]

_DURATION = [
    (re.compile(r"since yesterday|from yesterday|कल से"), "1 day"),
    (re.compile(r"(?:last|past) (?:one |1 )?day|पिछले दिन"), "1 day"),
    (re.compile(r"(?:three|3) days|तीन दिन"), "3 days"),
    (re.compile(r"(?:two|2) days|दो दिन"), "2 days"),
    (re.compile(r"(?:last|past) week|पिछले हफ्ते|पिछले सप्ताह"), "1 week"),
    (re.compile(r"(?:last|past) month|पिछले महीने"), "1 month"),
]

_DOSE = re.compile(r"\b(\d{1,4})\s*(mg|mcg|gm|g)\b", re.IGNORECASE)


def _find_terms(text: str, table) -> list[str]:
    lowered = text.lower()
    found = []
    for keys, canonical in table:
        if any(key.lower() in lowered for key in keys):
            found.append(canonical)
    return found


def extract_fields(text: str) -> dict:
    """Deterministic structured extraction from free text."""
    lowered = text.lower()
    complaint = _find_terms(text, SYMPTOMS)
    conditions = _find_terms(text, CONDITIONS)
    meds: list[str] = []
    for keyword, name in MEDICINES:
        if keyword in lowered:
            meds.append(name)
    # Attach doses found near medication names to the med list (simple pass).
    if meds and _DOSE.search(text):
        for match in _DOSE.finditer(text):
            meds.append(f"{match.group(1)} {match.group(2)}")

    duration = next((label for pattern, label in _DURATION if pattern.search(text)), None)

    missing: list[str] = []
    if not complaint:
        missing.append("chief complaint / present symptom")
    if not duration:
        missing.append("how long the problem has lasted (onset)")
    if not conditions:
        missing.append("past medical history")
    if not meds:
        missing.append("current medications")
    missing.append("allergies")
    missing.append("severity of the problem")

    return {
        "complaint": list(dict.fromkeys(complaint)),
        "duration": duration,
        "conditions": list(dict.fromkeys(conditions)),
        "medications": list(dict.fromkeys(meds)),
        "missing_information": missing,
    }
