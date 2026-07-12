"""Consent Request DocType controller — M1-T82. Foundation only (M2/M3 HIU consent flow consumes this)."""
import frappe
from frappe.model.document import Document


class ConsentRequest(Document):
	def validate(self):
		self._idor_check()

	def _idor_check(self):
		"""IDOR: current user must have write access to the linked Patient."""
		if self.patient and not frappe.has_permission("Patient", doc=self.patient, ptype="write"):
			frappe.throw(
				frappe._("Insufficient permissions to manage consent requests for this patient"),
				frappe.PermissionError,
			)
