"""
M1-T39: ABDM Audit Trail helpers.

Usage:
    from healthcare.regional.india.abdm.utils.audit import audit_log

    audit_log("ABHA_CREATE", patient="PAT-001", result="SUCCESS")
    audit_log("ABHA_OTP_REQUEST", patient="PAT-001", result="FAILURE", error_code="429")

Security constraints:
  - patient stored as SHA-256 hash only — no raw name, no PII
  - operation must be one of the 28 allowed values (enforced by DocType Select field)
  - ip_address taken from current request, never from caller
  - all inserts are fire-and-forget with ignore_permissions=True so audit
    survives even when called from low-privilege context; the DocType
    permissions prevent reading except by System Manager
"""

import hashlib

import frappe
from healthcare.regional.india.abdm.utils.log_utils import abdm_log


# The 28 valid operation codes (must match abdm_audit_log.json Select options)
_VALID_OPERATIONS = frozenset({
    "ABHA_CREATE", "ABHA_VERIFY", "ABHA_LINK", "ABHA_DEACTIVATE",
    "ABHA_DELETE", "ABHA_REACTIVATE", "QR_GENERATE", "CARD_GENERATE",
    "PROFILE_GET", "PROFILE_UPDATE", "TOKEN_REFRESH", "CONSENT_INIT", "CONSENT_GRANT",
    "CONSENT_REVOKE", "DATA_FETCH", "DATA_PUSH", "LINKING_INIT",
    "LINKING_CONFIRM", "SCAN_SHARE", "SESSION_LOGIN", "SESSION_LOGOUT",
    "ADMIN_ACCESS", "FHIR_VALIDATE", "ABHA_ADDRESS_VERIFY", "TOKEN_REVOKE",
    "RSA_ENCRYPT", "ABHA_OTP_REQUEST", "ABHA_OTP_VERIFY", "ABHA_OTP_RESEND",
    # Mobile enrolment sub-events (enrol.py::verify_mobile_otp + verify_mobile_otp_enrol)
    "ABHA_ACTIVATE", "ABHA_MOBILE_VERIFIED",
})


def audit_log(
    operation: str,
    patient: str = "",
    result: str = "SUCCESS",
    error_code: str = "",
) -> None:
    """
    Write one immutable ABDM Audit Log entry.

    Args:
        operation:  One of the 28 ABDM operation codes.
        patient:    Frappe Patient docname — stored as SHA-256 hash, never raw.
        result:     "SUCCESS" or "FAILURE".
        error_code: Optional HTTP status code or ABDM error code (no stack trace).

    The call is deliberately fire-and-forget.  Any exception is caught and
    logged to the Frappe error log rather than bubbling up to the caller —
    audit failures must never break the primary flow.
    """
    try:
        if operation not in _VALID_OPERATIONS:
            abdm_log("warning", f"audit_log: unknown operation '{operation}' — skipping")
            return

        # Guard: skip silently if the table hasn't been migrated yet
        if not frappe.db.table_exists("ABDM Audit Log"):
            abdm_log("warning", f"audit_log: tabABDMAuditLog not found — run bench migrate (op={operation})")
            return

        patient_hash = _hash_patient(patient) if patient else "anonymous"
        ip_address   = _get_client_ip()
        initiated_by = frappe.session.user or "Guest"

        doc = frappe.get_doc({
            "doctype":        "ABDM Audit Log",
            "operation":      operation,
            "patient_id_hash": patient_hash,
            "result":         result if result in ("SUCCESS", "FAILURE") else "FAILURE",
            "initiated_by":   initiated_by,
            "ip_address":     ip_address,
            "error_code":     str(error_code)[:64] if error_code else "",
            "timestamp":      frappe.utils.now_datetime(),
        })
        doc.insert(ignore_permissions=True)
        frappe.db.commit()

    except Exception as exc:
        # Never let audit failure break the primary flow
        import traceback
        frappe.log_error(
            title=f"ABDM audit_log failed | op={operation} err={type(exc).__name__}",
            message=traceback.format_exc(),
        )


def audit_log_failure(
    operation: str,
    patient: str = "",
    error_code: str = "",
) -> None:
    """Convenience wrapper for failure entries."""
    audit_log(operation, patient=patient, result="FAILURE", error_code=error_code)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hash_patient(patient: str) -> str:
    """Return SHA-256 hex of the patient docname. No truncation — full hash."""
    return hashlib.sha256(patient.encode("utf-8")).hexdigest()


def _get_client_ip() -> str:
    """
    Extract client IP from the current request.
    Uses X-Forwarded-For (first hop) or falls back to REMOTE_ADDR.
    Returns empty string if no request context (e.g. scheduled tasks).
    """
    try:
        xff = frappe.request.headers.get("X-Forwarded-For") or ""
        if xff:
            return xff.split(",")[0].strip()[:45]  # max IPv6 length
        return (frappe.request.environ.get("REMOTE_ADDR") or "")[:45]
    except Exception:
        return ""
