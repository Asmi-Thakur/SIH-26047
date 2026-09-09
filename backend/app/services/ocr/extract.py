"""Document classification + deterministic clinical extraction (Phase 4/2).

Turns raw OCR text into structured, source-labelled clinical data:

- ``classify_document``  : keyword classifier over the spec §16.3 classes;
  ``unknown`` when nothing matches — never a guess dressed as a fact.
- ``extract_document_facts``: lab-test rows (name/value/unit/reference/status),
  medicine lines, and problem/condition keywords, each carrying its
  ``source_text`` and a ``document_extracted`` provenance (ADR-009: extraction
  is information retrieval, never a diagnosis).

Reference ranges come ONLY from the report itself (spec §21). When the source
supplies no range the status is ``unknown`` — ranges are never invented.
"""
from __future__ import annotations

import re

# --- Document classification (spec §16.3) ------------------------------------

CLASSIFY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "lab_report": ("lab", "laboratory", "pathology", "diagnostics", "specimen", "haemoglobin", "hemoglobin", "glucose", "creatinine", "reference"),
    "prescription": ("prescription", "rx", "tab ", "tablet", "capsule", "syrup", "twice daily", "tds", "od ", "bd ", "sos"),
    "discharge_summary": ("discharge", "admitted", "admission", "summary of hospitalization", "follow up"),
    "imaging_report": ("x-ray", "xray", "ultrasound", "ct scan", "mri", "radiology", "impression:", "findings:"),
}

TYPE_LABELS: dict[str, str] = {
    "lab_report": "Lab report",
    "prescription": "Prescription",
    "discharge_summary": "Discharge summary",
    "imaging_report": "Imaging report",
    "other": "Other document",
    "unknown": "Unknown document type",
}


def classify_document(text: str) -> str:
    """Keyword classification into a spec §16.3 class (deterministic)."""
    lowered = (text or "").lower()
    scores: dict[str, int] = {}
    for doc_type, keywords in CLASSIFY_KEYWORDS.items():
        scores[doc_type] = sum(1 for keyword in keywords if keyword in lowered)
    best_type, best_score = max(scores.items(), key=lambda kv: kv[1])
    return best_type if best_score > 0 else "unknown"


# --- Structured extraction -----------------------------------------------------

# "Glucose 145 mg/dL (Ref 70-140) HIGH" / "Hb: 9.8 g/dL ref 13-17" / "Sugar (F) 180 mg% [70-110]"
TEST_LINE = re.compile(
    r"^\s*(?P<name>[A-Za-z][A-Za-z0-9 ()%/\-\.]{1,40}?)\s*[:\-]?\s+"
    r"(?P<value>\d{1,5}(?:\.\d{1,2})?)\s*"
    r"(?P<unit>mg/dL|mg/dl|g/dL|g/dl|mmol/L|mmol/l|mg%|meq/L|mEq/L|IU/L|U/L|ng/mL|pg/mL|cells/mm3|10\^?\d/?µ?l|/µL|µmol/L|%)\s*"
    r"(?:\(?\s*(?:ref(?:erence)?\.?|normal)?\s*[:\-]?\s*(?P<low>\d{1,5}(?:\.\d{1,2})?)\s*(?:-|to|–)\s*(?P<high>\d{1,5}(?:\.\d{1,2})?)\s*\)?)?\s*"
    r"(?P<flag>high|low|h|l)?\s*$",
    re.IGNORECASE,
)

_UNIT_ALIASES = {"mg/dl": "mg/dL", "g/dl": "g/dL", "mmol/l": "mmol/L", "meq/l": "mEq/L"}

# Problem/condition keywords (en + common Hindi transliterations) -> label.
CONDITION_KEYWORDS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("diabetes", "sugar", "shugra", "मधुमेह", "डायबिटीज़"), "Diabetes"),
    (("hypertension", "high blood pressure", "blood pressure", "बीपी", "उच्च रक्तचाप"), "Hypertension"),
    (("asthma", "दमा"), "Asthma"),
    (("thyroid", "थायरॉइड"), "Thyroid disorder"),
    (("tuberculosis", "tb "), "Tuberculosis"),
    (("anemia", "anaemia", "खून की कमी"), "Anemia"),
    (("arthritis", "joint pain", "गठिया", "जोड़ों का दर्द"), "Joint pain / arthritis"),
    (("heart disease", "cad", "coronary", "हृदय रोग"), "Heart disease"),
)

# Medicine-name keywords -> normalised label (deterministic, no invention).
MEDICINE_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("metformin", "Metformin"),
    ("insulin", "Insulin"),
    ("amlodipine", "Amlodipine"),
    ("atenolol", "Atenolol"),
    ("telmisartan", "Telmisartan"),
    ("paracetamol", "Paracetamol"),
    ("aspirin", "Aspirin"),
    ("thyroxine", "Thyroxine"),
    ("salbutamol", "Salbutamol"),
    ("omeprazole", "Omeprazole"),
    ("atorvastatin", "Atorvastatin"),
    ("azithromycin", "Azithromycin"),
    ("amoxicillin", "Amoxicillin"),
    ("cetirizine", "Cetirizine"),
)

_DOSE = re.compile(r"\b(\d{1,4}(?:\.\d)?)\s*(mg|mcg|gm|g|ml)\b", re.IGNORECASE)


def _normalise_unit(unit: str) -> str:
    return _UNIT_ALIASES.get(unit.lower(), unit)


def _flag_status(value: float, low: float | None, high: float | None, text_flag: str | None) -> str:
    """Spec §21: use the report's own reference range; never invent one."""
    if text_flag:
        flag = text_flag.strip().lower()
        if flag == "high" or flag == "h":
            return "high"
        if flag == "low" or flag == "l":
            return "low"
    if low is not None and value < low:
        return "low"
    if high is not None and value > high:
        return "high"
    if low is not None or high is not None:
        return "normal"
    return "unknown"


def extract_tests(lines: list[str]) -> list[dict]:
    """Lab-test rows found in OCR lines (value + optional reference range)."""
    tests: list[dict] = []
    for line in lines:
        match = TEST_LINE.match(line.strip())
        if not match:
            continue
        value = float(match.group("value"))
        low = float(match.group("low")) if match.group("low") else None
        high = float(match.group("high")) if match.group("high") else None
        tests.append(
            {
                "name": match.group("name").strip(" :"),
                "value": value,
                "unit": _normalise_unit(match.group("unit")),
                "reference_low": low,
                "reference_high": high,
                "status": _flag_status(value, low, high, match.group("flag")),
                "source_text": line.strip(),
            }
        )
    return tests


def extract_medications(lines: list[str]) -> list[dict]:
    """Medicine lines found in OCR text (names/doses present in the source)."""
    meds: list[dict] = []
    for line in lines:
        lowered = line.lower()
        for keyword, name in MEDICINE_KEYWORDS:
            if keyword in lowered:
                dose = _DOSE.search(line)
                meds.append(
                    {
                        "name": name,
                        "raw_text": line.strip(),
                        "strength": f"{dose.group(1)} {dose.group(2).lower()}" if dose else None,
                        "source_text": line.strip(),
                    }
                )
                break
    return meds


def extract_conditions(lines: list[str]) -> list[dict]:
    """Problem/condition mentions found in the document (labelled, not diagnosed)."""
    joined = "\n".join(lines).lower()
    found: list[dict] = []
    seen: set[str] = set()
    for keywords, label in CONDITION_KEYWORDS:
        if label in seen:
            continue
        for keyword in keywords:
            if keyword in joined:
                found.append({"text": label, "source_text": keyword.strip()})
                seen.add(label)
                break
    return found


def extract_document_facts(text: str) -> dict:
    """Structured facts from OCR text (all provenance = document_extracted)."""
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    tests = extract_tests(lines)
    return {
        "tests": tests,
        "abnormal_values": [t for t in tests if t["status"] in {"high", "low"}],
        "medications": extract_medications(lines),
        "conditions": extract_conditions(lines),
    }


__all__ = [
    "classify_document",
    "extract_document_facts",
    "extract_tests",
    "extract_medications",
    "extract_conditions",
    "TYPE_LABELS",
]
