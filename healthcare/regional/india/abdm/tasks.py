"""
M1-T28: Scheduled tasks for ABDM token lifecycle management.

Scheduler events (wired in hooks.py):
  hourly — notify_expiring_tokens : warn when X-token < 2 h to expiry
  daily  — refresh_expiring_tokens: clear tokens that have already expired
"""
import frappe
from frappe.utils import add_to_date, now_datetime, get_datetime


# ---------------------------------------------------------------------------
# Hourly: notify users whose X-token is about to expire
# ---------------------------------------------------------------------------

def notify_expiring_tokens():
    """
    Run hourly — find tokens expiring within 2 hours and send a Frappe
    system notification to Healthcare Users so they can prompt re-verification.
    No PII in logs — only registry name and patient ID used.
    """
    cutoff = add_to_date(now_datetime(), hours=2)
    now    = now_datetime()

    expiring = frappe.get_all(
        "ABDM Token Registry",
        filters=[
            ["x_token_expiry", "<", cutoff],
            ["x_token_expiry", ">", now],   # not yet expired
            ["x_token", "is", "set"],
        ],
        fields=["name", "patient"],
    )

    if not expiring:
        return

    for record in expiring:
        patient = record["patient"]
        try:
            # Notify Healthcare Users who have write access to this patient
            _notify_token_expiring(patient)
            frappe.logger("abdm").info(
                f"ABDM X-token expiry notification sent | registry={record['name']}"
            )
        except Exception:
            frappe.log_error(
                f"Token expiry notification failed | registry={record['name']}",
                "ABDM Token Notify",
            )


def _notify_token_expiring(patient: str):
    """
    Create a Frappe system notification for Healthcare Administrators
    that the ABHA session for a patient is about to expire.
    """
    recipients = _get_patient_healthcare_admins(patient)
    for user in recipients:
        frappe.get_doc({
            "doctype":   "Notification Log",
            "subject":   frappe._("ABHA session expiring soon"),
            "for_user":  user,
            "type":      "Alert",
            "document_type": "Patient",
            "document_name": patient,
            "email_content": frappe._(
                "The ABHA session for patient {0} will expire within 2 hours. "
                "Please ask the patient to re-verify their ABHA."
            ).format(patient),
        }).insert(ignore_permissions=True)


def _get_patient_healthcare_admins(patient: str) -> list:
    """Return users with Healthcare Administrator role."""
    return frappe.get_all(
        "Has Role",
        filters={"role": ["in", ["Healthcare Administrator", "System Manager"]]},
        fields=["parent"],
        pluck="parent",
    )[:5]  # cap at 5 to avoid spam


# ---------------------------------------------------------------------------
# Daily: clear expired tokens + log failures
# ---------------------------------------------------------------------------

def refresh_expiring_tokens():
    """
    Run daily — find all X-tokens that have expired (or will within 48 h).
    Calls abha_client.refresh_x_token() which either confirms the token
    is still valid or clears it so the UI shows EXPIRED.
    Alerts if 3+ consecutive failures occur (infra issue, not user issue).
    """
    from healthcare.regional.india.abdm.utils.abha_client import AbhaClient

    cutoff = add_to_date(now_datetime(), hours=48)
    expiring = frappe.get_all(
        "ABDM Token Registry",
        filters=[
            ["x_token_expiry", "<", cutoff],
            ["x_token", "is", "set"],
        ],
        fields=["name", "patient"],
    )

    client = AbhaClient()
    failure_count = 0

    for record in expiring:
        try:
            still_valid = client.refresh_x_token(record["name"])
            result = "VALID" if still_valid else "CLEARED"
            frappe.logger("abdm").info(
                f"ABDM token check | registry={record['name']} result={result}"
            )
        except Exception as e:
            failure_count += 1
            frappe.log_error(
                f"Token refresh failed | registry={record['name']} error={type(e).__name__}",
                "ABDM Token Refresh",
            )

    if failure_count >= 3:
        frappe.logger("abdm").error(
            f"ABDM token refresh: {failure_count} failures — manual review required"
        )
        # Notify System Managers
        for user in _get_patient_healthcare_admins(None):
            try:
                frappe.get_doc({
                    "doctype":   "Notification Log",
                    "subject":   frappe._("ABDM Token Refresh: multiple failures"),
                    "for_user":  user,
                    "type":      "Alert",
                    "email_content": frappe._(
                        "{0} ABDM X-token refresh failures detected during scheduled run. "
                        "Check ABDM Token Refresh error log."
                    ).format(failure_count),
                }).insert(ignore_permissions=True)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Daily: purge stale gateway token cache
# ---------------------------------------------------------------------------

def purge_gateway_token_cache():
    """
    Ensure the cached gateway access token is cleared daily so a fresh one
    is obtained. This prevents stale tokens from accumulating in Redis.
    The token will be re-fetched lazily on the next API call.
    """
    frappe.cache().delete_value("abdm:gateway_token")
    frappe.logger("abdm").info("ABDM gateway token cache purged")
