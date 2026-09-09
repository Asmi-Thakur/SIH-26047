"""FHIR R4 mapper (Phase 7): canonical case -> FHIR R4 Bundle.

Mapping contract (see docs/API_CONTRACT.md — FHIR, and docs/DATA_MODEL.md §1):

- Input is the **confirmed** canonical case — never raw DB rows and never an
  AI suggestion (ADR-005/007/009).
- ``Condition`` resources are created ONLY from clinician-confirmed
  information (source ``physician_confirmed``). Patient-reported or
  document-extracted problem data is carried as ``Observation`` resources so
  nothing ever becomes a diagnosis without the physician (spec §37, ADR-009).
- Provenance survives the hop to FHIR consumers: every resource carries the
  ``ext-source`` extension with a normalised source
  (``patient_reported`` / ``document_extracted`` / ``physician_confirmed``),
  and Composition narrative sections repeat the source inline.
- Output is a deterministic R4 ``Bundle`` (``type: collection``) with
  ``urn:uuid`` references. No network calls happen here — pushing a bundle to
  a FHIR server / ABDM is a future ``HealthRecordAdapter`` (ADR-011).

This module is pure and offline-safe: it never invents clinical facts.
"""
from __future__ import annotations

import html
import uuid
from collections.abc import Mapping

# --- Constants ---------------------------------------------------------------

FHIR_SOURCE_EXTENSION = "http://medikiosk.example.org/fhir/StructureDefinition/source"
FHIR_PROCESSING_STATUS_EXTENSION = (
    "http://medikiosk.example.org/fhir/StructureDefinition/processing-status"
)

# Canonical-case `source` values -> normalised provenance values on the wire.
SOURCE_MAP: dict[str, str] = {
    "patient_touch": "patient_reported",
    "patient_voice": "patient_reported",
    "patient_reported": "patient_reported",
    "document_uploaded": "document_extracted",
    "document_extracted": "document_extracted",
    "physician_confirmed": "physician_confirmed",
}

DISPLAY_SOURCE_MAP: dict[str, str] = {
    "patient_reported": "patient reported",
    "document_extracted": "document extracted",
    "physician_confirmed": "physician confirmed",
}

# Only these sources may become a Condition (a diagnosis).
CONDITION_SOURCES = {"physician_confirmed"}

# Resource types the bundle must contain when the case carries the data.
REQUIRED_RESOURCE_TYPES = (
    "Patient",
    "Encounter",
    "Consent",
    "Composition",
    "Observation",
    "AllergyIntolerance",
    "MedicationStatement",
    "DocumentReference",
)

_NEGATIVE_TEXTS = ("no medicine allergy", "none reported", "no reported")


# --- Small helpers ------------------------------------------------------------


def _is_negative(text: str) -> bool:
    lowered = (text or "").strip().lower()
    return any(lowered.startswith(prefix) for prefix in _NEGATIVE_TEXTS)


def _source_of(item: Mapping) -> str:
    return str(item.get("source") or "patient_touch")


def _normalised_source(item: Mapping) -> str:
    return SOURCE_MAP.get(_source_of(item), _source_of(item))


def _display_source(source: str) -> str:
    return DISPLAY_SOURCE_MAP.get(source, source)


def _source_extension(item: Mapping) -> dict:
    return {
        "url": FHIR_SOURCE_EXTENSION,
        "valueString": _normalised_source(item),
    }


def _extension_list(item: Mapping, *extra: dict) -> list[dict]:
    extensions = [_source_extension(item), *extra]
    return extensions


def _reference(resource_id: str) -> dict:
    return {"reference": f"urn:uuid:{resource_id}"}


def _narrative(text: str) -> dict:
    """Minimal valid XHTML narrative for Composition sections."""
    safe = html.escape((text or "").strip() or "None recorded", quote=False)
    return {
        "status": "generated",
        "div": f'<div xmlns="http://www.w3.org/1999/xhtml"><p>{safe}</p></div>',
    }


def _field_text(field: Mapping | None) -> str | None:
    if not isinstance(field, Mapping):
        return None
    text = (field.get("text") or "").strip()
    return text or None


def _items_text(items: list[Mapping]) -> str | None:
    texts = [str(i.get("text") or "").strip() for i in items]
    texts = [t for t in texts if t]
    return "; ".join(texts) if texts else None


def _derived_uuid(case_id: str | uuid.UUID, name: str) -> str:
    """Deterministic resource id per case (stable across re-exports)."""
    if isinstance(case_id, uuid.UUID):
        namespace = case_id
    else:
        namespace = uuid.UUID(str(case_id))
    return str(uuid.uuid5(namespace, name))


def _labelled(text: str, source: str) -> str:
    return f"{text} [{_display_source(source)}]"


# --- Resource builders ---------------------------------------------------------


def _patient_resource(canonical: Mapping) -> tuple[str, dict]:
    patient = canonical.get("patient") or {}
    resource_id = _derived_uuid(canonical["case_id"], "patient")
    resource: dict = {"resourceType": "Patient", "id": resource_id}
    token = patient.get("token")
    if token:
        resource["identifier"] = [
            {"system": "http://medikiosk.example.org/patient-token", "value": str(token)}
        ]
    if patient.get("name"):
        resource["name"] = [{"text": str(patient["name"])}]
    sex = str(patient.get("sex") or "").strip().lower()
    if sex in {"male", "female", "other"}:
        resource["gender"] = sex
    resource["extension"] = _extension_list(patient)
    return resource_id, resource


def _encounter_resource(canonical: Mapping, patient_id: str) -> tuple[str, dict]:
    resource_id = _derived_uuid(canonical["case_id"], "encounter")
    resource = {
        "resourceType": "Encounter",
        "id": resource_id,
        "status": "finished",
        "class": {
            "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
            "code": "AMB",
            "display": "ambulatory",
        },
        "subject": _reference(patient_id),
        "extension": _extension_list({"source": "patient_reported"}),
    }
    return resource_id, resource


def _consent_resource(canonical: Mapping, patient_id: str) -> tuple[str, dict] | None:
    consent = canonical.get("consent")
    if not isinstance(consent, Mapping):
        return None
    granted = bool(consent.get("granted"))
    resource_id = _derived_uuid(canonical["case_id"], "consent")
    purposes = [str(p) for p in (consent.get("purposes") or [])]
    provision: dict = {"type": "permit" if granted else "deny"}
    if purposes:
        provision["purpose"] = [
            {
                "system": "http://medikiosk.example.org/consent-purpose",
                "code": purpose,
                "display": purpose.replace("_", " "),
            }
            for purpose in purposes
        ]
    resource = {
        "resourceType": "Consent",
        "id": resource_id,
        "status": "active" if granted else "rejected",
        "scope": {
            "coding": [
                {
                    "system": "http://terminology.hl7.org/CodeSystem/consentscope",
                    "code": "patient-privacy",
                    "display": "Privacy Consent",
                }
            ]
        },
        "category": [{"text": "Clinical intake consent"}],
        "patient": _reference(patient_id),
        "provision": provision,
        "extension": _extension_list(consent),
    }
    if consent.get("timestamp"):
        resource["dateTime"] = consent["timestamp"]
    return resource_id, resource


def _observation(
    canonical: Mapping,
    observation_id: str,
    code_text: str,
    value_text: str,
    item: Mapping,
    patient_id: str,
    encounter_id: str,
) -> dict:
    return {
        "resourceType": "Observation",
        "id": observation_id,
        "status": "final",
        "category": [
            {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                        "code": "survey",
                        "display": "Survey",
                    }
                ]
            }
        ],
        "code": {"text": code_text},
        "subject": _reference(patient_id),
        "encounter": _reference(encounter_id),
        "valueString": _labelled(value_text, _normalised_source(item)),
        "extension": _extension_list(item),
    }


def _observation_resources(
    canonical: Mapping, patient_id: str, encounter_id: str
) -> list[tuple[str, dict]]:
    """All Observation resources; ids derived deterministically per case."""
    resources: list[tuple[str, dict]] = []
    case_id = canonical["case_id"]

    def add(name: str, code_text: str, value_text: str, item: Mapping) -> None:
        resources.append(
            (
                _derived_uuid(case_id, f"observation-{name}"),
                _observation(
                    canonical,
                    _derived_uuid(case_id, f"observation-{name}"),
                    code_text,
                    value_text,
                    item,
                    patient_id,
                    encounter_id,
                ),
            )
        )

    # Chief complaint (patient-reported; never a diagnosis — see Conditions).
    complaint = canonical.get("chief_complaint")
    if isinstance(complaint, Mapping) and _field_text(complaint):
        value = str(complaint["text"])
        if complaint.get("onset"):
            value = f"{value} — onset {complaint['onset']}"
        add("chief-complaint", "Chief complaint", value, complaint)

    hpi = canonical.get("hpi") or {}
    hpi_fields = [
        ("onset", "History of present illness — onset"),
        ("constancy", "History of present illness — constancy"),
        ("severity", "History of present illness — severity"),
        ("location", "History of present illness — location"),
        ("radiation", "History of present illness — radiation"),
        ("notes", "History of present illness — additional notes"),
    ]
    for key, code_text in hpi_fields:
        field = hpi.get(key)
        text = _field_text(field if isinstance(field, Mapping) else None)
        if text:
            add(f"hpi-{key}", code_text, text, field)  # type: ignore[arg-type]

    for key, code_text in (
        ("associated", "History of present illness — associated symptoms"),
        ("modifiers", "History of present illness — modifiers"),
    ):
        items = hpi.get(key) or []
        text = _items_text(items)
        if text:
            add(f"hpi-{key}", code_text, text, items[0])

    # Past medical history / family history / ROS — patient-reported problem
    # data stays an Observation; Conditions are reserved for the physician.
    for item in canonical.get("past_history") or []:
        text = _field_text(item)
        if text and not _is_negative(text):
            add("past-history", "Past medical history", text, item)

    surgery = canonical.get("surgical_history")
    surgery_text = _field_text(surgery if isinstance(surgery, Mapping) else None)
    if surgery_text and not _is_negative(surgery_text):
        add("surgical-history", "Past surgical history", surgery_text, surgery)  # type: ignore[arg-type]

    family_text = _items_text(list(canonical.get("family_history") or []))
    if family_text:
        add("family-history", "Family history", family_text, canonical["family_history"][0])

    for key in ("tobacco", "alcohol"):
        field = (canonical.get("personal_history") or {}).get(key)
        text = _field_text(field if isinstance(field, Mapping) else None)
        if text:
            add(f"personal-{key}", f"Personal history — {key}", text, field)  # type: ignore[arg-type]

    ros_text = _items_text(list(canonical.get("review_of_systems") or []))
    if ros_text:
        add("review-of-systems", "Review of systems", ros_text, canonical["review_of_systems"][0])

    return resources


def _condition_resources(canonical: Mapping, patient_id: str, encounter_id: str) -> list[tuple[str, dict]]:
    """Conditions ONLY from clinician-confirmed items (never AI output)."""
    resources: list[tuple[str, dict]] = []
    case_id = canonical["case_id"]
    for index, item in enumerate(canonical.get("past_history") or []):
        text = _field_text(item)
        if not text or _normalised_source(item) not in CONDITION_SOURCES:
            continue
        resource_id = _derived_uuid(case_id, f"condition-{index}")
        resources.append(
            (
                resource_id,
                {
                    "resourceType": "Condition",
                    "id": resource_id,
                    "clinicalStatus": {
                        "coding": [
                            {
                                "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                                "code": "active",
                                "display": "Active",
                            }
                        ]
                    },
                    "verificationStatus": {
                        "coding": [
                            {
                                "system": "http://terminology.hl7.org/CodeSystem/condition-ver-status",
                                "code": "confirmed",
                                "display": "Confirmed",
                            }
                        ]
                    },
                    "category": [
                        {
                            "coding": [
                                {
                                    "system": "http://terminology.hl7.org/CodeSystem/condition-category",
                                    "code": "problem-list-item",
                                    "display": "Problem List Item",
                                }
                            ]
                        }
                    ],
                    "code": {"text": text},
                    "subject": _reference(patient_id),
                    "encounter": _reference(encounter_id),
                    "note": [
                        {"text": f"Source: {_display_source(_normalised_source(item))}"}
                    ],
                    "extension": _extension_list(item),
                },
            )
        )
    return resources


def _allergy_resources(canonical: Mapping, patient_id: str) -> list[tuple[str, dict]]:
    resources: list[tuple[str, dict]] = []
    case_id = canonical["case_id"]
    for index, item in enumerate(canonical.get("allergies") or []):
        text = _field_text(item)
        if not text or _is_negative(text):
            continue
        resource_id = _derived_uuid(case_id, f"allergy-{index}")
        resources.append(
            (
                resource_id,
                {
                    "resourceType": "AllergyIntolerance",
                    "id": resource_id,
                    "clinicalStatus": {
                        "coding": [
                            {
                                "system": "http://terminology.hl7.org/CodeSystem/allergyintolerance-clinical",
                                "code": "active",
                                "display": "Active",
                            }
                        ]
                    },
                    "verificationStatus": {
                        "coding": [
                            {
                                "system": "http://terminology.hl7.org/CodeSystem/allergyintolerance-verification",
                                "code": "confirmed",
                                "display": "Confirmed",
                            }
                        ]
                    },
                    "code": {"text": text},
                    "patient": _reference(patient_id),
                    "extension": _extension_list(item),
                },
            )
        )
    return resources


def _medication_resources(canonical: Mapping, patient_id: str, encounter_id: str) -> list[tuple[str, dict]]:
    medications = canonical.get("medications") or {}
    items = [i for i in (medications.get("list") or []) if _field_text(i)]
    if not items:
        return []
    taking = str(medications.get("taking") or "").strip()
    status = "active" if taking.lower().startswith("yes") else "unknown"
    resources: list[tuple[str, dict]] = []
    case_id = canonical["case_id"]
    for index, item in enumerate(items):
        resource_id = _derived_uuid(case_id, f"medication-{index}")
        resources.append(
            (
                resource_id,
                {
                    "resourceType": "MedicationStatement",
                    "id": resource_id,
                    "status": status,
                    "medicationCodeableConcept": {"text": _field_text(item)},
                    "subject": _reference(patient_id),
                    "encounter": _reference(encounter_id),
                    "extension": _extension_list(item),
                },
            )
        )
    return resources


def _document_resources(canonical: Mapping, patient_id: str) -> list[tuple[str, dict]]:
    resources: list[tuple[str, dict]] = []
    case_id = canonical["case_id"]
    for index, document in enumerate(canonical.get("documents") or []):
        file_name = str(document.get("file_name") or "document")
        resource_id = _derived_uuid(case_id, f"document-{index}")
        attachment: dict = {"title": file_name}
        if document.get("mime_type"):
            attachment["contentType"] = document["mime_type"]
        resource = {
            "resourceType": "DocumentReference",
            "id": resource_id,
            "status": "current",
            "type": {"text": document.get("document_type") or file_name},
            "subject": _reference(patient_id),
            "content": [{"attachment": attachment}],
            "extension": _extension_list(
                document,
                {
                    "url": FHIR_PROCESSING_STATUS_EXTENSION,
                    "valueString": str(document.get("processing_status") or "uploaded"),
                },
            ),
        }
        if document.get("uploaded_at"):
            resource["date"] = document["uploaded_at"]
        resources.append((resource_id, resource))
    return resources


def _composition_resource(
    canonical: Mapping,
    *,
    patient_id: str,
    patient_token: str | None,
    encounter_id: str,
    consent_id: str | None,
    observation_ids: list[str],
    condition_ids: list[str],
    allergy_ids: list[str],
    medication_ids: list[str],
    document_ids: list[str],
    exported_at: str,
) -> tuple[str, dict]:
    case_id = canonical["case_id"]
    resource_id = _derived_uuid(case_id, "composition")

    complaint = canonical.get("chief_complaint") or {}
    complaint_text = _field_text(complaint) or "Not recorded"
    if complaint.get("onset"):
        complaint_text = f"{complaint_text} — onset {complaint['onset']}"

    hpi = canonical.get("hpi") or {}
    hpi_parts: list[str] = []
    for key, label in (
        ("onset", "Onset"),
        ("constancy", "Constancy"),
        ("severity", "Severity"),
        ("location", "Location"),
        ("radiation", "Radiation"),
    ):
        text = _field_text(hpi.get(key) if isinstance(hpi.get(key), Mapping) else None)
        if text:
            hpi_parts.append(f"{label}: {_labelled(text, _normalised_source(hpi[key]))}")
    for key, label in (("associated", "Associated symptoms"), ("modifiers", "Modifiers")):
        text = _items_text(list(hpi.get(key) or []))
        if text:
            hpi_parts.append(f"{label}: {text}")

    def section(title: str, narrative: str, refs: list[str] | None = None) -> dict:
        section_dict: dict = {"title": title, "text": _narrative(narrative)}
        if refs:
            section_dict["entry"] = [_reference(ref) for ref in refs]
        return section_dict

    sections = [
        section(
            "Chief complaint",
            _labelled(complaint_text, _normalised_source(complaint)) if isinstance(complaint, Mapping) else complaint_text,
            [],
        ),
        section("History of present illness", " · ".join(hpi_parts) or "Not recorded", []),
        section(
            "Past medical history",
            _items_text(list(canonical.get("past_history") or [])) or "None recorded",
            condition_ids,
        ),
        section(
            "Medications",
            _items_text(list((canonical.get("medications") or {}).get("list") or []))
            or "Not recorded",
            medication_ids,
        ),
        section(
            "Allergies",
            _items_text(list(canonical.get("allergies") or [])) or "None recorded",
            allergy_ids,
        ),
        section("Family history", _items_text(list(canonical.get("family_history") or [])) or "None recorded", []),
        section(
            "Personal / social history",
            _items_text(
                [
                    v
                    for v in (canonical.get("personal_history") or {}).values()
                    if isinstance(v, Mapping)
                ]
            )
            or "None recorded",
            [],
        ),
        section("Review of systems", _items_text(list(canonical.get("review_of_systems") or [])) or "None recorded", []),
        section(
            "Documents",
            _items_text([{"text": str(d.get("file_name") or "document")} for d in canonical.get("documents") or []])
            or "None uploaded",
            document_ids,
        ),
        section(
            "Triage status",
            str((canonical.get("triage") or {}).get("priority") or "routine"),
            [],
        ),
        section(
            "Missing / uncertain information",
            "; ".join(canonical.get("missing_information") or []) or "None flagged",
            [],
        ),
    ]

    resource: dict = {
        "resourceType": "Composition",
        "id": resource_id,
        "status": "final",
        "type": {"text": "Clinical intake case summary"},
        "category": [{"text": "Clinical intake"}],
        "subject": _reference(patient_id),
        "encounter": _reference(encounter_id),
        "date": exported_at,
        "author": [{"display": "MediKiosk intake (physician-confirmed)"}],
        "title": f"MediKiosk clinical case — Token {patient_token or 'walk-in'}",
        "section": sections,
        "extension": _extension_list({"source": "physician_confirmed"}),
    }
    if consent_id:
        # Consent context travels with the composition (relatesTo is for
        # compositions; keep it as a plain section reference instead).
        resource["section"].insert(
            0,
            {
                "title": "Consent",
                "text": _narrative("Patient consent recorded for clinical intake."),
                "entry": [_reference(consent_id)],
            },
        )
    return resource_id, resource


# --- Bundle assembly -----------------------------------------------------------


def build_fhir_bundle(
    canonical: Mapping,
    *,
    case_id: str | uuid.UUID,
    exported_at: str,
) -> dict:
    """Map a confirmed canonical case to a valid FHIR R4 Bundle.

    Deterministic: the same canonical case + exported_at always produce the
    same bundle (resource ids are uuid5-derived from the case id).
    """
    case_id_str = str(case_id)
    patient_id, patient = _patient_resource(canonical)
    encounter_id, encounter = _encounter_resource(canonical, patient_id)
    consent = _consent_resource(canonical, patient_id)
    consent_id = consent[0] if consent else None

    observations = _observation_resources(canonical, patient_id, encounter_id)
    conditions = _condition_resources(canonical, patient_id, encounter_id)
    allergies = _allergy_resources(canonical, patient_id)
    medications = _medication_resources(canonical, patient_id, encounter_id)
    documents = _document_resources(canonical, patient_id)

    patient_token = (canonical.get("patient") or {}).get("token")
    composition_id, composition = _composition_resource(
        canonical,
        patient_id=patient_id,
        patient_token=patient_token,
        encounter_id=encounter_id,
        consent_id=consent_id,
        observation_ids=[rid for rid, _ in observations],
        condition_ids=[rid for rid, _ in conditions],
        allergy_ids=[rid for rid, _ in allergies],
        medication_ids=[rid for rid, _ in medications],
        document_ids=[rid for rid, _ in documents],
        exported_at=exported_at,
    )

    entries: list[dict] = []

    def add(resource_id: str, resource: dict) -> None:
        entries.append({"fullUrl": f"urn:uuid:{resource_id}", "resource": resource})

    add(patient_id, patient)
    add(encounter_id, encounter)
    if consent:
        add(consent[0], consent[1])
    for resource_id, resource in observations:
        add(resource_id, resource)
    for resource_id, resource in conditions:
        add(resource_id, resource)
    for resource_id, resource in allergies:
        add(resource_id, resource)
    for resource_id, resource in medications:
        add(resource_id, resource)
    for resource_id, resource in documents:
        add(resource_id, resource)
    add(composition_id, composition)

    return {
        "resourceType": "Bundle",
        "id": case_id_str,
        "meta": {"lastUpdated": exported_at},
        "type": "collection",
        "timestamp": exported_at,
        "entry": entries,
    }


__all__ = [
    "build_fhir_bundle",
    "REQUIRED_RESOURCE_TYPES",
    "FHIR_SOURCE_EXTENSION",
    "FHIR_PROCESSING_STATUS_EXTENSION",
    "CONDITION_SOURCES",
    "SOURCE_MAP",
]
