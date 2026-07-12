"""
M1-T34: Debug mode / error hardening for ABDM endpoints.

Strips stack traces, file paths, and internal details from error responses.
Frappe's default 500 handler leaks tracebacks when developer_mode=1 is off
but still includes internal context in some paths. This handler ensures
ABDM-specific errors always return clean, safe JSON.

Wire via hooks.py:
    after_exception = "healthcare.regional.india.abdm.utils.error_handler.handle_abdm_exception"

M1-T52: Input validation edge-case helpers (null, malformed fields).
M1-T53: Timeout + network failure → clean 503.
"""

import frappe
from healthcare.regional.india.abdm.utils.log_utils import abdm_log


# ---------------------------------------------------------------------------
# T34: Clean exception handler (called by hooks.py after_exception)
# ---------------------------------------------------------------------------

def handle_abdm_exception(e):
    """
    Post-exception hook: ensure ABDM API error responses never leak
    stack traces, file paths, or internal state.

    Only fires for requests to healthcare.regional.india.abdm.* endpoints — checks the
    cmd/method path before acting.
    """
    try:
        cmd = (
            frappe.form_dict.get("cmd")
            or frappe.form_dict.get("method")
            or ""
        )
        if "healthcare.regional.india.abdm" not in cmd:
            return  # not our endpoint — let Frappe handle normally

        import requests as _requests

        # Map common exception types to clean status + message
        if isinstance(e, (_requests.Timeout, _requests.ConnectionError)):
            _set_clean_error(503, "ABDM service temporarily unavailable. Please try again in a moment.")
            abdm_log("warning", f"ABDM network error: {type(e).__name__}")
            return

        if isinstance(e, _requests.HTTPError):
            status = getattr(e.response, "status_code", 502) if hasattr(e, "response") else 502
            _set_clean_error(status, f"ABDM API error (HTTP {status}). No sensitive data exposed.")
            abdm_log("warning", f"ABDM HTTPError {status}")
            return

        # For ValidationError / PermissionError — Frappe handles these correctly
        # (clean JSON, no traceback). Only intercept unexpected exceptions.
        if isinstance(e, (frappe.ValidationError, frappe.PermissionError,
                          frappe.DoesNotExistError, frappe.AuthenticationError)):
            return  # Frappe already formats these safely

        # Unexpected exception — replace with generic 500, log internally
        frappe.log_error(title="ABDM Unexpected Error", message=frappe.get_traceback())
        _set_clean_error(500, "An unexpected error occurred. Our team has been notified.")

    except Exception:
        pass  # Never let the error handler itself crash


def _set_clean_error(status_code: int, message: str):
    """Replace Frappe's response with a clean error payload (no traceback)."""
    frappe.response.update({
        "http_status_code": status_code,
        "exc_type":         None,
        "exc":              None,
        "traceback":        None,
        "message":          message,
    })


# ---------------------------------------------------------------------------
# T52: Input validation utilities — reusable across all ABDM endpoints
# ---------------------------------------------------------------------------

def validate_required_str(value, field_name: str, max_length: int = 255) -> str:
    """
    Validate a required string field.
    Raises frappe.ValidationError on null / empty / overlong / injection attempt.
    """
    if value is None:
        frappe.throw(frappe._(f"{field_name} is required"), frappe.ValidationError)
    v = str(value).strip()
    if not v:
        frappe.throw(frappe._(f"{field_name} must not be empty"), frappe.ValidationError)
    if len(v) > max_length:
        frappe.throw(
            frappe._(f"{field_name} is too long (max {max_length} characters)"),
            frappe.ValidationError,
        )
    # Reject null bytes and control characters (T52 special char injection)
    if any(ord(c) < 32 for c in v):
        frappe.throw(
            frappe._(f"{field_name} contains invalid characters"),
            frappe.ValidationError,
        )
    return v


def validate_aadhaar(value) -> str:
    """Validate Aadhaar: exactly 12 digits, no special chars."""
    raw = validate_required_str(value, "Aadhaar", max_length=12)
    digits = raw.replace(" ", "").replace("-", "")
    if not digits.isdigit() or len(digits) != 12:
        frappe.throw(
            frappe._("Invalid Aadhaar format. Must be exactly 12 digits."),
            frappe.ValidationError,
        )
    return digits


def validate_mobile(value) -> str:
    """Validate mobile: exactly 10 digits."""
    raw = validate_required_str(value, "Mobile number", max_length=10)
    digits = raw.replace(" ", "").replace("-", "")
    if not digits.isdigit() or len(digits) != 10:
        frappe.throw(
            frappe._("Invalid mobile number. Must be exactly 10 digits."),
            frappe.ValidationError,
        )
    return digits


def validate_otp(value) -> str:
    """Validate OTP: exactly 6 digits."""
    raw = validate_required_str(value, "OTP", max_length=6)
    if not raw.isdigit() or len(raw) != 6:
        frappe.throw(
            frappe._("Invalid OTP. Must be exactly 6 digits."),
            frappe.ValidationError,
        )
    return raw


def validate_txn_id(value) -> str:
    """Validate txnId: non-empty alphanumeric/hyphen, max 64 chars."""
    raw = validate_required_str(value, "txnId", max_length=64)
    import re
    if not re.match(r'^[a-zA-Z0-9\-_]+$', raw):
        frappe.throw(
            frappe._("Invalid txnId format"),
            frappe.ValidationError,
        )
    return raw


def validate_patient_id(value) -> str:
    """
    Validate patient docname: non-empty, safe characters only.
    Does NOT check existence — caller must do frappe.db.exists() separately.
    """
    raw = validate_required_str(value, "Patient", max_length=140)
    import re
    if not re.match(r'^[a-zA-Z0-9\-_ .]+$', raw):
        frappe.throw(
            frappe._("Invalid patient identifier"),
            frappe.ValidationError,
        )
    return raw


# ---------------------------------------------------------------------------
# T53: Timeout constants (import these in abha_client.py)
# ---------------------------------------------------------------------------

# All outbound HTTP calls must use these timeouts
ABDM_CONNECT_TIMEOUT = 5    # seconds to establish TCP connection
ABDM_READ_TIMEOUT    = 20   # seconds to wait for response bytes
ABDM_TIMEOUT         = (ABDM_CONNECT_TIMEOUT, ABDM_READ_TIMEOUT)

# Wrapper (local service) — shorter since it's on the same host
WRAPPER_CONNECT_TIMEOUT = 3
WRAPPER_READ_TIMEOUT    = 15
WRAPPER_TIMEOUT         = (WRAPPER_CONNECT_TIMEOUT, WRAPPER_READ_TIMEOUT)
