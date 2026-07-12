"""
ABHA Address Detail — M1-T85.
Stores the patient's address as returned by ABHA V3 profile API.
Used by fhir/patient_builder.py to construct FHIR R4 Address element.
"""
import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


class ABHAAddressDetail(Document):
    def validate(self):
        self._idor_check()
        self.last_synced = now_datetime()

    def _idor_check(self):
        """IDOR: patient field must match abha_record.patient (M1-T4B)."""
        if self.abha_record:
            expected_patient = frappe.db.get_value("ABHA Record", self.abha_record, "patient")
            if expected_patient and self.patient != expected_patient:
                frappe.throw(
                    frappe._("Patient mismatch on ABHA Address Detail"),
                    frappe.PermissionError,
                )
