# MediKiosk — SIH 26047 Full Prototype Build Specification

> **Smart India Hackathon 2026 — Problem Statement 26047**  
> **Title:** Patient Case-Taking Software  
> **Organization:** Ministry of Ayush  
> **Department:** All India Institute of Ayurveda  
> **Category:** Software  
> **Theme:** Smart Automation

---

## 1. Purpose of this document

This is the implementation specification for a **working SIH prototype**, not merely a README.

The goal is to give a development team enough detail to start creating the repository, database, APIs, UI, AI services, demo data, and deployment environment without first having to redesign the product architecture.

The prototype must demonstrate one complete patient journey:

```text
Patient arrives
   ↓
Language selection
   ↓
Identity / token
   ↓
Consent
   ↓
Voice OR touch clinical history
   ↓
Real-time red-flag screening
   ↓
Prior-document upload / camera capture
   ↓
OCR + document classification
   ↓
Clinical entity extraction
   ↓
Timeline + abnormal-value detection
   ↓
AI physician-ready case summary
   ↓
Doctor review / edit / confirm
   ↓
FHIR R4 export / mock HIS
   ↓
Session closure + temporary-data cleanup
```

The system is **AI-assisted, not autonomous diagnosis software**. The physician remains the final decision-maker.

---

# 2. Source alignment

## 2.1 SIH26047 requirements covered

The official problem statement asks for a patient-facing platform that can collect comprehensive clinical history through natural voice conversation and guided touch, digitize paper medical documents, produce a structured physician-ready summary, support AYUSH history, detect urgent symptoms, and integrate with the hospital/ABDM ecosystem.

The prototype therefore treats these as the primary requirements:

| Requirement | Implementation | MVP |
|---|---|---:|
| Voice history taking | STT + controlled conversational flow | ✅ |
| Touch history taking | Large buttons / cards | ✅ |
| Multilingual use | English + Hindi first; architecture supports more | ✅ |
| Chief complaint | Structured field | ✅ |
| HPI | Adaptive clinical question flow | ✅ |
| Past medical/surgical history | Structured capture | ✅ |
| Drug/allergy history | Repeating structured entries | ✅ |
| Family history | Structured capture | ✅ |
| Personal history | Structured capture | ✅ |
| Review of systems | Conditional questions | ✅ |
| AYUSH mode | Dashavidha Pariksha + Ahara-Vihara | ✅ |
| Red-flag triage | Deterministic rules | ✅ |
| Prescription OCR | OCR + extraction | ✅ |
| Lab report OCR | OCR + reference-range parsing | ✅ |
| Discharge summary OCR | OCR + entity extraction | 🟡 |
| Timeline | Date extraction + sorting | ✅ |
| Physician summary | LLM structured draft | ✅ |
| Physician editing | Section-level editor | ✅ |
| Consent | Explicit consent record | ✅ |
| FHIR export | FHIR R4 bundle | ✅ |
| ABDM | Adapter boundary + mock/sandbox path | 🟡 |
| Offline operation | Local queue + retry | 🟡 |
| Production clinical validation | Out of scope | ❌ |

---

# 3. Product definition

## 3.1 Product name

**MediKiosk**

## 3.2 One-line pitch

> **MediKiosk turns the first 10 minutes of patient history-taking into a guided digital intake completed before the doctor consultation.**

## 3.3 Core differentiator

Do not present the project as simply “an AI medical chatbot.” The innovation is the **pre-consultation clinical intake pipeline** combining:

1. patient self-service;
2. voice + touch input;
3. controlled adaptive history-taking;
4. AYUSH-specific information capture;
5. medical document intelligence;
6. red-flag escalation;
7. physician verification;
8. interoperable structured output.

---

# 4. Prototype boundaries

## 4.1 Build now

Build a web application that can be opened on a laptop, tablet, touchscreen kiosk, or phone-sized browser.

The demo should use synthetic patient data and optionally local sample documents.

## 4.2 Do not build in the first prototype

Do not attempt to build:

- a complete hospital management system;
- billing;
- appointment scheduling;
- autonomous diagnosis;
- prescription generation;
- real-world production ABDM onboarding;
- real patient deployment;
- custom LLM training;
- custom OCR model training unless needed later;
- complex identity verification with Aadhaar.

These can be shown as future integration points.

---

# 5. Actors and permissions

| Role | Main actions |
|---|---|
| Patient | Start intake, choose language, give consent, answer questions, upload documents, review own captured answers |
| Triage Staff | See urgent alerts, open case, assign priority, acknowledge alert |
| Physician | View patient cases, review/edit summary, inspect source evidence, confirm case |
| Admin | Configure language, clinical question bank, demo data, integrations |

Authentication for the prototype may be simple role selection. Production must use proper institutional authentication and authorization.

---

# 6. UX / screen specification

## 6.1 Patient screens

### Screen P01 — Welcome

Elements:

- MediKiosk logo
- hospital/department name
- “Start” button
- language cards
- accessibility controls
- help button

Requirements:

- very large tap targets;
- minimal text;
- audio instructions;
- no scrolling where possible.

### Screen P02 — Identity

Options:

```text
[ Hospital Token ]
[ ABHA ID ]
[ New / Walk-in Patient ]
```

For demo mode, token is sufficient.

Do not collect Aadhaar in the prototype.

### Screen P03 — Consent

Show:

- what data will be captured;
- why it is captured;
- what will be shared;
- who can see it;
- ability to decline;
- audio explanation.

Actions:

```text
[ Hear explanation ]
[ I understand and consent ]
[ Continue without consent ]
```

If consent is declined, the system should not process documents or send records to downstream integrations.

### Screen P04 — Mode selection

```text
How would you like to answer?

[ Speak ]
[ Tap answers ]
[ Speak + Tap ]
```

### Screen P05 — Chief complaint

Prompt:

> “What brought you to the hospital today?”

Voice:
- record button;
- waveform/recording state;
- transcript preview;
- replay audio.

Touch fallback:
- symptom categories;
- “Other” free text.

### Screen P06 — Adaptive interview

Display:

- current section;
- question;
- microphone button;
- answer choices where possible;
- progress indicator;
- repeat question;
- back/edit.

### Screen P07 — Documents

Options:

```text
[ Take photo ]
[ Upload image ]
[ Upload PDF ]
[ Skip ]
```

### Screen P08 — Processing

Visible stages:

```text
✓ Document received
✓ Text detected
✓ Clinical entities extracted
✓ Values validated
✓ Timeline updated
```

Do not expose internal model names unless useful for the judging/demo screen.

### Screen P09 — Patient confirmation

Show simple statements:

- main complaint;
- medicines;
- allergies;
- important previous history;
- documents uploaded.

Allow “Edit” before submission.

### Screen P10 — Completion

Show:

> “Your information has been sent to the clinical team.”

For urgent case:

> “Please wait. A staff member has been notified.”

---

# 7. Physician console

## 7.1 Dashboard

Cards:

```text
Waiting         18
Urgent           2
Completed       27
Documents       31
```

Queue columns:

| Token | Time | Complaint | Priority | Documents | Status |
|---|---|---|---|---|---|
| A-104 | 10:42 | Chest pain | URGENT | 2 | Waiting |
| A-105 | 10:47 | Fever | ROUTINE | 1 | Ready |

## 7.2 Case view

Layout:

```text
┌──────────────────────────────────────────────────────────┐
│ Patient / Token / Priority / Consent status              │
├──────────────┬──────────────────────────────┬────────────┤
│ Summary      │ Case details                 │ Evidence   │
│              │                              │            │
│ CC           │ HPI                          │ Document   │
│ HPI          │ Past history                 │ source     │
│ Medications  │ Drug / Allergy               │ snippets   │
│ Investig.    │ Family / Personal            │            │
│ AYUSH        │ ROS                          │            │
└──────────────┴──────────────────────────────┴────────────┘
```

Every AI-generated section must show:

- source = interview / document / derived;
- confidence;
- editable text;
- accept/reject or edit capability.

## 7.3 Confirm action

Buttons:

```text
[ Save Draft ]
[ Confirm Clinical Record ]
```

Confirmation is the gate before FHIR/HIS export.

---

# 8. Clinical interview engine

The interview must **not** be a free-running LLM chat.

Use a state machine.

```text
WELCOME
  ↓
IDENTITY
  ↓
CONSENT
  ↓
CHIEF_COMPLAINT
  ↓
HPI_CORE
  ↓
HPI_CONDITIONAL
  ↓
PAST_HISTORY
  ↓
MEDICATIONS
  ↓
ALLERGIES
  ↓
FAMILY_HISTORY
  ↓
PERSONAL_HISTORY
  ↓
ROS
  ↓
AYUSH_MODE? ─── yes → AYUSH_HISTORY
  ↓
DOCUMENTS
  ↓
SUMMARY_REVIEW
  ↓
SUBMIT
```

The backend stores the current state as part of the session, so the interview can resume after a network interruption.

---

# 9. Clinical data model

Use a canonical internal JSON model before FHIR conversion.

```json
{
  "case_id": "case_01HQ...",
  "patient": {
    "patient_id": "pat_001",
    "token": "A-104",
    "name": "Demo Patient",
    "age": 52,
    "sex": "male",
    "preferred_language": "hi"
  },
  "consent": {
    "granted": true,
    "purpose": ["clinical_intake", "document_processing", "record_sharing"],
    "timestamp": "2026-09-06T10:42:00+05:30"
  },
  "chief_complaint": {
    "text": "Chest pain for two days",
    "onset": "2 days ago",
    "source": "patient_voice",
    "confidence": 0.94
  },
  "hpi": {
    "location": "central chest",
    "character": "pressure",
    "severity": 7,
    "radiation": "left arm",
    "aggravating": ["walking"],
    "relieving": ["rest"],
    "associated_symptoms": ["breathlessness", "sweating"]
  },
  "past_history": [],
  "surgical_history": [],
  "medications": [],
  "allergies": [],
  "family_history": [],
  "personal_history": {},
  "review_of_systems": {},
  "ayush": null,
  "documents": [],
  "timeline": [],
  "triage": {
    "priority": "urgent",
    "rules_triggered": ["CHEST_PAIN_PLUS_DYSPNEA"]
  }
}
```

---

# 10. Question bank

Do not hard-code questions inside React components.

Store them as JSON/YAML so the clinical workflow can be edited without rewriting the UI.

Example:

```yaml
- id: cc_001
  section: chief_complaint
  prompt:
    en: "What brought you to the hospital today?"
    hi: "आज आप अस्पताल क्यों आए हैं?"
  input: voice_or_choice
  required: true

- id: hpi_001
  section: hpi
  trigger: complaint:chest_pain
  prompt:
    en: "When did the pain start?"
    hi: "दर्द कब शुरू हुआ?"
  field: hpi.onset
  input: voice_or_choice
  required: true

- id: hpi_002
  section: hpi
  trigger: complaint:chest_pain
  prompt:
    en: "Where exactly is the pain?"
    hi: "दर्द कहाँ हो रहा है?"
  field: hpi.location
  input: voice_or_choice
```

---

# 11. Adaptive questioning

## 11.1 Rule

The system should determine the next question from:

```text
current state
+ chief complaint
+ already known fields
+ missing required fields
+ conditional triggers
```

The LLM may propose which allowed question is most natural, but it may only select from the backend-approved question bank.

## 11.2 Example

Input:

> “मुझे दो दिन से सीने में दर्द है और सांस लेने में तकलीफ है।”

Extraction:

```json
{
  "complaint": "chest_pain",
  "duration": "2 days",
  "associated_symptom": "dyspnea"
}
```

Question planner then asks:

1. exact location;
2. character;
3. severity;
4. radiation;
5. exertional relationship;
6. associated red flags.

There is no need to ask again for duration because it is already known.

---

# 12. SOCRATES-style HPI module

Supported fields:

| Code | Field |
|---|---|
| S | Site |
| O | Onset |
| C | Character |
| R | Radiation |
| A | Associated symptoms |
| T | Timing |
| E | Exacerbating/relieving factors |
| S | Severity |

This is a history-collection framework, not a diagnostic algorithm.

The question bank must contain complaint-specific variants for at least:

- chest pain;
- abdominal pain;
- headache;
- fever;
- cough/breathlessness;
- vomiting/diarrhea;
- joint pain;
- weakness/dizziness;
- skin complaints;
- “other”.

---

# 13. Red-flag triage engine

Red-flag detection must be deterministic.

## 13.1 Architecture

```text
Structured answers
      ↓
Normalized symptoms
      ↓
Rule engine
      ↓
Priority + explanation + timestamp
```

## 13.2 Example rules

```yaml
- id: CHEST_PAIN_PLUS_DYSPNEA
  all:
    - symptom: chest_pain
    - symptom: breathlessness
  priority: urgent
  message: "Chest pain with breathing difficulty reported. Immediate human triage required."

- id: STROKE_LIKE_SYMPTOMS
  any:
    - symptom: facial_weakness
    - symptom: arm_weakness
    - symptom: speech_difficulty
  priority: urgent
  message: "Possible acute neurological red flag reported. Immediate human triage required."

- id: SEVERE_BREATHING_DIFFICULTY
  all:
    - symptom: severe_breathlessness
  priority: urgent
  message: "Severe breathing difficulty reported. Immediate human triage required."
```

## 13.3 What the UI says

Correct:

> **URGENT TRIAGE FLAG**  
> Chest pain and breathing difficulty were reported. A clinical staff member has been notified.

Incorrect:

> “You are having a heart attack.”

---

# 14. AYUSH history module

When department/mode = AYUSH, activate additional questions.

## 14.1 Dashavidha Pariksha fields

```text
Prakriti
Vikriti
Sara
Samhanana
Pramana
Satmya
Sattva
Ahara Shakti
Vyayama Shakti
Vaya
```

## 14.2 Ahara-Vihara

Capture:

- meal pattern;
- appetite;
- dietary preferences;
- hydration;
- sleep;
- exercise/activity;
- work pattern;
- daily routine;
- relevant habits.

## 14.3 AYUSH disclaimer

The prototype captures practitioner-relevant history fields. It should **not independently determine a final Ayurvedic diagnosis or treatment plan**.

---

# 15. Voice pipeline

## 15.1 Interface

Frontend:

```text
MediaRecorder
   ↓
POST /api/speech/transcribe
   ↓
Speech provider adapter
   ↓
Transcript
   ↓
Transcript confirmation
```

## 15.2 Provider abstraction

Create:

```python
class SpeechProvider(Protocol):
    async def transcribe(self, audio: bytes, language: str) -> Transcript:
        ...

    async def synthesize(self, text: str, language: str) -> bytes:
        ...
```

Implement providers:

- `sarvam_provider.py`
- `indicconformer_provider.py`
- `mock_provider.py`

Demo mode must use `mock_provider.py`.

## 15.3 Languages

Initial:

- English (`en-IN`)
- Hindi (`hi-IN`)

Architecture must support later:

- Marathi;
- Bengali;
- Tamil;
- Telugu;
- Kannada;
- Malayalam;
- Odia;
- Assamese;
- other supported Indian languages.

AI4Bharat IndicConformer currently provides ASR resources across India's 22 official languages, making it a useful local/open-source path. citeturn567922search3

---

# 16. Medical document pipeline

## 16.1 Supported inputs

- JPG
- JPEG
- PNG
- WEBP
- PDF

## 16.2 Pipeline

```text
Upload
  ↓
File validation
  ↓
Virus / size check
  ↓
PDF → page images if required
  ↓
Preprocessing
  ↓
Document classification
  ↓
OCR
  ↓
Layout/table extraction
  ↓
Clinical entity extraction
  ↓
Normalization
  ↓
Validation
  ↓
Structured JSON
```

## 16.3 Document classification

Classes:

```text
prescription
lab_report
discharge_summary
imaging_report
other
unknown
```

## 16.4 Recommended OCR strategy

Primary:

**PaddleOCR** for general multilingual OCR/document parsing.

Optional fallbacks:

- Tesseract for simple printed text;
- Donut for a research/handwriting path;
- EasyOCR where useful for difficult image inputs.

PaddleOCR's current project supports structured document parsing and multilingual document workflows, while its PP-Structure family can preserve document structure. citeturn567922search10

Do not make Donut mandatory for the MVP because a general document workflow with a simpler OCR stack is easier to deploy and debug.

---

# 17. Image preprocessing

Create:

`backend/app/services/ocr/preprocess.py`

Operations:

```text
resize
orientation correction
gray scale
contrast enhancement
denosing
adaptive thresholding
deskew
crop / page detection
```

Use OpenCV.

Keep the original upload so the physician can inspect the source.

---

# 18. Structured medical-document schema

Example lab report:

```json
{
  "document_id": "doc_001",
  "type": "lab_report",
  "document_date": "2026-08-28",
  "patient_name": "Demo Patient",
  "laboratory": "Demo Diagnostics",
  "tests": [
    {
      "name": "Glucose",
      "value": 145,
      "unit": "mg/dL",
      "reference_low": 70,
      "reference_high": 140,
      "status": "high",
      "source_text": "Glucose 145 mg/dL"
    }
  ],
  "raw_text": "...",
  "confidence": 0.91
}
```

Example medication:

```json
{
  "name_raw": "Metformin 500",
  "normalized_name": "Metformin",
  "strength": "500 mg",
  "frequency": "twice daily",
  "route": "oral",
  "duration": "30 days",
  "confidence": 0.88,
  "source_document_id": "doc_004"
}
```

---

# 19. Evidence / provenance

Every extracted field should have provenance where practical.

```json
{
  "field": "medications[0].name",
  "value": "Metformin",
  "source": "document",
  "document_id": "doc_004",
  "page": 1,
  "source_text": "Tab Metformin 500 mg",
  "confidence": 0.88
}
```

This is especially important for the physician review screen because AI output can be corrected without losing the original evidence.

---

# 20. Timeline engine

The timeline combines:

- interview-reported events;
- document dates;
- surgery dates;
- laboratory dates;
- prescription dates.

Sort descending by event date.

Example:

```text
2026-08-28  Lab report       Glucose 145 mg/dL ↑
2026-08-20  Prescription    Metformin 500 mg
2026-07-11  Discharge       Previous admission
2026-06-01  Interview       Hypertension history reported
```

When an exact date cannot be established, use `date_precision`:

```text
exact
month
year
relative
unknown
```

Never fabricate a date.

---

# 21. Abnormal laboratory values

Use the reference range contained in the report when available.

```python
if value < reference_low:
    status = "low"
elif value > reference_high:
    status = "high"
else:
    status = "normal"
```

The system should not invent ranges if the source does not supply them. If no reference range exists:

```text
status = "unknown"
```

UI example:

```text
Glucose
145 mg/dL
Reference: 70–140 mg/dL
Status: HIGH
Source: Lab Report — 28 Aug 2026
```

---

# 22. LLM architecture

## 22.1 Responsibilities

The LLM may perform:

- transcript → structured answer extraction;
- free-text normalization;
- allowed-next-question selection;
- summary generation;
- patient-friendly paraphrasing.

It must not be the source of truth for:

- emergency escalation;
- consent;
- permissions;
- record finalization;
- FHIR validity;
- dates when not present in source.

## 22.2 Structured output

Always request JSON matching a Pydantic schema.

Example:

```python
class HPIAnswer(BaseModel):
    onset: str | None = None
    location: str | None = None
    character: str | None = None
    severity: int | None = Field(default=None, ge=0, le=10)
    radiation: str | None = None
    aggravating_factors: list[str] = []
    relieving_factors: list[str] = []
    associated_symptoms: list[str] = []
```

Validate the response before saving.

---

# 23. Prompt design

Store prompts as version-controlled files, not strings scattered across code.

Directory:

```text
backend/app/prompts/
├── extract_answer_v1.txt
├── next_question_v1.txt
├── document_extract_v1.txt
└── summary_v1.txt
```

## 23.1 Extraction prompt

```text
You are a clinical intake extraction component.

Convert the patient's latest statement into ONLY the fields allowed by the supplied schema.
Do not diagnose.
Do not invent information.
Do not infer a value unless it is explicitly stated.
If a field is unknown, return null.
Preserve clinically relevant qualifiers such as duration, severity and uncertainty.
Return JSON only.
```

## 23.2 Summary prompt

```text
Create a concise physician-readable draft from the verified structured case data.
Use only supplied facts.
Do not add diagnoses that are not already documented by a clinician/source document.
Separate patient-reported history from extracted document findings.
Do not invent dates or medications.
Output the requested structured sections only.
```

---

# 24. Summary format

The final physician draft should use:

```text
1. Patient / encounter
2. Chief complaint
3. History of present illness
4. Past medical history
5. Past surgical history
6. Medications
7. Allergies
8. Family history
9. Personal / social history
10. Review of systems
11. AYUSH history, when enabled
12. Prior investigations
13. Prior documents / timeline
14. Red-flag / triage status
15. Missing or uncertain information
```

The summary should distinguish:

- **reported by patient**;
- **found in document**;
- **confirmed/edited by physician**.

---

# 25. Backend API

Base URL:

`/api`

## 25.1 Sessions

### POST `/sessions`

Creates patient session.

Request:

```json
{
  "token": "A-104",
  "language": "hi",
  "department": "ayush"
}
```

Response:

```json
{
  "session_id": "sess_123",
  "case_id": "case_123",
  "state": "identity"
}
```

### GET `/sessions/{session_id}`

Returns current state.

### POST `/sessions/{session_id}/consent`

Stores consent decision.

---

## 25.2 Interview

### GET `/interview/{session_id}/next`

Returns next approved question.

### POST `/interview/{session_id}/answer`

```json
{
  "question_id": "hpi_001",
  "input_mode": "voice",
  "transcript": "It started two days ago"
}
```

Response:

```json
{
  "saved": true,
  "extracted_fields": {
    "hpi.onset": "2 days ago"
  },
  "next_question_id": "hpi_002",
  "triage": null
}
```

---

## 25.3 Speech

### POST `/speech/transcribe`

Multipart upload.

### POST `/speech/synthesize`

```json
{
  "text": "कृपया दर्द के बारे में बताइए",
  "language": "hi"
}
```

---

## 25.4 Documents

### POST `/documents/upload`

Multipart.

Response:

```json
{
  "document_id": "doc_001",
  "status": "processing"
}
```

### GET `/documents/{document_id}`

Returns extraction status and structured data.

### POST `/documents/{document_id}/reprocess`

Allows retry with another OCR provider.

---

## 25.5 Triage

### GET `/triage/active`

Returns urgent cases.

### POST `/triage/{alert_id}/acknowledge`

Marks alert as seen.

---

## 25.6 Cases

### GET `/cases/{case_id}`

Full case.

### GET `/cases?status=ready`

Physician queue.

### PATCH `/cases/{case_id}/summary`

Saves doctor edits.

### POST `/cases/{case_id}/confirm`

Locks/versions the clinician-confirmed case and starts export.

---

## 25.7 FHIR

### POST `/fhir/export/{case_id}`

Returns FHIR Bundle and destination status.

### GET `/fhir/export/{case_id}`

Returns last export.

---

# 26. Database design

Use PostgreSQL.

## Tables

```text
patients
sessions
consents
questions
answers
triage_alerts
documents
document_extractions
document_entities
clinical_timelines
case_summaries
case_versions
users
audit_logs
fhir_exports
sync_queue
```

## 26.1 patients

```sql
id UUID PRIMARY KEY
external_token TEXT UNIQUE
name TEXT
age INTEGER
sex TEXT
preferred_language TEXT
created_at TIMESTAMPTZ
updated_at TIMESTAMPTZ
```

## 26.2 sessions

```sql
id UUID PRIMARY KEY
patient_id UUID REFERENCES patients(id)
state TEXT NOT NULL
mode TEXT
department TEXT
started_at TIMESTAMPTZ
completed_at TIMESTAMPTZ
is_demo BOOLEAN DEFAULT FALSE
```

## 26.3 consents

```sql
id UUID PRIMARY KEY
session_id UUID REFERENCES sessions(id)
granted BOOLEAN NOT NULL
purposes JSONB
consent_text_version TEXT
created_at TIMESTAMPTZ
revoked_at TIMESTAMPTZ NULL
```

## 26.4 answers

```sql
id UUID PRIMARY KEY
session_id UUID REFERENCES sessions(id)
question_id TEXT
input_mode TEXT
raw_answer TEXT
structured_value JSONB
confidence NUMERIC
source TEXT
created_at TIMESTAMPTZ
```

## 26.5 documents

```sql
id UUID PRIMARY KEY
session_id UUID REFERENCES sessions(id)
file_name TEXT
mime_type TEXT
sha256 TEXT
document_type TEXT
storage_path TEXT
processing_status TEXT
uploaded_at TIMESTAMPTZ
```

## 26.6 audit_logs

```sql
id UUID PRIMARY KEY
actor_type TEXT
actor_id UUID NULL
action TEXT
entity_type TEXT
entity_id UUID
details JSONB
created_at TIMESTAMPTZ
```

---

# 27. FHIR interoperability

The confirmed case should be translated to a FHIR R4 Bundle.

## Minimum resources

```text
Patient
Encounter
Consent
Composition
Observation
MedicationStatement or MedicationRequest, where appropriate
AllergyIntolerance
DocumentReference
Condition only when clinician/source data supports it
```

Do not convert the AI's suspected diagnosis into a `Condition` merely because the LLM mentioned it.

## 27.1 Bundle skeleton

```json
{
  "resourceType": "Bundle",
  "type": "transaction",
  "entry": []
}
```

Each resource must have a deterministic mapping from the canonical case model.

---

# 28. FHIR development server

Use a local FHIR server for the prototype.

Recommended options:

- HAPI FHIR JPA Server;
- Medplum in a development environment.

The HAPI FHIR starter project is intended as a deployable starter for HAPI FHIR JPA, and the Medplum intake demo provides useful patterns for patient intake, conditional forms, and mapping intake data to FHIR resources. citeturn567922search1turn567922search0

For a hackathon demo, HAPI FHIR is a good neutral interoperability target.

---

# 29. ABDM integration boundary

Do not couple the core case-taking logic directly to ABDM.

Create:

```python
class HealthRecordAdapter(Protocol):
    async def create_patient(...): ...
    async def submit_bundle(...): ...
    async def fetch_patient_records(...): ...
```

Implement:

```text
MockHealthRecordAdapter
FHIRServerAdapter
ABDMAdapter (future/sandbox)
```

The demo can therefore prove interoperability without depending on live credentials.

---

# 30. Offline-first behavior

Patient state should survive a temporary network failure.

Frontend:

```text
IndexedDB
   ↓
local session state
   ↓
sync queue
   ↓
retry when online
```

Store only what is necessary.

Queue item:

```json
{
  "id": "sync_001",
  "operation": "answer",
  "session_id": "sess_123",
  "payload": {},
  "attempts": 0,
  "created_at": "..."
}
```

Do not indefinitely cache sensitive documents on shared kiosks.

---

# 31. Security requirements for prototype

Minimum:

- no API keys in frontend;
- environment variables on backend;
- file type validation;
- upload size limit;
- randomized storage names;
- access-controlled case endpoints;
- audit logs;
- consent status checked before sharing;
- temporary files deleted on session closure;
- demo data clearly separated from real data;
- no real patient data in Git.

The uploaded MediParse reference README currently exposes a Gemini variable in its client-oriented deployment pattern; **do not copy that approach** for MediKiosk. Keep AI credentials on the backend. fileciteturn2file1L265-L313

---

# 32. Frontend architecture

Recommended structure:

```text
frontend/
├── src/
│   ├── app/
│   │   ├── router.tsx
│   │   └── providers.tsx
│   ├── pages/
│   │   ├── patient/
│   │   │   ├── WelcomePage.tsx
│   │   │   ├── IdentityPage.tsx
│   │   │   ├── ConsentPage.tsx
│   │   │   ├── ModePage.tsx
│   │   │   ├── InterviewPage.tsx
│   │   │   ├── DocumentsPage.tsx
│   │   │   ├── ReviewPage.tsx
│   │   │   └── CompletePage.tsx
│   │   └── doctor/
│   │       ├── DashboardPage.tsx
│   │       ├── CasePage.tsx
│   │       └── TriagePage.tsx
│   ├── components/
│   │   ├── VoiceRecorder.tsx
│   │   ├── AudioPrompt.tsx
│   │   ├── QuestionCard.tsx
│   │   ├── TouchChoices.tsx
│   │   ├── DocumentUploader.tsx
│   │   ├── ProcessingSteps.tsx
│   │   ├── CaseSection.tsx
│   │   ├── EvidencePanel.tsx
│   │   ├── TriageBanner.tsx
│   │   └── Timeline.tsx
│   ├── services/
│   │   ├── api.ts
│   │   ├── speech.ts
│   │   └── offline.ts
│   ├── state/
│   │   └── sessionStore.ts
│   ├── i18n/
│   │   ├── en.ts
│   │   └── hi.ts
│   ├── types/
│   └── utils/
```

---

# 33. Backend architecture

```text
backend/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── api/
│   │   ├── sessions.py
│   │   ├── interview.py
│   │   ├── speech.py
│   │   ├── documents.py
│   │   ├── cases.py
│   │   ├── triage.py
│   │   └── fhir.py
│   ├── services/
│   │   ├── dialogue/
│   │   │   ├── engine.py
│   │   │   ├── planner.py
│   │   │   └── extractor.py
│   │   ├── speech/
│   │   ├── ocr/
│   │   ├── documents/
│   │   ├── summary/
│   │   ├── triage/
│   │   └── fhir/
│   ├── clinical/
│   │   ├── questions/
│   │   ├── rules/
│   │   ├── terminology/
│   │   └── schemas/
│   ├── integrations/
│   │   ├── gemini.py
│   │   ├── sarvam.py
│   │   ├── paddleocr.py
│   │   ├── hapi_fhir.py
│   │   └── abdm.py
│   ├── models/
│   ├── schemas/
│   ├── prompts/
│   └── tests/
└── requirements.txt
```

---

# 34. Demo mode architecture

`DEMO_MODE=true` must make the project work with no paid external API.

```text
DEMO_MODE
   ├── MockSpeechProvider
   ├── MockLLMProvider
   ├── MockOCRProvider
   └── Local HAPI/Mock FHIR
```

The demo mode should use a scripted patient journey.

Example:

```text
Token: A-104
Language: Hindi
Complaint: chest pain
Duration: 2 days
Associated: breathlessness, sweating
Document: demo_lab_report.jpg
Lab: glucose 145 mg/dL
```

A judge should be able to run the complete flow repeatedly and receive consistent output.

---

# 35. Demo fixtures

Create:

```text
demo/
├── patients/
│   ├── urgent_chest_pain.json
│   ├── fever_case.json
│   └── ayush_joint_pain.json
├── documents/
│   ├── lab_report.png
│   ├── prescription.png
│   └── discharge_summary.pdf
├── audio/
│   └── hindi_chest_pain.wav
└── expected/
    ├── urgent_case.json
    └── ayush_case.json
```

Do not include real patient information.

---

# 36. Recommended open-source building blocks

| Project | Use |
|---|---|
| Medplum Patient Intake Demo | FHIR-native intake UX patterns and conditional questionnaires |
| HAPI FHIR JPA Server Starter | Local FHIR R4 interoperability server |
| AI4Bharat IndicConformerASR | Local Indian-language ASR path |
| PaddleOCR | Primary OCR/document parsing |
| Tesseract | Lightweight OCR fallback |
| NAVER Donut | Research path for handwriting/document understanding |
| EasyOCR | Additional OCR fallback |

The current Medplum patient-intake demo explicitly demonstrates conditional intake flows and transformation of intake information into structured FHIR resources. citeturn567922search0turn567922search11

AI4Bharat's IndicConformer repository provides multilingual ASR models covering 22 official Indian languages. citeturn567922search3

PaddleOCR currently supports structured document parsing and multilingual document workflows and is therefore the recommended first OCR implementation rather than starting with a custom model. citeturn567922search10

---

# 37. How to use the supplied reference projects

## Reference A — MediParse.AI

Use as inspiration for:

- React/Vite/Tailwind frontend;
- upload experience;
- visible extraction pipeline;
- structured JSON output;
- medical-document workflow.

Its README explicitly describes ingestion → preprocessing → OCR → entity recognition → normalization → JSON construction. fileciteturn3file1L219-L247

## Reference B — Medical Prescription OCR

Use as inspiration for:

- Donut model usage;
- handwritten prescription OCR;
- structured prescription output;
- Hugging Face model/dataset approach.

Its README documents Donut inference and structured prescription extraction. fileciteturn2file2L424-L477

## Reference C — medical-data-extraction

Use as inspiration for:

- PDF → image conversion;
- preprocessing;
- parser separation;
- OCR/service modularity;
- testable extraction functions.

The project separates OCR extraction, preprocessing, prescription parsing, patient-details parsing, API, database and frontend layers. fileciteturn2file3L625-L653

Do not clone these projects wholesale. Extract patterns, dependencies, and ideas while keeping MediKiosk's architecture internally consistent.

---

# 38. Environment variables

`.env.example`

```env
APP_ENV=development
DEMO_MODE=true

DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/medikiosk
SESSION_SECRET=replace_me

LLM_PROVIDER=mock
GEMINI_API_KEY=

SPEECH_PROVIDER=mock
SARVAM_API_KEY=

OCR_PROVIDER=paddleocr

FHIR_BASE_URL=http://localhost:8080/fhir

MAX_UPLOAD_MB=15
```

Never commit `.env`.

---

# 39. Docker Compose

Services:

```yaml
services:
  postgres:
    image: postgres:16

  fhir:
    image: hapiproject/hapi:latest

  backend:
    build: ./backend
    depends_on:
      - postgres
      - fhir

  frontend:
    build: ./frontend
    depends_on:
      - backend
```

Pin production image versions rather than using `latest` after the prototype has stabilized.

---

# 40. Local development commands

```bash
# Clone
 git clone <your-repository>
 cd medikiosk

# Start infrastructure
 docker compose up -d postgres fhir

# Backend
 cd backend
 python -m venv .venv

# Windows
 .venv\Scripts\activate

# Linux/macOS
 source .venv/bin/activate

 pip install -r requirements.txt
 uvicorn app.main:app --reload --port 8000

# Frontend — separate terminal
 cd frontend
 npm install
 npm run dev
```

Frontend:

`http://localhost:5173`

Backend:

`http://localhost:8000`

Swagger:

`http://localhost:8000/docs`

FHIR:

`http://localhost:8080/fhir`

---

# 41. Minimal dependency set

## Frontend

```text
react
react-dom
react-router-dom
@tanstack/react-query
tailwindcss
lucide-react
i18next / react-i18next
```

Add only what the implementation needs.

## Backend

```text
fastapi
uvicorn
pydantic
pydantic-settings
sqlalchemy
asyncpg
alembic
python-multipart
httpx
opencv-python
pillow
paddleocr
```

Add provider SDKs only when they are actually used.

---

# 42. Testing strategy

## 42.1 Unit tests

Test:

- question-state transitions;
- trigger conditions;
- red-flag rules;
- normalization;
- lab reference range logic;
- date parsing;
- FHIR mapping;
- consent enforcement.

Example:

```python
def test_chest_pain_dyspnea_triggers_urgent():
    result = triage_engine.evaluate({
        "symptoms": ["chest_pain", "breathlessness"]
    })
    assert result.priority == "urgent"
```

## 42.2 API tests

Test the complete session flow using mock providers.

## 42.3 UI tests

At minimum test:

- start session;
- consent;
- touch answer;
- voice transcript fallback;
- document upload;
- urgent alert;
- doctor confirmation.

## 42.4 Golden-case tests

For each demo case, maintain expected JSON.

```text
input transcript
→ expected fields
→ expected triage
→ expected summary sections
```

This prevents prompt changes from silently breaking the demo.

---

# 43. Evaluation metrics

Do not claim clinical accuracy without validation.

Prototype metrics:

| Metric | Target |
|---|---:|
| Touch flow completion | ≥ 95% in scripted test |
| Session persistence | 100% in offline simulation |
| Red-flag rule recall on test cases | 100% |
| JSON schema validation | 100% |
| Successful FHIR bundle generation | ≥ 95% |
| Demo document extraction | ≥ 90% field-level correctness on curated fixtures |
| Physician edit workflow | 100% of AI sections editable |

For voice/OCR, report measured prototype performance rather than invented benchmark numbers.

---

# 44. Accessibility requirements

Patient UI:

- minimum large touch targets;
- high contrast;
- simple wording;
- audio prompts;
- no dependency on typing;
- repeat button;
- visual confirmation after speaking;
- progress indicator;
- error recovery without restarting.

For elderly users:

```text
[ Tap ]      [ Tap ]
large cards
large text
audio prompts
minimal scrolling
```

---

# 45. Failure handling

Every external component can fail.

## Speech failure

```text
Speech service unavailable
        ↓
Show transcript input / touch alternatives
```

## OCR failure

```text
OCR failed
  ↓
Allow retry
  ↓
Try fallback OCR
  ↓
Allow physician to inspect original document
```

## LLM failure

```text
LLM unavailable
  ↓
Continue deterministic question bank
  ↓
Store raw transcript
  ↓
Generate template-based draft
```

## FHIR failure

```text
FHIR unavailable
  ↓
Store confirmed case
  ↓
Queue export
  ↓
Retry
```

The patient should not be forced to repeat the entire intake because one integration failed.

---

# 46. Auditability

Log:

```text
SESSION_STARTED
CONSENT_GRANTED
QUESTION_ANSWERED
DOCUMENT_UPLOADED
OCR_COMPLETED
REDFLAG_RAISED
SUMMARY_GENERATED
DOCTOR_EDITED
CASE_CONFIRMED
FHIR_EXPORT_ATTEMPTED
FHIR_EXPORT_SUCCEEDED
SESSION_CLOSED
```

Do not log raw medical data into normal application logs unless necessary.

---

# 47. Privacy / session cleanup

When a patient completes a session:

1. save the required clinical record;
2. save audit event;
3. export if consent permits;
4. delete temporary recording files;
5. delete temporary processing images;
6. clear browser session data;
7. retain only the configured clinical record and audit data.

For shared kiosk mode, automatically return to the Welcome screen after a timeout.

---

# 48. Versioning

Every AI-generated case should have a version.

```text
case v1 — AI draft
case v2 — physician edit
case v3 — physician confirmed
```

Never overwrite confirmed clinical content silently.

Store:

```json
{
  "case_version": 3,
  "status": "confirmed",
  "confirmed_by": "doctor_001",
  "confirmed_at": "..."
}
```

---

# 49. Prototype dashboard analytics

Add a small analytics page for the judging/demo presentation.

Metrics:

```text
Patients processed today
Average intake completion time
Voice vs touch usage
Urgent flags
Documents processed
Cases ready for physician
Average physician edit rate
FHIR exports succeeded
```

Use synthetic/demo data only.

---

# 50. Recommended repository milestones

## Milestone 1 — Foundation

Create:

- monorepo;
- React app;
- FastAPI app;
- PostgreSQL;
- Docker Compose;
- environment configuration.

Definition of done:

```text
localhost:5173 works
localhost:8000/docs works
PostgreSQL connection works
```

## Milestone 2 — Touch intake

Implement:

- Welcome;
- identity;
- consent;
- question bank;
- state machine;
- touch answers;
- case JSON.

Definition of done:

> A complete patient history can be entered without AI.

## Milestone 3 — Triage

Implement deterministic red-flag rules.

Definition of done:

> Test cases correctly trigger urgent alerts.

## Milestone 4 — Voice

Implement MediaRecorder + mock speech provider first, then real provider.

Definition of done:

> Spoken answer becomes structured answer.

## Milestone 5 — Document intelligence

Implement:

- upload;
- preprocessing;
- OCR;
- classification;
- extraction;
- timeline.

Definition of done:

> A demo lab report produces structured values.

## Milestone 6 — Summary

Implement:

- case synthesis;
- provenance;
- uncertainty;
- physician editor.

Definition of done:

> Doctor can edit and confirm the case.

## Milestone 7 — FHIR

Implement:

- Patient;
- Encounter;
- Consent;
- Composition;
- Observation;
- AllergyIntolerance;
- DocumentReference.

Definition of done:

> Confirmed case becomes a valid FHIR Bundle and appears in HAPI FHIR.

## Milestone 8 — AYUSH

Implement Dashavidha + Ahara-Vihara.

## Milestone 9 — Offline

Implement local queue and recovery.

## Milestone 10 — Judging polish

Implement:

- animations kept subtle;
- large kiosk UI;
- demo reset button;
- seeded cases;
- visible AI/OCR pipeline;
- analytics dashboard;
- clean error states.

---

# 51. Five-minute judging demo

Use exactly one scripted patient for the main story.

## Step 1 — Start

Select Hindi.

## Step 2 — Patient input

Say:

> “मुझे दो दिन से सीने में दर्द है और सांस लेने में तकलीफ हो रही है।”

## Step 3 — AI extraction

Show:

```text
Chief complaint: Chest pain
Duration: 2 days
Associated symptom: Breathlessness
```

## Step 4 — Safety

Immediately show:

```text
URGENT TRIAGE FLAG
Chest pain + breathing difficulty reported.
Human triage required.
```

## Step 5 — Continue history

Answer remaining touch questions.

## Step 6 — Upload document

Upload demo lab report.

Show:

```text
OCR complete
Glucose 145 mg/dL — HIGH
```

## Step 7 — Summary

Show physician draft.

## Step 8 — Doctor edit

Change one generated sentence.

## Step 9 — Confirm

Click:

`Confirm Clinical Record`

## Step 10 — FHIR

Show generated Bundle / HAPI FHIR record.

## Step 11 — Close session

Show:

```text
Session closed
Temporary files removed
```

This is the core demo narrative.

---

# 52. What judges should understand in 30 seconds

The demo should communicate these five points visually:

```text
1. Patient does history themselves.
2. They can speak or tap.
3. Old paper records become structured data.
4. Emergency symptoms are escalated deterministically.
5. Doctor receives an editable interoperable case, not an AI diagnosis.
```

---

# 53. Common implementation mistakes to avoid

## Mistake 1 — Building a generic chatbot

Avoid.

Use a clinical question/state engine.

## Mistake 2 — Putting API keys in React

Avoid.

All secret provider keys stay in FastAPI environment variables.

## Mistake 3 — Letting LLM decide emergency severity

Avoid.

Use deterministic rules.

## Mistake 4 — Trying to train every model

Avoid.

Use pretrained/open-source components and focus engineering effort on orchestration.

## Mistake 5 — Building ABDM first

Avoid.

Build the complete local workflow first, then add a FHIR/ABDM adapter.

## Mistake 6 — Showing raw AI text to doctors

Avoid.

Normalize into structured sections and display evidence.

## Mistake 7 — No demo mode

Avoid.

Judging environments are unpredictable. Demo mode must run without external APIs.

---

# 54. Definition of “working prototype”

The prototype is considered complete when all of the following work locally:

```text
[ ] Start patient session
[ ] Select language
[ ] Record consent
[ ] Complete touch interview
[ ] Complete voice interview with mock provider
[ ] Detect urgent rule
[ ] Upload document
[ ] OCR document
[ ] Extract at least one clinical entity
[ ] Add item to timeline
[ ] Flag abnormal lab value
[ ] Generate structured case summary
[ ] Edit summary as physician
[ ] Confirm case
[ ] Generate FHIR Bundle
[ ] Store/export to local FHIR server
[ ] Close session and clean temp data
[ ] Reset demo and repeat
```

---

# 55. Suggested team division

For a 4–6 person hackathon team:

| Member | Ownership |
|---|---|
| 1 | Frontend patient/kiosk UX |
| 2 | Backend/API/database |
| 3 | AI/LLM dialogue + summary |
| 4 | OCR/document pipeline |
| 5 | FHIR/ABDM/interoperability |
| 6 | Integration, testing, demo and deployment |

Use shared schemas and API contracts so the modules can be developed independently.

---

# 56. First 24 implementation tasks

Start in this order:

```text
01. Create GitHub repository
02. Create frontend/backend folders
03. Add Docker Compose
04. Add PostgreSQL
05. Add FastAPI health endpoint
06. Add React routing
07. Build Welcome screen
08. Build Identity screen
09. Build Consent screen
10. Create Session API
11. Create question-bank YAML
12. Create interview state machine
13. Build QuestionCard
14. Build TouchChoices
15. Save answers to PostgreSQL
16. Build triage rule engine
17. Build triage UI
18. Add demo patient fixture
19. Add document upload API
20. Add PaddleOCR adapter
21. Add document extraction schema
22. Build physician dashboard
23. Build summary editor
24. Build FHIR export
```

Only after this path works should you connect live speech and live LLM APIs.

---

# 57. Recommended branch structure

```text
main
├── develop
├── feature/patient-kiosk
├── feature/interview-engine
├── feature/triage
├── feature/document-ocr
├── feature/summary
├── feature/fhir
└── feature/offline
```

Commit style:

```text
feat: add clinical question state machine
feat: add document extraction pipeline
fix: prevent consentless FHIR export
feat: add urgent triage rule
```

---

# 58. README structure for final GitHub repository

Keep the user-facing README shorter than this build specification.

Recommended:

```text
README.md
├── Hero
├── Problem
├── Solution
├── Key Features
├── Architecture
├── Demo Screenshots
├── Quick Start
├── Demo Mode
├── Open Source Components
├── API / FHIR
├── Safety + Privacy
├── Roadmap
└── License
```

This document should be stored separately as:

```text
docs/PROTOTYPE_BUILD_SPEC.md
```

---

# 59. Final architecture

```text
                         ┌─────────────────────────────┐
                         │          PATIENT             │
                         │      Kiosk / Tablet UI      │
                         └──────────────┬──────────────┘
                                        │
                              Voice / Touch / Docs
                                        │
                                        ▼
┌────────────────────────────────────────────────────────────────┐
│                         FASTAPI BACKEND                         │
│                                                                │
│  Session Service ── Interview Engine ── Clinical State        │
│          │                    │                  │              │
│          │                    ├── LLM Extractor  │              │
│          │                    └── Question Bank  │              │
│          │                                       │              │
│          ├── Speech Adapter                       ├── Triage    │
│          │                                       │              │
│          ├── Document Service ── OCR ── Entities │              │
│          │                                       │              │
│          └────────────────── Case Model ─────────┘              │
│                                  │                               │
│                          Summary Generator                       │
│                                  │                               │
│                          Physician Review                        │
│                                  │                               │
│                          FHIR Mapper                             │
└──────────────────────────────┬───┬──────────────────────────────┘
                               │   │
                         ┌─────┘   └───────┐
                         ▼                 ▼
                  PostgreSQL          HAPI FHIR
                         │                 │
                         ▼                 ▼
                    Audit/Data       FHIR R4 Bundle
                         │
                         ▼
                    ABDM Adapter
```

---

# 60. Final engineering principle

**Build the deterministic shell first and add AI inside it.**

The project should remain functional when:

- the LLM is unavailable;
- speech recognition fails;
- OCR fails;
- FHIR is offline;
- the internet disappears temporarily.

AI should improve the experience, not become the single point of failure.

The finished system should feel like a **real clinical intake product with AI inside it**, not a chatbot surrounded by mock screens.

---

# 61. Prototype disclaimer

This implementation is for a Smart India Hackathon prototype using synthetic/demo data. It is not a validated medical device, does not replace clinical judgment, and must not be deployed for real patient care without appropriate clinical validation, institutional governance, security/privacy review, and regulatory compliance.

