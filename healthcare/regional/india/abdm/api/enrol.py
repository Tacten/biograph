"""
M1-T11, T59, T12, T60, T61: ABHA Enrolment API endpoints — SOP §3.

All endpoints are @frappe.whitelist (authenticated only).
Security enforced per-endpoint:
  - Mass assignment: only explicitly listed fields accepted (M1-T7)
  - IDOR: patient permission check inside abha_client (M1-T4B)
  - Rate limiting: per-user per-patient (M1-T13)
  - PII scrubbed from all logs (M1-T6)
  - Tokens stored in ABDM Token Registry, never in response body
"""

import frappe
from healthcare.regional.india.abdm.utils.abha_client import AbhaClient
from healthcare.regional.india.abdm.utils.rate_limit import (
    check_otp_send, check_otp_verify, check_otp_resend,
    check_txn_not_consumed, mark_txn_consumed,
)
from healthcare.regional.india.abdm.utils.log_utils import abdm_log
from healthcare.regional.india.abdm.utils.http_guards import require_post
from healthcare.regional.india.abdm.utils.audit import audit_log


# ---------------------------------------------------------------------------
# Input validation helpers (M1-T7 mass assignment + M1-T52 invalid input)
# ---------------------------------------------------------------------------

def _require(value, name: str):
    if not value or not str(value).strip():
        frappe.throw(frappe._(f"{name} is required"), frappe.ValidationError)
    return str(value).strip()


# Verhoeff checksum tables (M1-T7 input validation)
_VERHOEFF_D = [
    [0,1,2,3,4,5,6,7,8,9],
    [1,2,3,4,0,6,7,8,9,5],
    [2,3,4,0,1,7,8,9,5,6],
    [3,4,0,1,2,8,9,5,6,7],
    [4,0,1,2,3,9,5,6,7,8],
    [5,9,8,7,6,0,4,3,2,1],
    [6,5,9,8,7,1,0,4,3,2],
    [7,6,5,9,8,2,1,0,4,3],
    [8,7,6,5,9,3,2,1,0,4],
    [9,8,7,6,5,4,3,2,1,0],
]
_VERHOEFF_P = [
    [0,1,2,3,4,5,6,7,8,9],
    [1,5,7,6,2,8,3,0,9,4],
    [5,8,0,3,7,9,6,1,4,2],
    [8,9,1,6,0,4,3,5,2,7],
    [9,4,5,3,1,2,6,8,7,0],
    [4,2,8,6,5,7,3,9,0,1],
    [2,7,9,3,8,0,6,4,1,5],
    [7,0,4,6,9,1,3,2,5,8],
]

def _verhoeff_validate(number: str) -> bool:
    """Return True if number passes the Verhoeff checksum."""
    c = 0
    for i, ch in enumerate(reversed(number)):
        c = _VERHOEFF_D[c][_VERHOEFF_P[i % 8][int(ch)]]
    return c == 0


def _validate_aadhaar(aadhaar: str):
    digits = aadhaar.replace(" ", "").replace("-", "")
    if not digits.isdigit() or len(digits) != 12:
        frappe.throw(frappe._("Invalid Aadhaar number format. Must be 12 digits."), frappe.ValidationError)
    if not _verhoeff_validate(digits):
        frappe.throw(frappe._("Invalid Aadhaar number. Please check and re-enter."), frappe.ValidationError)
    return digits


def _validate_otp(otp: str):
    if not otp or not otp.strip().isdigit() or len(otp.strip()) != 6:
        frappe.throw(frappe._("Invalid OTP format. Must be 6 digits."), frappe.ValidationError)
    return otp.strip()


def _validate_patient(patient: str) -> str:
    patient = _require(patient, "Patient")
    if not frappe.db.exists("Patient", patient):
        frappe.throw(frappe._("Patient not found"), frappe.ValidationError)
    return patient


def _assert_no_existing_abha(patient: str) -> None:
    """
    Raise a clear ValidationError if the patient already has an ABHA Record.
    Prevents re-enrolment attempts that ABDM would silently reject with a
    confusing 400 'Invalid Transaction Id' error.
    """
    existing = frappe.db.get_value(
        "ABHA Record",
        {"patient": patient},
        ["abha_number", "preferred_abha_address"],
        as_dict=True,
    )
    if existing:
        abha_id = existing.get("abha_number") or existing.get("preferred_abha_address") or ""
        hint = f" ({abha_id})" if abha_id else ""
        frappe.throw(
            frappe._(
                f"This patient already has an ABHA{hint}. "
                "Use ABDM → Verify ABHA to re-authenticate instead of creating a new one."
            ),
            frappe.ValidationError,
        )


# ---------------------------------------------------------------------------
# Step 1: Generate Aadhaar OTP  (M1-T11)
# ---------------------------------------------------------------------------

@frappe.whitelist()
@require_post
def generate_aadhaar_otp(patient: str, aadhaar: str) -> dict:
    """
    SOP §3 Step 1 — Send OTP to Aadhaar-linked mobile.
    Encrypts Aadhaar before sending. Stores T-token in Token Registry.

    Aadhaar Act compliance: the plaintext Aadhaar is NEVER stored anywhere.
    It is validated, immediately encrypted (RSA) inside AbhaClient, then zeroed.
    Accepted fields: patient, aadhaar (ONLY — all others rejected per M1-T7)
    """
    patient  = _validate_patient(patient)
    aadhaar  = _validate_aadhaar(_require(aadhaar, "Aadhaar"))
    _assert_no_existing_abha(patient)
    check_otp_send(patient)  # M1-T13: rate limit

    client = AbhaClient()
    try:
        result = client.generate_aadhaar_otp(patient, aadhaar)
    finally:
        # Zero the plaintext Aadhaar immediately — Aadhaar Act §29 compliance.
        # Prevents it appearing in Frappe Error Log tracebacks.
        aadhaar = "000000000000"  # noqa: F841

    abdm_log("info", f"Aadhaar OTP sent | patient={patient}")
    return {"message": "OTP sent successfully", "txnId": result.get("txnId")}


# ---------------------------------------------------------------------------
# Step 2: Resend OTP  (M1-T59)
# ---------------------------------------------------------------------------

@frappe.whitelist()
@require_post
def resend_aadhaar_otp(patient: str, txn_id: str) -> dict:
    """
    SOP §3 Step 2 — Resend OTP for existing txnId.
    Max 3 resends per txnId (M1-T13).
    """
    patient = _validate_patient(patient)
    txn_id  = _require(txn_id, "txnId")

    check_otp_resend(txn_id)  # M1-T13

    client = AbhaClient()
    client.resend_aadhaar_otp(patient, txn_id)

    abdm_log("info", f"Aadhaar OTP resent | patient={patient}")
    return {"message": "OTP resent successfully"}


# ---------------------------------------------------------------------------
# Step 3: Enrol ABHA via Aadhaar OTP  (M1-T12)
# ---------------------------------------------------------------------------

@frappe.whitelist()
@require_post
def enrol_by_aadhaar(patient: str, txn_id: str, otp: str, mobile: str = "") -> dict:
    """
    SOP §3 Steps 4-5 — Verify OTP + mobile, create ABHA.
    V3 requires the user's mobile alongside the OTP; ABDM auto-links it if it
    matches the Aadhaar-linked mobile, otherwise triggers a separate mobile OTP.
    Returns mobile_linked=True when auto-linked (frontend skips step A3).
    """
    patient = _validate_patient(patient)
    txn_id  = _require(txn_id, "txnId")
    otp     = _validate_otp(_require(otp, "OTP"))
    mobile  = str(mobile or "").strip()
    if mobile and (not mobile.isdigit() or len(mobile) != 10):
        frappe.throw(frappe._("Mobile number must be 10 digits."), frappe.ValidationError)

    check_txn_not_consumed(txn_id)  # M1-T50: reject replay of an already-completed enrolment
    check_otp_verify(txn_id)  # M1-T13

    client = AbhaClient()
    response = client.enrol_abha_by_aadhaar(patient, txn_id, otp, mobile=mobile)

    # Create ABHA Record from response (server-set only)
    abha_record = _create_abha_record_from_enrolment(patient, response)
    mark_txn_consumed(txn_id)  # M1-T50

    # SOP §3 Step 6: ABDM auto-links mobile when it matches Aadhaar-linked mobile.
    # Detect via mobileLinked flag or ACTIVE status in response.
    _resp_profile = response.get("ABHAProfile") or response
    mobile_linked = bool(
        _resp_profile.get("mobileLinked") or _resp_profile.get("mobile_linked")
        or response.get("mobileLinked") or response.get("mobile_linked")
        or abha_record.status == "ACTIVE"
    )

    abdm_log("info", f"ABHA enrolled | patient={patient} | mobile_linked={mobile_linked}")
    audit_log("ABHA_CREATE", patient=patient, result="SUCCESS")
    return {
        "message": "ABHA created successfully",
        "abha_number": abha_record.abha_number,
        "abha_address": abha_record.abha_address,
        "status": abha_record.status,
        "mobile_linked": mobile_linked,
    }


def _create_abha_record_from_enrolment(patient: str, enrol_response: dict) -> "frappe.Document":
    """
    Parse ABHA V3 enrolment response and create/update the ABHA Record.
    All fields set server-side — nothing from client input.
    FHIR Identifier system URIs set per FHIR Identifier Systems sheet.
    """
    from frappe.utils import now_datetime

    # V3 nests the profile under ABHAProfile; fall back to root for DL / legacy shapes.
    _profile = enrol_response.get("ABHAProfile") or enrol_response
    abha_number = (
        _profile.get("ABHANumber") or _profile.get("abhaNumber") or _profile.get("enrolmentNumber")
        or enrol_response.get("ABHANumber") or enrol_response.get("abhaNumber") or ""
    )
    phr = (
        _profile.get("preferredAbhaAddress") or _profile.get("phrAddress") or _profile.get("abhaAddress")
        or enrol_response.get("preferredAbhaAddress") or enrol_response.get("abhaAddress") or ""
    )
    abha_address = phr[0] if isinstance(phr, list) else str(phr or "")

    if not abha_number:
        import json as _json
        _profile_keys = list(_profile.keys()) if isinstance(_profile, dict) else []
        frappe.log_error(
            title="ABDM enrol/byAadhaar — missing ABHANumber",
            message=f"Root keys: {list(enrol_response.keys())}\nProfile keys: {_profile_keys}",
        )
        frappe.throw(frappe._("ABHA enrolment response missing ABHA number"), frappe.ValidationError)

    # Upsert ABHA Record
    existing = frappe.db.get_value("ABHA Record", {"patient": patient}, "name")
    if existing:
        rec = frappe.get_doc("ABHA Record", existing)
    else:
        rec = frappe.new_doc("ABHA Record")
        rec.patient = patient
        rec.abha_type = "STANDARD"
        rec.created_at = now_datetime()

    rec.abha_number  = abha_number
    rec.abha_address = abha_address
    rec.status       = "UNVERIFIED"  # becomes ACTIVE after mobile OTP (Step 4)
    rec.save(ignore_permissions=False)

    # Trigger FHIR Patient Cache sync
    _sync_fhir_cache(patient)

    # Mirror onto Patient's own custom fields for backward compatibility with
    # the pre-existing native module's UI/reports — ABHA Record stays the
    # source of truth, this is a denormalised convenience copy only.
    _sync_abha_fields_to_patient(patient, abha_number, abha_address)

    return rec


def _sync_abha_fields_to_patient(patient: str, abha_number: str, abha_address: str) -> None:
    """Mirror abha_number/abha_address onto Patient-abha_number / Patient-abha_address
    (custom fields created by regional/india/abdm/setup.py). Non-fatal if they
    don't exist (e.g. company country isn't India)."""
    if not abha_number:
        return
    try:
        frappe.db.set_value("Patient", patient, {
            "abha_number": abha_number,
            "abha_address": abha_address or "",
        })
    except Exception:
        pass


def _sync_fhir_cache(patient: str):
    try:
        from healthcare.regional.india.abdm.patient_builder import build_patient_fhir
        build_patient_fhir(patient)
    except Exception as e:
        # Non-fatal — log and continue
        frappe.log_error(f"FHIR cache sync failed for patient={patient}: {type(e).__name__}", "ABDM FHIR")


# ---------------------------------------------------------------------------
# Step 4: Mobile verification after enrolment  (M1-T60)
# ---------------------------------------------------------------------------

@frappe.whitelist()
@require_post
def send_mobile_otp(patient: str, txn_id: str, mobile: str = "") -> dict:
    """SOP §3 Step 6 — Send mobile OTP when entered mobile differs from Aadhaar-linked mobile.
    Mobile is passed from the frontend (collected in step A2 alongside the OTP).
    Falls back to Patient record mobile if not supplied.
    """
    patient = _validate_patient(patient)
    txn_id  = _require(txn_id, "txnId")

    mobile = str(mobile or "").strip()
    if not mobile:
        mobile = str(frappe.db.get_value("Patient", patient, "mobile") or "").strip()

    client = AbhaClient()
    client.send_mobile_otp_post_enrol(patient, txn_id, mobile=mobile)

    abdm_log("info", f"Mobile OTP sent post-enrol | patient={patient}")
    return {"message": "Mobile OTP sent"}


@frappe.whitelist()
@require_post
def verify_mobile_otp(patient: str, txn_id: str, otp: str) -> dict:
    """
    SOP §3 Step 4 — Verify mobile OTP.
    Stores X-token in Token Registry. Sets ABHA Record status to ACTIVE.
    """
    patient = _validate_patient(patient)
    txn_id  = _require(txn_id, "txnId")
    otp     = _validate_otp(_require(otp, "OTP"))

    check_txn_not_consumed(txn_id)  # M1-T50: reject replay of an already-completed activation
    check_otp_verify(txn_id)  # M1-T13

    client = AbhaClient()
    client.verify_mobile_otp_post_enrol(patient, txn_id, otp)

    # Activate the ABHA Record
    rec_name = frappe.db.get_value("ABHA Record", {"patient": patient}, "name")
    if rec_name:
        from frappe.utils import now_datetime
        frappe.db.set_value("ABHA Record", rec_name, {
            "status": "ACTIVE",
            "verified_at": now_datetime(),
        })
    mark_txn_consumed(txn_id)  # M1-T50

    _sync_fhir_cache(patient)
    abdm_log("info", f"Mobile OTP verified | patient={patient} | ABHA ACTIVE")
    audit_log("ABHA_ACTIVATE", patient=patient, result="SUCCESS")
    return {"message": "Mobile verified. ABHA is now active."}


# ---------------------------------------------------------------------------
# Step 5: Email verification — optional, skippable
# ---------------------------------------------------------------------------

@frappe.whitelist()
@require_post
def skip_email_verification(patient: str, txn_id: str) -> dict:
    """SOP §3 Step 5 — Client clicked Skip. Nothing to do server-side."""
    _validate_patient(patient)
    abdm_log("info", f"Email verification skipped | patient={patient}")
    return {"message": "Email step skipped"}


# ---------------------------------------------------------------------------
# Step 6: ABHA Address suggestions + selection  (M1-T61)
# ---------------------------------------------------------------------------

@frappe.whitelist()
@require_post
def get_abha_suggestions(patient: str) -> dict:
    """SOP §3 Step 6a — Get suggested ABHA addresses."""
    patient = _validate_patient(patient)

    client = AbhaClient()
    suggestions = client.get_abha_address_suggestions(patient)

    return {"suggestions": suggestions}


@frappe.whitelist()
@require_post
def set_abha_address(patient: str, abha_address: str) -> dict:
    """
    SOP §3 Step 6b — Finalise ABHA address (CRITICAL).
    Updates preferred_abha_address in ABHA Record.
    """
    patient      = _validate_patient(patient)
    abha_address = _require(abha_address, "ABHA Address")

    # Validate format — must end with @abdm (prod) or @sbx (sandbox)
    if not (abha_address.endswith("@abdm") or abha_address.endswith("@sbx")):
        frappe.throw(frappe._("Invalid ABHA address format (must end with @abdm or @sbx)"), frappe.ValidationError)

    client = AbhaClient()
    client.set_abha_address(patient, abha_address)

    # Update preferred_abha_address in ABHA Record
    rec_name = frappe.db.get_value("ABHA Record", {"patient": patient}, "name")
    if rec_name:
        frappe.db.set_value("ABHA Record", rec_name, "preferred_abha_address", abha_address)

    _sync_fhir_cache(patient)
    abdm_log("info", f"ABHA address set | patient={patient}")
    return {"message": "ABHA address confirmed", "abha_address": abha_address}


# ---------------------------------------------------------------------------
# Mobile OTP ABHA creation (M1-T16)
# ---------------------------------------------------------------------------

def _validate_mobile(mobile: str) -> str:
    mobile = _require(mobile, "Mobile")
    if not mobile.isdigit() or len(mobile) != 10:
        frappe.throw(frappe._("Invalid mobile number. Must be 10 digits."), frappe.ValidationError)
    return mobile


@frappe.whitelist()
@require_post
def generate_mobile_otp(patient: str, mobile: str) -> dict:
    """M1-T16: SOP §3 Mobile flow — Generate OTP via mobile number."""
    patient = _validate_patient(patient)
    mobile  = _validate_mobile(mobile)
    _assert_no_existing_abha(patient)
    check_otp_send(patient)
    client = AbhaClient()
    result = client.generate_mobile_otp(patient, mobile)
    abdm_log("info", f"Mobile OTP sent | patient={patient}")
    return {"message": "OTP sent", "txnId": result.get("txnId")}


@frappe.whitelist()
@require_post
def verify_mobile_otp_enrol(patient: str, txn_id: str, otp: str) -> dict:
    """M1-T16: Verify mobile OTP and chain into address selection."""
    patient = _validate_patient(patient)
    txn_id  = _require(txn_id, "txnId")
    otp     = _validate_otp(_require(otp, "OTP"))
    check_txn_not_consumed(txn_id)  # M1-T50
    check_otp_verify(txn_id)
    client = AbhaClient()
    result = client.verify_mobile_otp_enrol(patient, txn_id, otp)
    mark_txn_consumed(txn_id)  # M1-T50
    abdm_log("info", f"Mobile OTP verified (enrol) | patient={patient}")
    audit_log("ABHA_MOBILE_VERIFIED", patient=patient, result="SUCCESS")
    return {"message": "OTP verified", "txnId": result.get("txnId", txn_id)}


# ---------------------------------------------------------------------------
# DL ABHA creation (M1-T62 / M1-T63)
# ---------------------------------------------------------------------------

@frappe.whitelist()
@require_post
def generate_dl_otp(patient: str, mobile: str) -> dict:
    """M1-T62: SOP §4 Step 1 — Send mobile OTP for DL flow."""
    patient = _validate_patient(patient)
    mobile  = _validate_mobile(mobile)
    _assert_no_existing_abha(patient)
    check_otp_send(patient)
    client = AbhaClient()
    result = client.generate_dl_otp(patient, mobile)
    abdm_log("info", f"DL OTP sent | patient={patient}")
    return {"message": "OTP sent", "txnId": result.get("txnId")}


@frappe.whitelist()
@require_post
def verify_dl_otp(patient: str, txn_id: str, otp: str) -> dict:
    """M1-T62: SOP §4 Step 2 — Verify mobile OTP for DL flow."""
    patient = _validate_patient(patient)
    txn_id  = _require(txn_id, "txnId")
    otp     = _validate_otp(_require(otp, "OTP"))
    check_otp_verify(txn_id)
    client = AbhaClient()
    result = client.verify_dl_otp(patient, txn_id, otp)
    abdm_log("info", f"DL OTP verified | patient={patient}")
    return {"message": "OTP verified", "txnId": result.get("txnId", txn_id)}


@frappe.whitelist()
@require_post
def enrol_by_dl(patient: str, txn_id: str, dl_data: str) -> dict:
    """
    M1-T63: SOP §4 Step 3 — Submit DL document for ABHA creation.
    dl_data: JSON string with documentId, name fields, dob, gender,
             frontSidePhoto, backSidePhoto (base64), address fields.
    """
    import json
    patient = _validate_patient(patient)
    txn_id  = _require(txn_id, "txnId")
    check_txn_not_consumed(txn_id)  # M1-T50: reject replay of an already-completed DL enrolment

    # Parse and whitelist fields — mass assignment protection (M1-T7)
    try:
        raw = json.loads(dl_data) if isinstance(dl_data, str) else dl_data
    except (ValueError, TypeError):
        frappe.throw(frappe._("Invalid DL data format"), frappe.ValidationError)

    allowed = {
        "documentId", "firstName", "middleName", "lastName",
        "dob", "gender", "frontSidePhoto", "backSidePhoto",
        "address", "state", "district", "pinCode",
    }
    safe_dl = {k: v for k, v in raw.items() if k in allowed}

    if not safe_dl.get("documentId"):
        frappe.throw(frappe._("DL number is required"), frappe.ValidationError)
    if not safe_dl.get("dob"):
        frappe.throw(frappe._("Date of birth is required"), frappe.ValidationError)

    client = AbhaClient()
    response = client.enrol_by_dl(patient, txn_id, safe_dl)

    # Create ABHA Record from DL enrolment response
    enrol_profile = response.get("EnrolProfile", {})
    abha_number = enrol_profile.get("enrolmentNumber", "").replace("-", "")
    phr_list = enrol_profile.get("phrAddress", [])
    abha_address = phr_list[0] if phr_list else ""

    if abha_number:
        _create_abha_record_from_enrolment(patient, {
            "ABHANumber": abha_number,
            "preferredAbhaAddress": abha_address,
        })
    mark_txn_consumed(txn_id)  # M1-T50

    _sync_fhir_cache(patient)
    abdm_log("info", f"DL ABHA enrolment complete | patient={patient}")
    audit_log("ABHA_CREATE", patient=patient, result="SUCCESS")
    return {
        "message": "ABHA created via Driving Licence",
        "abha_number": abha_number,
        "abha_address": abha_address,
        "status": enrol_profile.get("abhaStatus", "ACTIVE"),
    }
