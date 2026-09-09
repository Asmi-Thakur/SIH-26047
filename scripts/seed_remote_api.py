"""Seed the deployed MediKiosk backend directly via HTTP API.

Usage:
  python scripts/seed_remote_api.py --base https://sih-26047-production.up.railway.app
"""
import argparse
import io
import json
import sys
import urllib.error
import urllib.request
from PIL import Image, ImageDraw, ImageFont

def api_call(base: str, method: str, path: str, payload: dict | None = None) -> tuple[int, dict]:
    url = f"{base.rstrip('/')}{path}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"}
    
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            return exc.code, json.loads(body)
        except Exception:
            return exc.code, {"raw_error": body}

def upload_lab_image(base: str, session_id: str) -> str:
    """Generate synthetic lab report and upload as multipart/form-data."""
    img = Image.new("RGB", (900, 360), "white")
    draw = ImageDraw.Draw(img)
    lines = [
        "Demo Diagnostics Laboratory",
        "Patient: Demo Patient (A-902)   Date: 2026-08-28",
        "Glucose 145 mg/dL (Ref 70-140) HIGH",
        "Haemoglobin 13.5 g/dL (Ref 13-17)",
        "Creatinine 1.1 mg/dL (Ref 0.7-1.3)",
    ]
    y = 30
    for line in lines:
        draw.text((40, y), line, fill="black")
        y += 60
    
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    img_bytes = buf.getvalue()

    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    body = bytearray()
    
    body.extend(f"--{boundary}\r\n".encode())
    body.extend(b'Content-Disposition: form-data; name="session_id"\r\n\r\n')
    body.extend(f"{session_id}\r\n".encode())
    
    body.extend(f"--{boundary}\r\n".encode())
    body.extend(b'Content-Disposition: form-data; name="file"; filename="lab_report.png"\r\n')
    body.extend(b"Content-Type: image/png\r\n\r\n")
    body.extend(img_bytes)
    body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode())

    req = urllib.request.Request(
        f"{base.rstrip('/')}/api/documents/upload",
        data=bytes(body),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST"
    )
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        return res["document_id"]

def run_answers(base: str, session_id: str, answers: list[tuple[str, dict]]):
    for q_id, val in answers:
        payload = {
            "question_id": q_id,
            "input_mode": "touch",
            "choice_codes": val.get("choice_codes"),
            "text": val.get("text")
        }
        status, res = api_call(base, "POST", f"/api/interview/{session_id}/answer", payload)
        if status != 200:
            print(f"    [Warning] Answering {q_id} returned {status}: {res}")

def seed_remote(base: str):
    print(f"Testing connectivity to {base} ...")
    status, health = api_call(base, "GET", "/api/health")
    if status != 200:
        print(f"Error: Target backend returned HTTP {status}: {health}")
        sys.exit(1)
    print(f"Connected! Backend status: {health.get('status')}, DB: {health.get('database')}\n")

    # 1. A-901 (Urgent Chest Pain)
    print("Seeding A-901: Urgent Chest Pain...")
    _, s1 = api_call(base, "POST", "/api/sessions", {"token": "A-901", "language": "en", "demo": True})
    sess1 = s1["session_id"]
    api_call(base, "POST", f"/api/sessions/{sess1}/consent", {"granted": True, "purposes": ["clinical_intake"], "consent_text_version": "v1"})
    run_answers(base, sess1, [
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
    ])
    api_call(base, "GET", f"/api/cases/by-session/{sess1}")
    print("  ✓ A-901 created & triage alert triggered.")

    # 2. A-902 (Routine Fever + Document OCR)
    print("Seeding A-902: Routine Fever + Lab Report...")
    _, s2 = api_call(base, "POST", "/api/sessions", {"token": "A-902", "language": "hi", "demo": True})
    sess2 = s2["session_id"]
    api_call(base, "POST", f"/api/sessions/{sess2}/consent", {"granted": True, "purposes": ["clinical_intake", "document_processing"]})
    run_answers(base, sess2, [
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
    ])
    try:
        doc_id = upload_lab_image(base, sess2)
        api_call(base, "POST", f"/api/documents/{doc_id}/reprocess")
        print("  ✓ Lab report uploaded and OCR processed.")
    except Exception as e:
        print(f"  [Notice] Document upload skipped: {e}")
    api_call(base, "GET", f"/api/cases/by-session/{sess2}")
    print("  ✓ A-902 created.")

    # 3. A-903 (AYUSH Joint Pain)
    print("Seeding A-903: AYUSH Joint Pain + Dashavidha...")
    _, s3 = api_call(base, "POST", "/api/sessions", {"token": "A-903", "language": "en", "department": "ayush", "demo": True})
    sess3 = s3["session_id"]
    api_call(base, "POST", f"/api/sessions/{sess3}/consent", {"granted": True, "purposes": ["clinical_intake"]})
    run_answers(base, sess3, [
        ("cc_001", {"choice_codes": ["joint_pain"]}),
        ("hpi_001", {"choice_codes": ["months"]}),
        ("hpi_002", {"choice_codes": ["intermittent"]}),
        ("hpi_003", {"choice_codes": ["moderate"]}),
        ("hpi_004", {"choice_codes": ["none"]}),
        ("hpi_005", {"text": "both knees"}),
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
    ])
    api_call(base, "GET", f"/api/cases/by-session/{sess3}")
    print("  ✓ A-903 created.")

    print("\n✅ Successfully seeded all 3 demo cases into the deployed backend!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="https://sih-26047-production.up.railway.app")
    args = parser.parse_args()
    seed_remote(args.base)