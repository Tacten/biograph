"""
M1-T19 / M1-T20: SSRF Prevention Utilities
============================================
T19 — Webhook SSRF: validate that ABDM callbacks originate from
      known gateway IPs configured in ABDM Settings.
T20 — FHIR reference URL SSRF: ensure no URL inside a callback
      payload resolves to RFC 1918 / loopback / link-local addresses,
      preventing server-side request forgery via crafted FHIR references.
"""

import ipaddress
import socket
from urllib.parse import urlparse

import frappe
from healthcare.regional.india.abdm.utils.log_utils import abdm_log

# ---------------------------------------------------------------------------
# RFC 1918, loopback, and link-local ranges that must never be fetched
# ---------------------------------------------------------------------------
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),        # loopback
    ipaddress.ip_network("169.254.0.0/16"),      # link-local
    ipaddress.ip_network("100.64.0.0/10"),       # shared address space
    ipaddress.ip_network("::1/128"),             # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),            # IPv6 ULA
    ipaddress.ip_network("fe80::/10"),           # IPv6 link-local
]


# ---------------------------------------------------------------------------
# T19 — IP allowlist enforcement
# ---------------------------------------------------------------------------

def assert_abdm_gateway_ip(request_ip: str | None) -> None:
    """
    M1-T19: Raise PermissionError if the caller's IP is not in the ABDM
    gateway IP allowlist configured in ABDM Settings.

    If the allowlist is empty or not configured, a WARNING is logged but
    the request is allowed (development / sandbox mode).
    The allowlist is a JSON array in ABDM Settings.abdm_gateway_ip_allowlist,
    e.g. ["103.5.6.0/24", "104.16.0.0/12"].

    Called for all allow_guest ABDM webhook endpoints.
    """
    import json

    try:
        settings = frappe.get_single("ABDM Settings")
        raw = getattr(settings, "abdm_gateway_ip_allowlist", None) or ""
        if not raw.strip():
            abdm_log(
                "warning",
                "ABDM gateway IP allowlist not configured — skipping IP check (sandbox/dev mode)",
            )
            return

        allowed = json.loads(raw)
        if not allowed:
            return

        client_ip = _extract_ip(request_ip)
        if not client_ip:
            abdm_log("warning", "Could not determine callback client IP — allowing")
            return

        client_addr = ipaddress.ip_address(client_ip)
        for entry in allowed:
            network = ipaddress.ip_network(entry, strict=False)
            if client_addr in network:
                return  # allowed

        abdm_log("error", f"ABDM callback rejected — IP not in allowlist (masked)")
        frappe.throw(
            frappe._("ABDM callback rejected: unauthorised source IP"),
            frappe.PermissionError,
        )
    except (frappe.PermissionError, frappe.ValidationError):
        raise
    except Exception as exc:
        # Never block a callback due to misconfigured allowlist
        abdm_log("warning", f"IP allowlist check error ({type(exc).__name__}) — allowing")


def _extract_ip(raw: str | None) -> str | None:
    """
    Extract the real client IP from X-Forwarded-For or REMOTE_ADDR.
    X-Forwarded-For may contain a comma-separated list; the first entry
    is the originating IP.

    NOTE: Only trust X-Forwarded-For if the server is behind a trusted
    reverse proxy. Spoofing this header is trivially easy otherwise.
    Per WASA guidance we use the last untrusted hop (rightmost) when the
    infrastructure is not fully controlled — here we use the first entry
    as ABDM sandbox does not traverse multiple proxies.
    """
    if not raw:
        return None
    # X-Forwarded-For format: "client, proxy1, proxy2"
    first = raw.split(",")[0].strip()
    try:
        ipaddress.ip_address(first)
        return first
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# T20 — FHIR reference URL SSRF prevention
# ---------------------------------------------------------------------------

def assert_safe_url(url: str, context: str = "") -> None:
    """
    M1-T20: Raise ValidationError if *url* resolves to a private/internal
    network address.  Call this before making any HTTP request derived from
    FHIR reference URLs received in ABDM callbacks.

    Checks:
    1. Scheme must be https (no http, file, gopher, …)
    2. Hostname must not be a numeric private IP
    3. DNS-resolved IPs must not fall in blocked ranges

    *context* is logged (sanitised) to aid debugging.
    """
    if not url:
        return

    parsed = urlparse(url)

    if parsed.scheme not in ("https",):
        abdm_log("error", f"SSRF block: disallowed scheme in FHIR ref ({context})")
        frappe.throw(
            frappe._("Disallowed URL scheme in ABDM payload"),
            frappe.ValidationError,
        )

    hostname = parsed.hostname
    if not hostname:
        frappe.throw(frappe._("Invalid URL in ABDM payload"), frappe.ValidationError)

    # Check if hostname is already an IP literal
    try:
        addr = ipaddress.ip_address(hostname)
        _assert_not_blocked(addr, context)
        return
    except ValueError:
        pass  # not an IP literal — resolve via DNS

    # DNS resolution
    try:
        resolved = socket.getaddrinfo(hostname, None)
        for item in resolved:
            addr = ipaddress.ip_address(item[4][0])
            _assert_not_blocked(addr, context)
    except socket.gaierror:
        # Cannot resolve — block to be safe
        abdm_log("error", f"SSRF block: unresolvable hostname in FHIR ref ({context})")
        frappe.throw(
            frappe._("Unresolvable hostname in ABDM payload"),
            frappe.ValidationError,
        )


def _assert_not_blocked(addr: ipaddress.IPv4Address | ipaddress.IPv6Address, context: str) -> None:
    for network in _BLOCKED_NETWORKS:
        if addr in network:
            abdm_log("error", f"SSRF block: private IP in FHIR ref ({context})")
            frappe.throw(
                frappe._("FHIR reference URL resolves to private network — blocked"),
                frappe.ValidationError,
            )


def sanitise_fhir_references(data: dict | list, _depth: int = 0) -> None:
    """
    M1-T20: Recursively walk *data* (decoded JSON) and call assert_safe_url
    on every value whose key is "reference", "url", or "valueUrl".
    Mutates nothing — only raises if a bad URL is found.
    Depth-limited to 20 to prevent stack exhaustion on malformed payloads.
    """
    if _depth > 20:
        return
    if isinstance(data, dict):
        for key, value in data.items():
            if key in ("reference", "url", "valueUrl") and isinstance(value, str):
                assert_safe_url(value, context=key)
            elif isinstance(value, (dict, list)):
                sanitise_fhir_references(value, _depth + 1)
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, (dict, list)):
                sanitise_fhir_references(item, _depth + 1)
