"""
Backend calls made only by the React ABHA desk (`/abha`).

Everything ABDM-facing stays in enrol.py / profile.py and AbhaClient; this module adds what the page needs around
them, without editing any existing function:

  - get_context:            what is already known about a patient, so no screen asks for it again
  - get_consent_text:       the wording that consent.record_consent stores, so the page shows exactly what is stored
  - request_enrolment_otp:  generate_aadhaar_otp, but only once a valid consent has been recorded

Each call checks the caller's Patient permission.
"""

import hashlib
import re

import frappe
from frappe.utils import add_to_date, get_datetime, now_datetime

from healthcare.regional.india.abdm.utils.http_guards import require_post

# A recorded agreement covers one creation session: it stops being usable after this long.
CONSENT_VALID_MINUTES = 30
CONSENT_TYPE = "ABHA Creation"


def _patient(patient: str, ptype: str = "read") -> str:
    patient = (patient or "").strip()
    if not patient or not frappe.db.exists("Patient", patient):
        frappe.throw(frappe._("Patient not found"), frappe.ValidationError)
    if not frappe.has_permission("Patient", ptype, patient):
        frappe.throw(frappe._("Not permitted"), frappe.PermissionError)
    return patient


def _mask_abha_number(number: str):
    """91-1234-5678-9012 -> 91-XXXX-XXXX-9012 (the desk shows the full number only on the profile)."""
    digits = re.sub(r"\D", "", number or "")
    if len(digits) != 14:
        return None
    return f"{digits[:2]}-XXXX-XXXX-{digits[10:]}"


def _consent_module():
    from healthcare.regional.india.abdm.api import consent

    return consent


@frappe.whitelist()
@require_post
def get_context(patient: str) -> dict:
    """What the desk already knows about this patient. A local read: no ABDM call is made.

    The mobile number itself is not returned (only whether one exists): screens that need it ask for the one to use.
    """
    patient = _patient(patient)
    row = frappe.db.get_value(
        "Patient", patient, ["name", "patient_name", "sex", "dob", "mobile"], as_dict=True
    )
    record = frappe.db.get_value(
        "ABHA Record",
        {"patient": patient},
        ["abha_number", "abha_address", "preferred_abha_address", "status", "verified_at"],
        as_dict=True,
    )
    number = (record and record.abha_number) or None
    return {
        "patient": {
            "name": row.name,
            "patient_name": row.patient_name,
            "sex": row.sex,
            "dob": str(row.dob) if row.dob else None,
            "has_mobile": bool(row.mobile),
        },
        "abha": {
            "linked": bool(number),
            "abha_number": number,
            "abha_number_masked": _mask_abha_number(number),
            "abha_address": (record and (record.preferred_abha_address or record.abha_address)) or None,
            "status": record.status if record else None,
            "verified_at": str(record.verified_at) if record and record.verified_at else None,
        },
    }


@frappe.whitelist()
@require_post
def get_consent_text() -> dict:
    """The wording `consent.record_consent` stores (ABDM's own text), with its version and hash."""
    return _consent_module().get_consent_text()


def _check_consent(patient: str, consent_name: str):
    """Raise unless `consent_name` is a current agreement by this user for this patient to the current wording."""
    if not _consent_module().consent_doctype_ready():
        frappe.throw(
            frappe._("Consent cannot be recorded yet: the ABDM Consent doctype is not on this site. Run bench migrate."),
            frappe.ValidationError,
        )
    refusal = dict(msg=frappe._("Record the patient's agreement to the terms before requesting the OTP."), title=frappe._("Agreement needed"))
    if not consent_name or not isinstance(consent_name, str) or not frappe.db.exists("ABDM Consent", consent_name):
        frappe.throw(**refusal)
    doc = frappe.get_doc("ABDM Consent", consent_name)
    expires = add_to_date(get_datetime(doc.consent_datetime), minutes=CONSENT_VALID_MINUTES)
    if (
        doc.patient != patient
        or doc.captured_by != frappe.session.user
        or doc.consent_type != CONSENT_TYPE
        or doc.consent_status != "Granted"
        or doc.consent_text != _consent_module().CONSENT_TEXT_ABHA_CREATION
        or now_datetime() > expires
    ):
        frappe.throw(**refusal)
    return doc


@frappe.whitelist()
@require_post
def request_enrolment_otp(patient: str, aadhaar: str, consent_name: str) -> dict:
    """enrol.generate_aadhaar_otp, but only once the patient's agreement is on record.

    The Desk wizard keeps using generate_aadhaar_otp directly; the React desk must come through here. After the OTP
    is sent the consent row is linked to the ABDM transaction, as the Desk wizard does.
    """
    patient = _patient(patient, "write")
    _check_consent(patient, consent_name)

    from healthcare.regional.india.abdm.api.enrol import generate_aadhaar_otp

    result = generate_aadhaar_otp(patient, aadhaar)
    txn_id = (result or {}).get("txnId")
    if txn_id:
        frappe.db.set_value(
            "ABDM Consent", consent_name, {"txn_id": txn_id, "auth_method": "Aadhaar OTP"}, update_modified=False
        )
    return result


def _ten_digits(raw) -> str:
    """A mobile as 10 digits (drops spaces, dashes, +91/91), or '' when it is not one."""
    digits = re.sub(r"\D", "", str(raw or ""))
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    return digits if len(digits) == 10 else ""


@frappe.whitelist()
@require_post
def complete_enrolment(patient: str, txn_id: str, otp: str, mobile: str = "") -> dict:
    """enrol.enrol_by_aadhaar, with the mobile taken from the Patient when none is given.

    ABDM links the mobile automatically when it matches the Aadhaar-linked one, which saves a second OTP. Giving it the
    number already on the Patient record means nobody is asked for it twice. When it does not match, the response says
    `mobile_linked: false` and the page runs the mobile-OTP step with the same number.
    """
    patient = _patient(patient, "write")
    chosen = _ten_digits(mobile) or _ten_digits(frappe.db.get_value("Patient", patient, "mobile"))

    from healthcare.regional.india.abdm.api.enrol import enrol_by_aadhaar

    return enrol_by_aadhaar(patient, txn_id, otp, chosen)
