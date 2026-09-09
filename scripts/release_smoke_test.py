"""Release smoke test (API level) — run against a freshly seeded database.

Demonstrates the three demo journeys end-to-end through the real HTTP API:

  A-901 urgent   → confirm → FHIR export → confirmed case rejects edits
  A-902 routine  → document OCR provenance → confirm → export
  A-903 AYUSH    → Dashavidha case.ayush → confirm → export

Usage:
  backend/.venv/bin/python scripts/release_smoke_test.py --base http://127.0.0.1:8001
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request

failures: list[str] = []


def call(base: str, method: str, path: str, payload: dict | None = None):
    req = urllib.request.Request(
        base + path,
        data=json.dumps(payload).encode() if payload is not None else None,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode())


def check(label: str, ok: bool, detail: str = "") -> None:
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {label}{(' — ' + detail) if detail else ''}")
    if not ok:
        failures.append(label)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8001")
    args = parser.parse_args()
    base = args.base.rstrip("/")

    status, health = call(base, "GET", "/api/health")
    check("backend healthy", status == 200 and health.get("status") == "ok", str(health.get("status")))

    status, cases = call(base, "GET", "/api/cases")
    items = cases if isinstance(cases, list) else cases.get("items", cases.get("cases", []))
    by_token = {}
    for item in items:
        # wire contract: case_id, plus token echoed in the summary/list payload
        token = item.get("token") or (item.get("session") or {}).get("token") or ""
        by_token[str(token)[:5]] = item["case_id"]
    check("3 seeded cases listed", len(items) == 3, f"n={len(items)}")

    for token in ("A-901", "A-902", "A-903"):
        case_id = by_token.get(token)
        if not case_id:
            check(f"{token} present in queue", False, "missing")
            continue
        status, case = call(base, "GET", f"/api/cases/{case_id}")
        check(f"{token} case readable", status == 200)
        yield_check = case.get("provenance") is not None or "provenance" in json.dumps(case)
        check(f"{token} provenance present", yield_check)

    # A-901 — urgent triage → confirm → export → immutability
    a901 = by_token["A-901"]
    status, case = call(base, "GET", f"/api/cases/{a901}")
    tri = json.dumps(case)
    check("A-901 deterministic urgent triage", "URGENT" in tri.upper() or "urgent" in tri)
    status, _ = call(base, "POST", f"/api/cases/{a901}/confirm")
    check("A-901 confirm accepted", status == 200)
    status, body = call(base, "POST", f"/api/fhir/export/{a901}")
    check("A-901 FHIR export after confirm", status == 200 and body.get("status") == "succeeded", str(body.get("status")))
    status, case = call(base, "GET", f"/api/cases/{a901}")
    check("A-901 locked after confirm", case.get("status") == "confirmed", str(case.get("status")))
    status, _ = call(base, "PATCH", f"/api/cases/{a901}/summary", {"summary": {"chief_complaint": "TAMPER"}, "note": "x"})
    check("A-901 edit after confirm rejected", status == 409, f"HTTP {status}")

    # A-902 — routine + document OCR provenance
    a902 = by_token["A-902"]
    status, case = call(base, "GET", f"/api/cases/{a902}")
    blob = json.dumps(case)
    check("A-902 routine (not escalated)", "urgent" not in blob.lower() or "not urgent" in blob.lower())
    check("A-902 document_extracted provenance", "document_extracted" in blob)
    check("A-902 abnormal glucose flagged", "145" in blob and "HIGH" in blob.upper())
    status, _ = call(base, "POST", f"/api/cases/{a902}/confirm")
    check("A-902 confirm accepted", status == 200)
    status, body = call(base, "POST", f"/api/fhir/export/{a902}")
    check("A-902 FHIR export", status == 200 and body.get("status") == "succeeded")

    # A-903 — AYUSH Dashavidha
    a903 = by_token["A-903"]
    status, case = call(base, "GET", f"/api/cases/{a903}")
    ayush = (case.get("canonical") or {}).get("ayush") or {}
    check("A-903 case.ayush block present", bool(ayush), f"{len(ayush)} keys")
    ayush_blob = json.dumps(ayush).lower()
    check("A-903 Dashavidha answers captured", "nidra" in ayush_blob and "ahara" in ayush_blob)
    status, _ = call(base, "POST", f"/api/cases/{a903}/confirm")
    check("A-903 confirm accepted", status == 200)
    status, body = call(base, "POST", f"/api/fhir/export/{a903}")
    check("A-903 FHIR export", status == 200 and body.get("status") == "succeeded")

    print()
    if failures:
        print(f"SMOKE TEST FAILED — {len(failures)} failure(s): {failures}")
        return 1
    print("SMOKE TEST PASSED — all three demo journeys verified through the API.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
