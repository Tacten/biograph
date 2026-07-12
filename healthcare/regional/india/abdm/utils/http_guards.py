"""
M1-T35: HTTP method enforcement for ABDM endpoints.

All ABDM mutation endpoints must reject non-POST requests with 405.
Frappe's @frappe.whitelist() accepts both GET and POST by default;
this decorator enforces POST-only at the application layer.

Usage:
    from healthcare.regional.india.abdm.utils.http_guards import require_post

    @frappe.whitelist()
    @require_post
    def my_endpoint():
        ...

The decorator also sets the Allow header to guide API clients.
"""

import functools

import frappe


def require_post(fn):
    """
    Decorator: reject any request that is not an HTTP POST with 405.
    Safe to apply to any @frappe.whitelist() function.
    Works when the function is called via Frappe's API gateway
    (frappe.request is available) and is a no-op when called
    programmatically from within Python (no request context).
    """
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            method = frappe.request.method
        except Exception:
            # No HTTP request context (e.g. unit test, scheduled task) — allow
            return fn(*args, **kwargs)

        if method.upper() != "POST":
            frappe.response["http_status_code"] = 405
            frappe.response["headers"] = {"Allow": "POST"}
            frappe.response["message"] = (
                f"Method '{method}' not allowed. This endpoint only accepts POST."
            )
            # Raise to abort further processing — Frappe will serialise the response
            raise frappe.PermissionError(
                frappe._("Method Not Allowed. Use POST.")
            )

        return fn(*args, **kwargs)

    return wrapper
