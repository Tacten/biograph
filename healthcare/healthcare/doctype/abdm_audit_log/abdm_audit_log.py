"""
M1-T39: ABDM Audit Log DocType controller.

Immutable security audit trail for all ABDM operations.
Stores patient_id_hash (SHA-256) — never raw patient name or PII.
Only System Manager can read; no user can write via UI (insert via code only).
"""

import frappe
from frappe.model.document import Document


class ABDMAuditLog(Document):
    def onload(self):
        # M1-T29: reading the audit trail is itself a privileged action and
        # must be logged. onload() fires only when a document is explicitly
        # opened via the desk (frappe.desk.form.load.getdoc) — not on insert,
        # so this can't recurse into itself.
        if not self.is_new():
            from healthcare.regional.india.abdm.utils.audit import audit_log
            audit_log("ADMIN_ACCESS", result="SUCCESS")

    def before_insert(self):
        # Auto-set server timestamp regardless of client value
        self.timestamp = frappe.utils.now_datetime()

    def before_save(self):
        # before_save fires on insert too — only block modification of an
        # already-existing record, not the initial creation.
        if not self.is_new():
            frappe.throw(
                frappe._("ABDM Audit Log records are immutable and cannot be modified."),
                frappe.PermissionError,
            )

    def on_trash(self):
        frappe.throw(
            frappe._("ABDM Audit Log records cannot be deleted."),
            frappe.PermissionError,
        )
