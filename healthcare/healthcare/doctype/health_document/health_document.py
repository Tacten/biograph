"""Health Document DocType controller — M1-T83. Foundation only (M2/M3 HIU data-fetch flow consumes this)."""
import frappe
from frappe.model.document import Document


class HealthDocument(Document):
	def validate(self):
		self._idor_check()
		self._cross_reference_check()

	def _idor_check(self):
		"""IDOR: current user must have write access to the linked Patient."""
		if self.patient and not frappe.has_permission("Patient", doc=self.patient, ptype="write"):
			frappe.throw(
				frappe._("Insufficient permissions to manage health documents for this patient"),
				frappe.PermissionError,
			)

	def _cross_reference_check(self):
		"""Ensure care_context (and consent, if set) belong to the same patient — prevents cross-patient linkage."""
		if self.care_context:
			cc_patient = frappe.db.get_value("Care Context", self.care_context, "patient")
			if cc_patient and cc_patient != self.patient:
				frappe.throw(
					frappe._("Patient mismatch between Health Document and its Care Context"),
					frappe.PermissionError,
				)
		if self.consent:
			consent_patient = frappe.db.get_value("Consent Request", self.consent, "patient")
			if consent_patient and consent_patient != self.patient:
				frappe.throw(
					frappe._("Patient mismatch between Health Document and its Consent Request"),
					frappe.PermissionError,
				)
