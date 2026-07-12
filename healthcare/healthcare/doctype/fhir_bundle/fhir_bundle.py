"""FHIR Bundle DocType controller — M1-T84. Foundation only (M2/M3 HIU data-fetch flow consumes this)."""
import frappe
from frappe.model.document import Document


class FHIRBundle(Document):
	def validate(self):
		self._idor_check()

	def _idor_check(self):
		"""IDOR: current user must have write access to the Patient behind the linked Health Document."""
		if not self.health_document:
			return
		patient = frappe.db.get_value("Health Document", self.health_document, "patient")
		if patient and not frappe.has_permission("Patient", doc=patient, ptype="write"):
			frappe.throw(
				frappe._("Insufficient permissions to manage this FHIR Bundle"),
				frappe.PermissionError,
			)
