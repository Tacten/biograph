"""
M1-T18 / M1-T21 / M1-T49: HIP Share-Profile Callback
======================================================
ABDM Gateway calls this endpoint when a patient scans the HIP's
session QR code with their ABHA app and consents to share their
profile (SOP §6 Scan & Share).

Security controls applied:
  T19 — IP allowlist (via ssrf_guard.assert_abdm_gateway_ip)
  T20 — FHIR reference URL SSRF (via ssrf_guard.sanitise_fhir_references)
  T21 — Callback signature / replay prevention
  T49 — Demographic spoofing prevention

Endpoint: POST /api/method/healthcare.regional.india.abdm.api.hip.receive_share_profile
Auth:      allow_guest=True  (ABDM Gateway calls this without Frappe session)
Returns:   202 Accepted on success; 4xx on security rejection
"""

import hashlib
import hmac
from datetime import datetime, timezone

import frappe
from healthcare.regional.india.abdm.utils.log_utils import abdm_log
from healthcare.regional.india.abdm.utils.ssrf_guard import assert_abdm_gateway_ip, sanitise_fhir_references
from healthcare.regional.india.abdm.utils.audit import audit_log, audit_log_failure
from healthcare.regional.india.abdm.utils.fhir_validator import validate_fhir_payload


# ---------------------------------------------------------------------------
# Public endpoint — T18
# ---------------------------------------------------------------------------

@frappe.whitelist(allow_guest=True)
def receive_share_profile() -> dict:
    """
    ABDM → HIP Scan & Share callback (SOP §6).

    Expected JSON body:
    {
      "requestId":  "<uuid>",
      "timestamp":  "<ISO-8601>",
      "intent":     "PROFILE_SHARE",   # optional field
      "profile": {
        "shareCode": "<4-digit PIN>",
        "hipCode":   "<HIP ID>",        # optional
        "patient": {
          "abhaNumber":   "91-XXXX-XXXX-XXXX",
          "abhaAddress":  "xxx@abdm",
          "name":         "...",
          "gender":       "M|F|O",
          "yearOfBirth":  1990,
          "monthOfBirth": "6",
          "dayOfBirth":   "15",
          "address":      {...},
          "identifiers":  [...]
        }
      }
    }

    Returns {"status": "accepted"} with HTTP 200 (Frappe maps to 200 by default).
    ABDM gateway expects 202 — Frappe does not expose status codes at the
    whitelist level so we return a clear JSON body; gateway retries on 5xx only.
    """
    # ── 1. IP allowlist check (T19) ────────────────────────────────────────
    client_ip = (
        frappe.request.headers.get("X-Forwarded-For")
        or frappe.request.environ.get("REMOTE_ADDR")
    )
    assert_abdm_gateway_ip(client_ip)

    # ── 2. Parse and hardened-validate body (T36: size/XXE/script/depth) ──
    body_raw = frappe.request.data or b""
    try:
        body = validate_fhir_payload(body_raw)
    except frappe.ValidationError:
        abdm_log("error", "share_profile: payload rejected by FHIR parser hardening")
        raise

    request_id = _require_str(body, "requestId")
    timestamp  = _require_str(body, "timestamp")
    profile    = body.get("profile") or {}
    if not isinstance(profile, dict):
        frappe.throw(frappe._("Missing profile in callback"), frappe.ValidationError)

    # ── 3. Replay / timestamp check (T21 anti-replay) ─────────────────────
    _assert_timestamp_fresh(timestamp, request_id)

    # ── 4. Callback signature validation (T21) ────────────────────────────
    signature_header = frappe.request.headers.get("X-HIP-Signature") or ""
    _validate_signature(body_raw, signature_header)

    # ── 5. FHIR reference URL SSRF check (T20) ────────────────────────────
    sanitise_fhir_references(body)

    # ── 6. Extract patient profile ────────────────────────────────────────
    share_code   = _require_str(profile, "shareCode")
    patient_data = profile.get("patient") or {}
    if not isinstance(patient_data, dict):
        frappe.throw(frappe._("Missing patient data in profile"), frappe.ValidationError)

    abha_number  = (patient_data.get("abhaNumber") or "").replace("-", "")
    abha_address = patient_data.get("abhaAddress") or ""
    received_name   = patient_data.get("name") or ""
    received_gender = (patient_data.get("gender") or "").upper()
    year_of_birth   = patient_data.get("yearOfBirth")

    if not abha_number:
        frappe.throw(frappe._("ABHA number missing in share_profile callback"), frappe.ValidationError)

    # ── 7. Match patient + demographic spoofing check (T49) ───────────────
    patient_name = _match_and_validate_patient(
        abha_number, received_name, received_gender, year_of_birth
    )

    # ── 8. Store linking token (T22) ──────────────────────────────────────
    from healthcare.healthcare.doctype.abdm_token_registry.abdm_token_registry import store_linking_token
    store_linking_token(patient_name, share_code, expiry_minutes=60)

    # ── 9. Update ABHA Record with latest demographic snapshot ────────────
    _sync_abha_record(patient_name, patient_data, abha_number, abha_address)

    # ── 10. Trigger FHIR Patient Cache refresh ────────────────────────────
    try:
        from healthcare.regional.india.abdm.patient_builder import build_patient_fhir
        build_patient_fhir(patient_name)
    except Exception as exc:
        abdm_log("warning", f"FHIR cache refresh failed after share_profile ({type(exc).__name__})")

    abdm_log("info", f"share_profile accepted | patient={patient_name} | requestId={request_id}")
    audit_log("SCAN_SHARE", patient=patient_name, result="SUCCESS")
    return {"status": "accepted", "requestId": request_id}


# ---------------------------------------------------------------------------
# T21 — Timestamp freshness / anti-replay
# ---------------------------------------------------------------------------

def _assert_timestamp_fresh(timestamp: str, request_id: str, max_age_minutes: int = 5) -> None:
    """
    Reject callbacks whose timestamp is > max_age_minutes in the past or future.
    This prevents replay attacks where a captured callback is re-sent later.
    """
    try:
        ts = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        delta = abs((now - ts).total_seconds())
        if delta > max_age_minutes * 60:
            abdm_log("error", f"share_profile replay rejected: timestamp drift {int(delta)}s")
            frappe.throw(
                frappe._("Callback timestamp too old or too far in the future — possible replay attack"),
                frappe.PermissionError,
            )
    except (ValueError, TypeError):
        abdm_log("warning", "share_profile: unparseable timestamp — allowing")


# ---------------------------------------------------------------------------
# T21 — HMAC signature validation
# ---------------------------------------------------------------------------

def _validate_signature(body: bytes, signature_header: str) -> None:
    """
    M1-T21: Validate the X-HIP-Signature header using HMAC-SHA256 over the
    raw request body and the callback_secret configured in ABDM Settings.

    If no callback_secret is configured (sandbox / dev), log a warning and
    allow the request.  Never hard-fail due to missing secret configuration
    so sandbox testing is not broken.

    Signature header format (ABDM convention):
        X-HIP-Signature: sha256=<hex_digest>
    """
    try:
        settings = frappe.get_single("ABDM Settings")
        secret = getattr(settings, "callback_secret", None)
        if secret:
            secret = settings.get_password("callback_secret", raise_exception=False)

        if not secret:
            if signature_header:
                abdm_log("warning", "share_profile: callback_secret not set — skipping sig check")
            return

        if not signature_header:
            abdm_log("error", "share_profile: X-HIP-Signature missing but callback_secret configured")
            frappe.throw(
                frappe._("Missing callback signature"),
                frappe.PermissionError,
            )

        # Strip "sha256=" prefix if present
        expected_prefix = "sha256="
        sig_value = (
            signature_header[len(expected_prefix):]
            if signature_header.startswith(expected_prefix)
            else signature_header
        )

        computed = hmac.new(
            secret.encode("utf-8"),
            body,
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(computed, sig_value.lower()):
            abdm_log("error", "share_profile: HMAC signature mismatch")
            frappe.throw(
                frappe._("Invalid callback signature"),
                frappe.PermissionError,
            )
    except (frappe.PermissionError, frappe.ValidationError):
        raise
    except Exception as exc:
        abdm_log("warning", f"Signature validation error ({type(exc).__name__}) — allowing")


# ---------------------------------------------------------------------------
# T49 — Demographic spoofing prevention
# ---------------------------------------------------------------------------

def _match_and_validate_patient(
    abha_number: str,
    received_name: str,
    received_gender: str,
    received_yob: int | None,
) -> str:
    """
    M1-T49: Find the Patient record linked to abha_number.
    If found, compare incoming demographics against stored data.
    Reject if gender or year-of-birth mismatches to prevent spoofing.

    Returns the Frappe Patient docname.
    Raises ValidationError if no match or demographic mismatch detected.
    """
    # Look up ABHA Record by abha_number
    rec_name = frappe.db.get_value("ABHA Record", {"abha_number": abha_number}, "name")
    if not rec_name:
        # ABHA number not on file — accept callback and create a stub ABHA record
        # (staff will confirm manually)
        abdm_log("warning", f"share_profile: ABHA not on file — auto-linking deferred")
        frappe.throw(
            frappe._("No Patient found for this ABHA number. Please create the Patient first."),
            frappe.DoesNotExistError,
        )

    patient_name = frappe.db.get_value("ABHA Record", rec_name, "patient")
    if not patient_name:
        frappe.throw(frappe._("ABHA Record has no linked Patient"), frappe.ValidationError)

    # Fetch stored demographics from Patient record
    patient = frappe.get_doc("Patient", patient_name)

    # Gender check
    if received_gender and patient.sex:
        stored_gender = patient.sex[0].upper()  # M / F / O
        if received_gender[0] != stored_gender:
            abdm_log(
                "error",
                f"share_profile DEMOGRAPHIC MISMATCH: gender | patient={patient_name}",
            )
            frappe.throw(
                frappe._("Demographic mismatch in share_profile callback — gender"),
                frappe.PermissionError,
            )

    # Year-of-birth check (allow ±1 year tolerance for edge cases)
    if received_yob and patient.dob:
        stored_yob = int(str(patient.dob)[:4])
        if abs(int(received_yob) - stored_yob) > 1:
            abdm_log(
                "error",
                f"share_profile DEMOGRAPHIC MISMATCH: year of birth | patient={patient_name}",
            )
            frappe.throw(
                frappe._("Demographic mismatch in share_profile callback — year of birth"),
                frappe.PermissionError,
            )

    return patient_name


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require_str(data: dict, key: str) -> str:
    value = data.get(key)
    if not value or not str(value).strip():
        frappe.throw(frappe._(f"Missing required field: {key}"), frappe.ValidationError)
    return str(value).strip()


def _sync_abha_record(
    patient: str,
    patient_data: dict,
    abha_number: str,
    abha_address: str,
) -> None:
    """Update ABHA Record with the latest profile snapshot from the callback."""
    rec_name = frappe.db.get_value("ABHA Record", {"patient": patient}, "name")
    if not rec_name:
        return
    update = {}
    if abha_number:
        update["abha_number"] = abha_number
    if abha_address:
        update["abha_address"] = abha_address
        update["preferred_abha_address"] = abha_address
    if update:
        frappe.db.set_value("ABHA Record", rec_name, update)
