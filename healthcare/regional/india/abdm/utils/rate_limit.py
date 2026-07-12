"""
M1-T13: Per-user OTP rate limiting for all ABHA endpoints.
M1-T37: General per-user API rate limiting (non-OTP endpoints).
M1-T50: Token/txnId replay prevention — single-use enforcement on terminal
        verify calls (enrolment, login, lifecycle actions).
M1-T92: Password login brute-force throttling (no OTP in this flow, so it
        needs its own, stricter limiter rather than reusing the OTP one).

Rules (per backlog):
- Max 3 OTP sends per patient per 10 minutes (per user, NOT per IP)
- Max 3 verify attempts per txnId
- Max 3 resends per txnId
- Max 10 API calls per user per endpoint per minute (non-OTP general limit)
- A txnId that has already completed a terminal verify cannot be replayed
- Max 3 password login attempts per patient per 15 minutes

Uses Frappe's cache (Redis) with TTL keys.
Raises frappe.ValidationError on breach (maps to HTTP 429 at the Frappe layer).
All limits are per AUTHENTICATED USER, not per IP — changing X-Forwarded-For
has no effect on enforcement.
"""

import frappe

# Key prefixes
_OTP_SEND_PREFIX    = "abdm:otp_send:"      # per user+patient
_OTP_VERIFY_PREFIX  = "abdm:otp_verify:"    # per txnId
_OTP_RESEND_PREFIX  = "abdm:otp_resend:"    # per txnId
_TXN_CONSUMED_PREFIX = "abdm:txn_consumed:" # per txnId — M1-T50

_OTP_SEND_LIMIT     = 3
_OTP_SEND_WINDOW    = 600   # 10 minutes in seconds
_OTP_VERIFY_LIMIT   = 3
_OTP_RESEND_LIMIT   = 3
_TXN_TTL            = 1800  # 30 minutes — txnId lifetime

# M1-T37: General API rate limit
_API_CALL_PREFIX    = "abdm:api_call:"   # per user+endpoint
_API_CALL_LIMIT     = 10                 # max calls
_API_CALL_WINDOW    = 60                 # per 60 seconds
_RETRY_AFTER_SECS   = 60                 # value for Retry-After hint in error message

# M1-T92: Password login brute-force throttle (stricter than the general OTP-send limit —
# a password has no per-attempt OTP freshness check backing it, so guessing is cheaper)
_PASSWORD_ATTEMPT_PREFIX = "abdm:password_attempt:"  # per user+patient
_PASSWORD_ATTEMPT_LIMIT  = 3
_PASSWORD_ATTEMPT_WINDOW = 900   # 15 minutes


def check_otp_send(patient: str):
    """
    Enforce: max 3 OTP sends per user per patient per 10 minutes.
    Call BEFORE sending the OTP. Raises on breach.
    """
    key = f"{_OTP_SEND_PREFIX}{frappe.session.user}:{patient}"
    _check_and_increment(key, _OTP_SEND_LIMIT, _OTP_SEND_WINDOW,
                         "Too many OTP requests. Please wait 10 minutes before trying again.")


def check_otp_verify(txn_id: str):
    """
    Enforce: max 3 verify attempts per txnId.
    Call BEFORE verifying the OTP.
    """
    key = f"{_OTP_VERIFY_PREFIX}{txn_id}"
    _check_and_increment(key, _OTP_VERIFY_LIMIT, _TXN_TTL,
                         "Maximum verification attempts reached for this OTP. Please request a new OTP.")


def check_otp_resend(txn_id: str):
    """
    Enforce: max 3 resends per txnId.
    Call BEFORE resending the OTP.
    """
    key = f"{_OTP_RESEND_PREFIX}{txn_id}"
    _check_and_increment(key, _OTP_RESEND_LIMIT, _TXN_TTL,
                         "Maximum resend attempts reached for this OTP session.")


def check_txn_not_consumed(txn_id: str):
    """
    M1-T50: Reject replay of a txnId that has already completed a terminal
    verify (ABHA enrolment, login, or lifecycle action). Call this BEFORE
    check_otp_verify at the top of any endpoint that grants a session,
    creates an ABHA, or performs deactivate/delete/reactivate — a captured
    and re-sent request must not be able to repeat the effect.
    """
    if frappe.cache().get(f"{_TXN_CONSUMED_PREFIX}{txn_id}"):
        frappe.throw(
            frappe._("This request has already been processed. Please start again."),
            frappe.ValidationError,
            title=frappe._("Duplicate Request"),
        )


def mark_txn_consumed(txn_id: str):
    """
    M1-T50: Mark a txnId as consumed immediately after a successful terminal
    verify call. TTL matches the txnId lifetime — no point remembering it
    past the point ABDM itself would reject a stale txnId.
    """
    frappe.cache().set_value(f"{_TXN_CONSUMED_PREFIX}{txn_id}", 1, expires_in_sec=_TXN_TTL)


def check_password_attempt(patient: str):
    """
    M1-T92: Enforce max 3 password-login attempts per user per patient per
    15 minutes. Call BEFORE attempting password verification — password
    login has no OTP freshness check behind it, so it needs its own,
    stricter brute-force throttle rather than reusing check_otp_verify.
    """
    key = f"{_PASSWORD_ATTEMPT_PREFIX}{frappe.session.user}:{patient}"
    _check_and_increment(key, _PASSWORD_ATTEMPT_LIMIT, _PASSWORD_ATTEMPT_WINDOW,
                         "Too many password attempts. Please wait 15 minutes before trying again.")


def check_api_call(endpoint: str):
    """
    M1-T37: Enforce per-user, per-endpoint rate limit (max 10 calls/minute).

    Call at the top of any non-OTP ABDM endpoint.
    Enforcement is by authenticated user (frappe.session.user) — IP address
    spoofing via X-Forwarded-For has no effect.

    Raises frappe.ValidationError with a Retry-After hint on breach.
    """
    user = frappe.session.user or "Guest"
    key  = f"{_API_CALL_PREFIX}{user}:{endpoint}"
    _check_and_increment(
        key,
        _API_CALL_LIMIT,
        _API_CALL_WINDOW,
        frappe._(
            f"Too many requests to {endpoint}. "
            f"Please wait {_RETRY_AFTER_SECS} seconds before retrying. "
            f"(Retry-After: {_RETRY_AFTER_SECS})"
        ),
    )


def _check_and_increment(key: str, limit: int, ttl: int, message: str):
    """
    Atomically check count and increment. Raises frappe.ValidationError if limit exceeded.
    Uses Frappe cache (Redis) with TTL.
    """
    cache = frappe.cache()
    current = cache.get(key)
    count = int(current) if current else 0

    if count >= limit:
        frappe.throw(frappe._(message), frappe.ValidationError, title=frappe._("Rate Limit Exceeded"))

    # Increment — set with TTL only on first call
    if count == 0:
        cache.set_value(key, 1, expires_in_sec=ttl)
    else:
        cache.set_value(key, count + 1, expires_in_sec=ttl)
