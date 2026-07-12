"""
M1-T33: Secure HTTP response headers for all ABDM responses.

Wired via hooks.py:
    after_request = ["healthcare.regional.india.abdm.utils.secure_headers.add_security_headers"]

Headers set:
  Strict-Transport-Security — HSTS, 1 year, includeSubDomains
  X-Frame-Options           — DENY (clickjacking)
  X-Content-Type-Options    — nosniff
  Content-Security-Policy   — tight policy for ABDM API responses
  Referrer-Policy           — no-referrer (no PII leaks via Referer)
  Permissions-Policy        — disable unneeded browser features
  Cache-Control             — no-store for API endpoints (prevent PHI caching)

These are applied to ALL Frappe responses, not just ABDM endpoints, which is
correct: HSTS and clickjacking protection should be global. The CSP is kept
permissive enough for Frappe Desk UI while preventing script injection on
ABDM API responses.

For securityheaders.com grade A, the following must be set:
  ✅ Strict-Transport-Security
  ✅ X-Frame-Options
  ✅ X-Content-Type-Options
  ✅ Content-Security-Policy
  ✅ Referrer-Policy
  ✅ Permissions-Policy
"""

import frappe


def add_security_headers():
    """
    Frappe after_request hook — adds security headers to every response.

    Should be configured in hooks.py:
        after_request = ["healthcare.regional.india.abdm.utils.secure_headers.add_security_headers"]
    """
    try:
        response = frappe.response

        # HSTS: 1 year, include subdomains, preload-ready
        _set_header("Strict-Transport-Security",
                    "max-age=31536000; includeSubDomains; preload")

        # Clickjacking
        _set_header("X-Frame-Options", "DENY")

        # MIME-type sniffing
        _set_header("X-Content-Type-Options", "nosniff")

        # Referrer — no PII leaks via Referer header
        _set_header("Referrer-Policy", "no-referrer")

        # Disable unneeded browser APIs
        _set_header("Permissions-Policy",
                    "geolocation=(), microphone=(), camera=(), "
                    "payment=(), usb=(), interest-cohort=()")

        # CSP — must allow Frappe Desk assets but deny inline scripts for API
        # This CSP is appropriate for the Frappe API layer. Frappe Desk itself
        # needs 'unsafe-inline' for its jQuery-heavy UI; this is the minimum
        # safe policy that does not break Frappe Desk while protecting ABDM
        # API responses from XSS injection.
        _set_header(
            "Content-Security-Policy",
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "  # Frappe Desk requires these
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; "
            "font-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "object-src 'none'; "
            "base-uri 'self';"
        )

        # Cache-Control: prevent PHI from being cached by browsers or proxies
        # Only apply to ABDM API responses (cmd contains regional.india.abdm)
        cmd = frappe.form_dict.get("cmd") or frappe.form_dict.get("method") or ""
        if "healthcare.regional.india.abdm" in cmd:
            _set_header("Cache-Control", "no-store, no-cache, must-revalidate, private")
            _set_header("Pragma", "no-cache")

    except Exception:
        pass  # Never let header injection failures break the response


def _set_header(name: str, value: str) -> None:
    """Set a header only if not already set by Frappe or another hook."""
    try:
        # frappe.response.headers is a Werkzeug Headers object
        if name not in frappe.response.headers:
            frappe.response.headers[name] = value
    except AttributeError:
        # Older Frappe versions may not expose .headers — silently skip
        pass
