"""
M1-T36: FHIR parser hardening.

Protections:
  - XXE (XML External Entity) injection detection in FHIR text fields
  - 10 MB maximum payload size
  - Reject malformed JSON / non-dict payloads
  - Depth limit (50 levels) to prevent stack exhaustion on crafted bundles

Python's json.loads() is not vulnerable to XXE itself (it parses JSON, not
XML), but FHIR R4 resources often contain narrative.div (XHTML) and text
fields where XXE payloads might be embedded to exploit downstream XML parsers
(e.g. HAPI FHIR, NHA wrapper). We scan for the DOCTYPE/ENTITY pattern and
reject any payload that contains it.

Usage:
    from healthcare.regional.india.abdm.utils.fhir_validator import validate_fhir_payload

    validated = validate_fhir_payload(raw_body_bytes)
"""

import json
import re

import frappe

_MAX_PAYLOAD_BYTES = 10 * 1024 * 1024  # 10 MB
_MAX_DEPTH         = 50
_XXE_PATTERN       = re.compile(
    r'<!(?:DOCTYPE|ENTITY)[^>]*>',
    re.IGNORECASE | re.DOTALL,
)
_SCRIPT_PATTERN    = re.compile(
    r'<script[\s>]',
    re.IGNORECASE,
)


def validate_fhir_payload(raw: bytes) -> dict:
    """
    Validate a raw FHIR Bundle/Resource payload.

    Args:
        raw: Raw request body bytes.

    Returns:
        Parsed dict if valid.

    Raises:
        frappe.ValidationError on any security or format violation.
    """
    # 1. Size limit (T36: 10 MB max)
    if len(raw) > _MAX_PAYLOAD_BYTES:
        frappe.throw(
            frappe._(f"Payload too large. Maximum size is {_MAX_PAYLOAD_BYTES // (1024*1024)} MB."),
            frappe.ValidationError,
        )

    # 2. XXE detection — scan raw bytes before parsing (catches obfuscation)
    try:
        text = raw.decode("utf-8", errors="replace")
    except Exception:
        frappe.throw(frappe._("Invalid payload encoding"), frappe.ValidationError)

    if _XXE_PATTERN.search(text):
        frappe.throw(
            frappe._("External entities not permitted in FHIR payload"),
            frappe.ValidationError,
        )

    # 3. Script injection in narrative fields
    if _SCRIPT_PATTERN.search(text):
        frappe.throw(
            frappe._("Script tags not permitted in FHIR payload"),
            frappe.ValidationError,
        )

    # 4. JSON parse
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as e:
        frappe.throw(
            frappe._(f"Malformed JSON in FHIR payload: {type(e).__name__}"),
            frappe.ValidationError,
        )

    # 5. Must be a dict
    if not isinstance(data, dict):
        frappe.throw(
            frappe._("FHIR payload must be a JSON object"),
            frappe.ValidationError,
        )

    # 6. Depth limit
    _assert_depth(data, current=0)

    return data


def validate_fhir_resource_type(data: dict, expected: str | None = None) -> str:
    """
    Validate that resourceType is present and (optionally) matches expected.
    Returns the resourceType string.
    """
    rt = data.get("resourceType")
    if not rt or not isinstance(rt, str):
        frappe.throw(
            frappe._("FHIR payload missing resourceType"),
            frappe.ValidationError,
        )
    if expected and rt != expected:
        frappe.throw(
            frappe._(f"Expected FHIR resourceType '{expected}', got '{rt}'"),
            frappe.ValidationError,
        )
    return rt


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _assert_depth(obj, current: int) -> None:
    """Recursively check nesting depth. Raises on excessive depth."""
    if current > _MAX_DEPTH:
        frappe.throw(
            frappe._("FHIR payload nesting too deep (max 50 levels)"),
            frappe.ValidationError,
        )
    if isinstance(obj, dict):
        for v in obj.values():
            _assert_depth(v, current + 1)
    elif isinstance(obj, list):
        for item in obj:
            _assert_depth(item, current + 1)
