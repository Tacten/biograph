"""
S4 / S5 / S5B / S5C: ABHA Profile, QR, Card, Manual Verification, Lifecycle endpoints.

Whitelisted endpoints:
  get_token_status         — patient_abha.js token badge (referenced at startup)
  get_abha_profile         — S5B: fetch ABHA profile from API
  get_abha_qr_code         — S4: fetch QR code image (base64) for display
  download_abha_card       — S5B: get ABHA card as base64 PNG
  request_verify_otp       — S5: send OTP to verify/link ABHA address
  verify_abha_otp          — S5: verify OTP, store X-token, update ABHA Record
  request_lifecycle_otp    — S5C: send OTP before deactivate/delete/reactivate
  confirm_lifecycle_action — S5C: execute deactivate / delete / reactivate

Security: IDOR via AbhaClient._assert_patient_permission on every call.
          Rate limiting: OTP sends reuse check_otp_send / check_otp_verify.
          No PII in logs.
"""

import frappe
from frappe.utils import get_datetime, now_datetime

from healthcare.regional.india.abdm.utils.abha_client import AbhaClient
from healthcare.regional.india.abdm.utils.rate_limit import (
    check_otp_send, check_otp_verify, check_api_call,
    check_txn_not_consumed, mark_txn_consumed, check_password_attempt,
)
from healthcare.regional.india.abdm.utils.log_utils import abdm_log
from healthcare.regional.india.abdm.utils.audit import audit_log, audit_log_failure
from healthcare.regional.india.abdm.utils.http_guards import require_post
from healthcare.regional.india.abdm.api.enrol import _sync_abha_fields_to_patient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require(value, name: str) -> str:
    if not value or not str(value).strip():
        frappe.throw(frappe._(f"{name} is required"), frappe.ValidationError)
    return str(value).strip()


def _validate_patient(patient: str) -> str:
    patient = _require(patient, "Patient")
    if not frappe.db.exists("Patient", patient):
        frappe.throw(frappe._("Patient not found"), frappe.ValidationError)
    return patient


def _validate_otp(otp: str) -> str:
    otp = _require(otp, "OTP").strip()
    if not otp.isdigit() or len(otp) != 6:
        frappe.throw(frappe._("OTP must be 6 digits"), frappe.ValidationError)
    return otp


# ---------------------------------------------------------------------------
# Token status (called on every Patient form load — must be fast)
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_token_status(patient: str) -> dict:
    """
    Return ABHA token status for the dashboard badge in patient_abha.js.
    Fast path: reads from ABDM Token Registry only (no external API call).
    """
    patient = _validate_patient(patient)

    rec_name = frappe.db.get_value("ABHA Record", {"patient": patient}, "name")
    if not rec_name:
        return {"status": "NONE", "expiry": None}

    reg_name = frappe.db.get_value("ABDM Token Registry", {"patient": patient}, "name")
    if not reg_name:
        return {"status": "NONE", "expiry": None}

    reg = frappe.get_doc("ABDM Token Registry", reg_name)

    if not reg.x_token or not reg.x_token_expiry:
        return {"status": "NONE", "expiry": None}

    expiry = get_datetime(reg.x_token_expiry)
    now = get_datetime(now_datetime())
    remaining = (expiry - now).total_seconds()

    if remaining <= 0:
        status = "EXPIRED"
    elif remaining < 3600:   # < 1 hour → warn
        status = "EXPIRING"
    else:
        status = "ACTIVE"

    return {"status": status, "expiry": str(reg.x_token_expiry)}


# ---------------------------------------------------------------------------
# S4: ABHA QR code
# ---------------------------------------------------------------------------

def _assert_x_token(patient: str) -> None:
    """Raise a clear error if no active X-token is stored for this patient."""
    from healthcare.healthcare.doctype.abdm_token_registry.abdm_token_registry import get_x_token
    from frappe.utils import get_datetime, now_datetime
    x_token = get_x_token(patient)
    if not x_token:
        frappe.throw(
            frappe._("No active ABHA session found. Use <b>ABDM → Verify ABHA</b> first, then try again."),
            frappe.ValidationError,
        )


@frappe.whitelist()
@require_post
def get_abha_qr_code(patient: str) -> dict:
    """
    S4 — Fetch the patient's ABHA QR code from ABHA V3 API.
    Returns base64-encoded PNG string.
    Requires active X-token (patient must have verified ABHA).
    """
    patient = _validate_patient(patient)
    check_api_call("get_abha_qr_code")
    _assert_x_token(patient)
    client = AbhaClient()
    qr_b64 = client.get_abha_qr_code(patient)
    if not qr_b64:
        frappe.throw(frappe._("Could not fetch ABHA QR code. Please verify your ABHA first."), frappe.ValidationError)
    abdm_log("info", f"QR fetched | patient={patient}")
    audit_log("QR_GENERATE", patient=patient, result="SUCCESS")
    return {"qr_code": qr_b64}


# ---------------------------------------------------------------------------
# S5B: Profile & Card
# ---------------------------------------------------------------------------

@frappe.whitelist()
@require_post
def get_abha_profile(patient: str) -> dict:
    """
    S5B — Fetch full ABHA profile from ABHA V3 API.
    Syncs key fields (name, mobile, email) into ABHA Record.
    """
    patient = _validate_patient(patient)
    check_api_call("get_abha_profile")
    _assert_x_token(patient)
    client = AbhaClient()
    profile = client.get_abha_profile(patient)

    # Sync displayable fields into ABHA Record (never log name/mobile/email)
    rec_name = frappe.db.get_value("ABHA Record", {"patient": patient}, "name")
    if rec_name:
        update = {}
        phr = profile.get("preferredAbhaAddress") or profile.get("phrAddress")
        if phr:
            update["preferred_abha_address"] = phr if isinstance(phr, str) else phr[0]
        if update:
            frappe.db.set_value("ABHA Record", rec_name, update)

    abdm_log("info", f"Profile fetched | patient={patient}")
    audit_log("PROFILE_GET", patient=patient, result="SUCCESS")
    return {
        "abha_number": profile.get("abhaNumber", "").replace("-", ""),
        "abha_address": profile.get("preferredAbhaAddress", ""),
        "name": profile.get("name", ""),
        "mobile": profile.get("mobile", "")[-4:] + "XXXXXX" if profile.get("mobile") else "",  # mask mobile
        "email": _mask_email(profile.get("email", "")),
        "gender": profile.get("gender", ""),
        "dob": profile.get("dateOfBirth", ""),
        "status": profile.get("abhaStatus", ""),
    }


def _mask_email(email: str) -> str:
    if not email or "@" not in email:
        return ""
    local, domain = email.split("@", 1)
    masked = local[:2] + "*" * max(0, len(local) - 2)
    return f"{masked}@{domain}"


@frappe.whitelist()
@require_post
def download_abha_card(patient: str) -> dict:
    """
    S5B — Download ABHA card as base64-encoded PNG.
    Returns base64 string that the dialog renders as <img>.
    """
    import base64
    patient = _validate_patient(patient)
    check_api_call("download_abha_card")
    _assert_x_token(patient)
    client = AbhaClient()
    card_bytes = client.get_abha_card(patient)
    if not card_bytes:
        frappe.throw(frappe._("Could not download ABHA Card. Please verify your ABHA first."), frappe.ValidationError)
    abdm_log("info", f"ABHA card downloaded | patient={patient}")
    audit_log("CARD_GENERATE", patient=patient, result="SUCCESS")
    return {"card_b64": base64.b64encode(card_bytes).decode("utf-8")}


# ---------------------------------------------------------------------------
# Profile update (PATCH /v3/profile/account/update)
# ---------------------------------------------------------------------------

@frappe.whitelist()
@require_post
def update_abha_profile(
    patient: str,
    first_name: str = "",
    middle_name: str = "",
    last_name: str = "",
    email: str = "",
) -> dict:
    """
    Update local Patient record with ABHA profile fields.

    NOTE: SOP §7.1/7.2 (Update Mobile/Email via ABDM API) is Post-M1 / M2.
    This endpoint updates the Frappe Patient document locally only.
    ABDM-side sync will be added in M2 once the API endpoint is available.
    """
    import re
    patient = _validate_patient(patient)

    patient_update: dict = {}
    updated: list = []

    fn = first_name.strip()
    mn = middle_name.strip()
    ln = last_name.strip()
    em = email.strip()

    if not fn and not ln and not em:
        frappe.throw(frappe._("Provide at least one field to update"), frappe.ValidationError)

    if em and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", em):
        frappe.throw(frappe._("Enter a valid email address"), frappe.ValidationError)

    # Build full name from parts that were supplied
    if fn or mn or ln:
        full_name = " ".join(p for p in [fn, mn, ln] if p).strip()
        patient_update["patient_name"] = full_name
        patient_update["first_name"]   = fn
        patient_update["middle_name"]  = mn
        patient_update["last_name"]    = ln
        updated += ["name"]

    if em:
        patient_update["email"] = em
        updated += ["email"]

    if patient_update:
        frappe.db.set_value("Patient", patient, patient_update)

    abdm_log("info", f"ABHA profile updated (local) | patient={patient} | fields={updated}")
    audit_log("PROFILE_UPDATE", patient=patient, result="SUCCESS")
    return {"message": "Profile updated successfully", "updated_fields": updated}


# ---------------------------------------------------------------------------
# M1-T92: Login via Password — no OTP required
# ---------------------------------------------------------------------------

_VALID_PASSWORD_LOGIN_HINTS = {"abha-number", "mobile", "email", "aadhaar"}


@frappe.whitelist()
@require_post
def login_with_password(
    patient: str,
    login_id: str,
    password: str,
    login_hint: str = "abha-number",
) -> dict:
    """
    M1-T92: Standalone password login (no OTP) — confirmed real via the
    loginHint/authMethods "password" enum value, but the SOP gives it no
    dedicated worked example. See AbhaClient.login_with_password for the
    best-effort request shape — confirm against the ABHA sandbox before
    production use.
    """
    patient    = _validate_patient(patient)
    login_id   = _require(login_id, "Login ID").strip()
    password   = _require(password, "Password")
    login_hint = (login_hint or "abha-number").lower()

    if login_hint not in _VALID_PASSWORD_LOGIN_HINTS:
        frappe.throw(frappe._("Invalid login_hint"), frappe.ValidationError)
    if login_hint == "abha-number" and (not login_id.isdigit() or len(login_id) != 14):
        frappe.throw(frappe._("ABHA number must be 14 digits"), frappe.ValidationError)
    if login_hint == "mobile" and (not login_id.isdigit() or len(login_id) != 10):
        frappe.throw(frappe._("Mobile number must be 10 digits"), frappe.ValidationError)
    if login_hint == "aadhaar" and (not login_id.isdigit() or len(login_id) != 12):
        frappe.throw(frappe._("Aadhaar number must be 12 digits"), frappe.ValidationError)

    check_password_attempt(patient)  # M1-T92: brute-force throttle (3 / 15 min)

    client = AbhaClient()
    try:
        response = client.login_with_password(patient, login_id, password, login_hint=login_hint)
    finally:
        password = "0" * len(password)  # noqa: F841 — never linger in memory/tracebacks

    accounts = response.get("accounts", [])
    account  = accounts[0] if accounts else {}
    account_profile = _extract_profile_from_account(account)

    _upsert_abha_record(patient, account_profile)
    abdm_log("info", f"ABHA password login verified | patient={patient}")
    audit_log("ABHA_VERIFY", patient=patient, result="SUCCESS")
    return account_profile


# ---------------------------------------------------------------------------
# S5 (new): Verify ABHA — Path 1: mobile / Aadhaar login
# VRFY_ABHA_101 (mobile OTP) / VRFY_ABHA_201 (Aadhaar OTP)
# ---------------------------------------------------------------------------

_VALID_LOGIN_HINTS = {"mobile", "aadhaar", "abha-number"}
_VALID_OTP_SYSTEMS = {"abdm", "aadhaar"}


@frappe.whitelist()
@require_post
def request_abha_login_otp(
    patient: str,
    login_id: str,
    login_hint: str,
) -> dict:
    """
    Path 1 Step 1 — Send OTP using mobile number, Aadhaar number, or ABHA number.
    POST /v3/profile/login/request/otp
    login_hint: "mobile" (10-digit) | "aadhaar" (12-digit) | "abha-number" (14-digit)
    For "abha-number", ABDM sends the OTP to the ABHA-linked mobile (SOP §6.2).
    """
    patient    = _validate_patient(patient)
    login_id   = _require(login_id, "Login ID").strip()
    login_hint = _require(login_hint, "login_hint").lower()

    if login_hint not in _VALID_LOGIN_HINTS:
        frappe.throw(frappe._("login_hint must be 'mobile', 'aadhaar', or 'abha-number'"), frappe.ValidationError)
    if login_hint == "mobile" and (not login_id.isdigit() or len(login_id) != 10):
        frappe.throw(frappe._("Mobile number must be 10 digits"), frappe.ValidationError)
    if login_hint == "aadhaar" and (not login_id.isdigit() or len(login_id) != 12):
        frappe.throw(frappe._("Aadhaar number must be 12 digits"), frappe.ValidationError)
    if login_hint == "abha-number":
        login_id = login_id.replace("-", "")
        if not login_id.isdigit() or len(login_id) != 14:
            frappe.throw(frappe._("ABHA number must be 14 digits"), frappe.ValidationError)

    check_otp_send(patient)

    client = AbhaClient()
    try:
        result = client.request_abha_login_otp(patient, login_id, login_hint)
    finally:
        # Zero login_id (may be Aadhaar) — Aadhaar Act §29 compliance.
        login_id = "0" * len(login_id)  # noqa: F841

    abdm_log("info", f"ABHA login OTP sent | patient={patient} | hint={login_hint}")
    audit_log("ABHA_OTP_REQUEST", patient=patient, result="SUCCESS")
    return {"txnId": result.get("txnId")}


@frappe.whitelist()
@require_post
def verify_abha_login_otp(
    patient: str,
    txn_id: str,
    otp: str,
    login_hint: str = "mobile",
) -> dict:
    """
    Path 1 Step 2 — Verify OTP; return extracted profile for frontend to write to Patient.
    POST /v3/profile/login/verify  (no /verify/user — profile is in accounts[])
    """
    patient    = _validate_patient(patient)
    txn_id     = _require(txn_id, "txnId")
    otp        = _validate_otp(_require(otp, "OTP"))
    login_hint = (login_hint or "mobile").lower()

    check_txn_not_consumed(txn_id)  # M1-T50
    check_otp_verify(txn_id)

    client   = AbhaClient()
    response = client.verify_abha_login_otp(patient, txn_id, otp, login_hint)

    accounts = response.get("accounts", [])
    account  = accounts[0] if accounts else {}
    profile  = _extract_profile_from_account(account)

    _upsert_abha_record(patient, profile)
    mark_txn_consumed(txn_id)  # M1-T50
    abdm_log("info", f"ABHA login verified (Path 1) | patient={patient}")
    audit_log("ABHA_VERIFY", patient=patient, result="SUCCESS")
    return profile


# ---------------------------------------------------------------------------
# S5 (new): Verify ABHA — Path 2: ABHA address / PHR web login
# VRFY_ABHA_102 (mobile OTP via address) / VRFY_ABHA_202 (Aadhaar OTP via address)
# ---------------------------------------------------------------------------


@frappe.whitelist()
@require_post
def request_abha_address_otp(
    patient: str,
    abha_address: str,
    otp_system: str = "abdm",
) -> dict:
    """
    Path 2 Step 1 — Send OTP to ABHA address holder.
    POST /v3/phr/web/login/abha/request/otp
    otp_system: "abdm" (mobile OTP) | "aadhaar" (Aadhaar OTP)
    """
    patient     = _validate_patient(patient)
    abha_address = _require(abha_address, "ABHA Address").strip()
    otp_system   = (otp_system or "abdm").lower()

    if "@" not in abha_address:
        frappe.throw(frappe._("Enter a valid ABHA address (e.g. name@sbx)"), frappe.ValidationError)
    if otp_system not in _VALID_OTP_SYSTEMS:
        frappe.throw(frappe._("otp_system must be 'abdm' or 'aadhaar'"), frappe.ValidationError)

    check_otp_send(patient)

    client = AbhaClient()
    result = client.request_abha_address_otp(patient, abha_address, otp_system)

    abdm_log("info", f"ABHA address OTP sent | patient={patient}")
    return {"txnId": result.get("txnId")}


@frappe.whitelist()
@require_post
def verify_abha_address_otp(
    patient: str,
    txn_id: str,
    otp: str,
    otp_system: str = "abdm",
) -> dict:
    """
    Path 2 Step 2 — Verify OTP; return extracted profile for frontend to write to Patient.
    POST /v3/profile/login/verify  (same endpoint as Path 1 — accounts[] format)
    otp_system must match what was used in request_abha_address_otp ("abdm" or "aadhaar").
    """
    patient    = _validate_patient(patient)
    txn_id     = _require(txn_id, "txnId")
    otp        = _validate_otp(_require(otp, "OTP"))
    otp_system = (otp_system or "abdm").lower()

    check_txn_not_consumed(txn_id)  # M1-T50
    check_otp_verify(txn_id)

    client   = AbhaClient()
    response = client.verify_abha_address_otp(patient, txn_id, otp, otp_system=otp_system)
    mark_txn_consumed(txn_id)  # M1-T50

    # PHR /login/abha/verify returns ABHAProfile nested under ABHAProfile/abhaProfile/profile key
    # or at the root. _extract_profile_from_phr_response handles all variants.
    profile = _extract_profile_from_phr_response(response)
    _upsert_abha_record(patient, profile)
    # X-token is stored by verify_abha_address_otp — fetch full profile from ABDM to sync Patient
    try:
        _sync_abha_profile_to_patient(patient, client)
    except Exception:
        pass  # non-fatal — ABHA Record is already linked
    audit_log("ABHA_ADDRESS_VERIFY", patient=patient, result="SUCCESS")
    abdm_log("info", f"ABHA address verified (Path 2) | patient={patient}")
    return profile


# ---------------------------------------------------------------------------
# Shared helpers for the new verify paths
# ---------------------------------------------------------------------------

def _extract_profile_from_account(account: dict) -> dict:
    """
    Extract a normalised profile dict from accounts[0] in /v3/profile/login/verify response.
    Keys returned match what _on_abha_verified in the frontend expects.
    """
    abha_address = account.get("preferredAbhaAddress") or account.get("ABHAAddress") or ""
    if isinstance(abha_address, list):
        abha_address = abha_address[0] if abha_address else ""
    return {
        "abha_number":  (account.get("ABHANumber") or account.get("abhaNumber") or "").replace("-", ""),
        "abha_address": abha_address,
        "name":         account.get("name") or account.get("fullName") or "",
        "gender":       (account.get("gender") or "").upper(),
        "mobile":       account.get("mobile") or "",
        "dob":          account.get("dateOfBirth") or account.get("dob") or "",
    }


def _extract_profile_from_phr_response(response: dict) -> dict:
    """
    Extract a normalised profile dict from /v3/phr/web/login/abha/verify response.
    Per SOP §12.1 Step 3, the real response nests the profile in a `users` list
    (response["users"][0]) — ABHAProfile/abhaProfile/profile are kept as
    fallbacks for other response variants.
    """
    _users = response.get("users")
    p = (
        (_users[0] if isinstance(_users, list) and _users else None)
        or response.get("ABHAProfile")
        or response.get("abhaProfile")
        or response.get("profile")
        or response
    )
    abha_address = (
        p.get("preferredAbhaAddress")
        or p.get("abhaAddress")
        or p.get("phrAddress")
        or ""
    )
    if isinstance(abha_address, list):
        abha_address = abha_address[0] if abha_address else ""

    dob = p.get("dateOfBirth") or p.get("dob") or ""
    # PHR response sometimes returns {"day":d,"month":m,"year":y}
    if isinstance(dob, dict):
        day   = dob.get("day") or dob.get("date") or "01"
        month = dob.get("month") or "01"
        year  = dob.get("year") or ""
        dob   = f"{year}-{int(month):02d}-{int(day):02d}" if year else ""

    return {
        "abha_number":  (p.get("abhaNumber") or p.get("ABHANumber") or "").replace("-", ""),
        "abha_address": abha_address,
        "name":         p.get("name") or p.get("fullName") or "",
        "gender":       (p.get("gender") or "").upper(),
        "mobile":       p.get("mobile") or "",
        "dob":          dob,
    }


def _upsert_abha_record(patient: str, profile: dict) -> None:
    """Create or update ABHA Record from a verified profile dict."""
    from frappe.utils import now_datetime
    abha_number  = profile.get("abha_number", "")
    abha_address = profile.get("abha_address", "")
    if not abha_number:
        return

    # Guard: this abha_number may already be linked to a DIFFERENT patient
    # (e.g. verification run against the wrong HIMS patient record). Without
    # this check, the insert below fails with a raw MySQL duplicate-key error
    # instead of a clear, actionable message.
    other = frappe.db.get_value("ABHA Record", {"abha_number": abha_number}, ["name", "patient"], as_dict=True)
    if other and other.patient != patient:
        if frappe.db.exists("Patient", other.patient):
            frappe.throw(
                frappe._(
                    "This ABHA number is already linked to a different patient record ({0}). "
                    "Please confirm you are verifying the correct patient."
                ).format(other.patient),
                frappe.ValidationError,
            )
        # The other patient no longer exists (deleted) — this is an orphaned
        # record, not a real conflict. Reclaim it rather than blocking.
        frappe.delete_doc("ABHA Record", other.name, ignore_permissions=True, force=True)
        abdm_log("info", f"Reclaimed orphaned ABHA Record {other.name} (patient {other.patient} no longer exists)")

    existing = frappe.db.get_value("ABHA Record", {"patient": patient}, "name")
    if existing:
        frappe.db.set_value("ABHA Record", existing, {
            "abha_number":           abha_number,
            "abha_address":          abha_address,
            "preferred_abha_address": abha_address,
            "status":                "ACTIVE",
            "verified_at":           now_datetime(),
        })
    else:
        rec = frappe.get_doc({
            "doctype":               "ABHA Record",
            "patient":               patient,
            "abha_number":           abha_number,
            "abha_address":          abha_address,
            "preferred_abha_address": abha_address,
            "abha_type":             "STANDARD",
            "status":                "ACTIVE",
            "created_at":            now_datetime(),
            "verified_at":           now_datetime(),
        })
        rec.insert(ignore_permissions=False)

    _sync_abha_fields_to_patient(patient, abha_number, abha_address)


# ---------------------------------------------------------------------------
# S5: Manual ABHA Verification (legacy — keep for backward compat)
# ---------------------------------------------------------------------------

_VALID_OTP_MODES = {"mobile", "aadhaar"}


@frappe.whitelist()
@require_post
def request_verify_otp(
    patient: str,
    abha_address: str,
    otp_mode: str = "mobile",
) -> dict:
    """
    S5 Step 1 — Send OTP to the ABHA address/number for manual verification.
    Uses SOP §6 login flow: POST /v3/profile/login/request/otp.

    otp_mode: "mobile" (default) or "aadhaar".
    Aadhaar OTP is only valid for 14-digit ABHA number input.
    """
    patient      = _validate_patient(patient)
    abha_address = _require(abha_address, "ABHA Address")
    otp_mode     = (otp_mode or "mobile").lower()

    if otp_mode not in _VALID_OTP_MODES:
        frappe.throw(frappe._("Invalid OTP mode. Use 'mobile' or 'aadhaar'."), frappe.ValidationError)

    # Basic format check
    clean      = abha_address.strip()
    is_number  = clean.isdigit() and len(clean) == 14
    is_address = "@" in clean
    is_mobile  = clean.isdigit() and len(clean) == 10
    if not is_number and not is_address and not is_mobile:
        frappe.throw(
            frappe._("Enter a valid ABHA address (name@abdm) or 14-digit ABHA number."),
            frappe.ValidationError,
        )

    check_otp_send(patient)

    client = AbhaClient()
    result = client.request_login_otp(patient, clean, otp_mode=otp_mode)

    abdm_log("info", f"Verify OTP sent | patient={patient} | mode={otp_mode}")
    return {"message": "OTP sent", "txnId": result.get("txnId")}


@frappe.whitelist()
@require_post
def verify_abha_otp(
    patient: str,
    txn_id: str,
    otp: str,
    otp_mode: str = "mobile",
) -> dict:
    """
    S5 Step 2 — Verify OTP, receive X-token, link/update ABHA Record,
    then fetch full ABHA profile and sync canonical fields into Patient.

    otp_mode must match what was passed to request_verify_otp.
    """
    patient  = _validate_patient(patient)
    txn_id   = _require(txn_id, "txnId")
    otp      = _validate_otp(_require(otp, "OTP"))
    otp_mode = (otp_mode or "mobile").lower()

    if otp_mode not in _VALID_OTP_MODES:
        frappe.throw(frappe._("Invalid OTP mode."), frappe.ValidationError)

    check_txn_not_consumed(txn_id)  # M1-T50
    check_otp_verify(txn_id)

    client = AbhaClient()
    response = client.verify_login_otp(patient, txn_id, otp, otp_mode=otp_mode)
    mark_txn_consumed(txn_id)  # M1-T50

    # SOP §6: login/verify response has accounts[] (not ABHAProfile).
    # X-token is already stored by client.verify_login_otp (via verify/user step).
    accounts = response.get("accounts", [])
    account  = accounts[0] if accounts else {}

    abha_number  = account.get("ABHANumber", "").replace("-", "")
    abha_address = account.get("preferredAbhaAddress", "")
    if isinstance(abha_address, list):
        abha_address = abha_address[0] if abha_address else ""

    if abha_number:
        from frappe.utils import now_datetime
        existing = frappe.db.get_value("ABHA Record", {"patient": patient}, "name")
        if existing:
            frappe.db.set_value("ABHA Record", existing, {
                "abha_number":  abha_number,
                "abha_address": abha_address,
                "preferred_abha_address": abha_address,
                "status":       "ACTIVE",
                "verified_at":  now_datetime(),
            })
        else:
            rec = frappe.get_doc({
                "doctype":     "ABHA Record",
                "patient":     patient,
                "abha_number": abha_number,
                "abha_address": abha_address,
                "preferred_abha_address": abha_address,
                "abha_type":   "STANDARD",
                "status":      "ACTIVE",
                "created_at":  now_datetime(),
                "verified_at": now_datetime(),
            })
            rec.insert(ignore_permissions=False)

        _sync_abha_fields_to_patient(patient, abha_number, abha_address)

    # Fetch full profile from ABHA API (X-token is now live) and sync to Patient.
    # This is the canonical source of truth — Patient fields are overwritten with
    # data from ABDM, never the other way around.
    _sync_abha_profile_to_patient(patient, client)

    # Sync FHIR cache
    try:
        from healthcare.regional.india.abdm.patient_builder import build_patient_fhir
        build_patient_fhir(patient)
    except Exception as e:
        frappe.log_error(f"FHIR sync after verify: {type(e).__name__}", "ABDM FHIR")

    abdm_log("info", f"ABHA verified + linked | patient={patient}")
    return {
        "message": "ABHA verified and linked",
        "abha_number":  abha_number,
        "abha_address": abha_address,
    }


def _sync_abha_profile_to_patient(patient: str, client) -> None:
    """
    Fetch full ABHA profile from ABDM and write canonical fields back to Patient.
    Called after successful OTP verification (X-token is live).

    Mapped fields:
      ABHA name        → Patient.patient_name
      ABHA gender      → Patient.sex  (M→Male, F→Female, O→Other)
      ABHA dateOfBirth → Patient.dob
      ABHA mobile      → Patient.mobile

    Only non-blank values are written. Errors are non-fatal — ABHA Record
    is already linked regardless.
    No PII is logged.
    """
    try:
        profile = client.get_abha_profile(patient)
    except Exception as exc:
        frappe.log_error(f"ABHA profile sync failed: {type(exc).__name__}", "ABDM Profile Sync")
        return

    from frappe.utils import getdate

    update: dict = {}

    # Full name — split into parts so Frappe's auto-computed
    # patient_name = first_name + middle_name + last_name doesn't double up.
    # Setting first_name = full name and last_name = "" via set_value is unsafe
    # because Frappe silently skips empty-string updates, leaving stale last_name
    # in the DB and causing duplication on the next form save.
    abha_name = (profile.get("name") or "").strip()
    if abha_name:
        parts = abha_name.split()
        first  = parts[0] if parts else ""
        last   = parts[-1] if len(parts) > 1 else ""
        middle = " ".join(parts[1:-1]) if len(parts) > 2 else ""
        update["patient_name"] = abha_name
        update["first_name"]   = first
        update["middle_name"]  = middle or None   # None clears the field via set_value
        update["last_name"]    = last  or None

    # Gender: ABHA uses single-letter codes
    _GENDER_MAP = {"M": "Male", "F": "Female", "O": "Other"}
    abha_gender = (profile.get("gender") or "").strip().upper()
    if abha_gender in _GENDER_MAP:
        update["sex"] = _GENDER_MAP[abha_gender]

    # Date of birth — ABHA may return "YYYY-MM-DD" string or
    # {"day": d, "month": m, "year": y} dict
    dob_raw = profile.get("dateOfBirth")
    if dob_raw:
        try:
            if isinstance(dob_raw, str):
                update["dob"] = getdate(dob_raw)
            elif isinstance(dob_raw, dict):
                day   = dob_raw.get("day") or dob_raw.get("date")
                month = dob_raw.get("month")
                year  = dob_raw.get("year")
                if year and month and day:
                    update["dob"] = getdate(f"{year}-{int(month):02d}-{int(day):02d}")
        except Exception:
            pass  # malformed date — skip silently

    # Mobile number (raw from API — not masked at this call site)
    abha_mobile = (profile.get("mobile") or "").strip()
    if abha_mobile:
        update["mobile"] = abha_mobile

    if update:
        frappe.db.set_value("Patient", patient, update)
        abdm_log("info", f"Patient fields synced from ABHA | patient={patient} | fields={list(update.keys())}")


# ---------------------------------------------------------------------------
# S5C: ABHA Lifecycle (deactivate / delete / reactivate)
# ---------------------------------------------------------------------------

_ALLOWED_ACTIONS = {"deactivate", "delete", "reactivate"}


_ALLOWED_OTP_MODES = {"mobile", "aadhaar"}


@frappe.whitelist()
@require_post
def request_lifecycle_otp(
    patient: str,
    action: str,
    otp_mode: str = "mobile",
    aadhaar_number: str = "",
) -> dict:
    """
    S5C Step 1 — Request OTP before deactivate / delete / reactivate.

    action:         deactivate | delete | reactivate
    otp_mode:       mobile (default) | aadhaar
    aadhaar_number: required when otp_mode == "aadhaar" (collected from UI, never logged)

    All three actions use POST /v3/profile/account/request/otp with X-Token.
    """
    patient  = _validate_patient(patient)
    action   = _require(action, "action").lower()
    otp_mode = (otp_mode or "mobile").lower()

    if action not in _ALLOWED_ACTIONS:
        frappe.throw(frappe._("Invalid lifecycle action"), frappe.ValidationError)
    if otp_mode not in _ALLOWED_OTP_MODES:
        frappe.throw(frappe._("Invalid OTP mode"), frappe.ValidationError)

    rec = frappe.db.get_value(
        "ABHA Record", {"patient": patient},
        ["abha_number", "preferred_abha_address"],
        as_dict=True,
    )
    if not rec or not rec.abha_number:
        frappe.throw(frappe._("No ABHA linked to this patient"), frappe.ValidationError)

    abha_number  = rec.abha_number
    abha_address = rec.preferred_abha_address or ""

    # Fetch patient's mobile for mobile-OTP mode (loginHint "mobile" needs 10-digit number)
    mobile_number = ""
    if otp_mode == "mobile":
        mobile_number = (frappe.db.get_value("Patient", patient, "mobile") or "").strip()

    # All lifecycle actions use X-token — ensure session is active
    from healthcare.healthcare.doctype.abdm_token_registry.abdm_token_registry import get_x_token
    if not get_x_token(patient):
        frappe.throw(
            frappe._("Your ABHA session has expired. Please use ABDM → Verify ABHA to refresh your session, then try again."),
            frappe.ValidationError,
        )

    check_otp_send(patient)

    client = AbhaClient()
    result = client.request_account_otp(
        patient,
        action,
        abha_number,
        otp_mode=otp_mode,
        aadhaar_number=aadhaar_number or None,
        abha_address=abha_address or None,
        mobile_number=mobile_number or None,
    )

    abdm_log("info", f"Lifecycle OTP sent | patient={patient} | action={action} | otp_mode={otp_mode}")
    return {"message": "OTP sent", "txnId": result.get("txnId")}


@frappe.whitelist()
@require_post
def confirm_lifecycle_action(patient: str, txn_id: str, otp: str, action: str, otp_mode: str = "mobile") -> dict:
    """S5C Step 2 — Confirm lifecycle action with OTP."""
    patient  = _validate_patient(patient)
    txn_id   = _require(txn_id, "txnId")
    otp      = _validate_otp(_require(otp, "OTP"))
    action   = _require(action, "action").lower()
    otp_mode = (otp_mode or "mobile").lower()

    if action not in _ALLOWED_ACTIONS:
        frappe.throw(frappe._("Invalid lifecycle action"), frappe.ValidationError)
    if otp_mode not in _ALLOWED_OTP_MODES:
        frappe.throw(frappe._("Invalid OTP mode"), frappe.ValidationError)

    check_txn_not_consumed(txn_id)  # M1-T50: reject replay of an already-completed lifecycle action
    check_otp_verify(txn_id)

    client = AbhaClient()
    if action == "deactivate":
        client.deactivate_abha(patient, txn_id, otp)
    elif action == "delete":
        client.delete_abha(patient, txn_id, otp)
    elif action == "reactivate":
        client.reactivate_abha(patient, txn_id, otp, otp_mode=otp_mode)
    mark_txn_consumed(txn_id)  # M1-T50

    # Update ABHA Record status
    status_map = {
        "deactivate": "DEACTIVATED",
        "delete":     "DELETED",
        "reactivate": "ACTIVE",
    }
    rec_name = frappe.db.get_value("ABHA Record", {"patient": patient}, "name")
    if rec_name:
        frappe.db.set_value("ABHA Record", rec_name, "status", status_map[action])

    abdm_log("info", f"Lifecycle action={action} | patient={patient}")
    op_map = {"deactivate": "ABHA_DEACTIVATE", "delete": "ABHA_DELETE", "reactivate": "ABHA_REACTIVATE"}
    audit_log(op_map[action], patient=patient, result="SUCCESS")
    return {"message": f"ABHA {action}d successfully", "status": status_map[action]}
