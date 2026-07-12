"""Care Context DocType controller — M1-T81. Foundation only (M2/M3 HIP linking consumes this)."""
import frappe
from frappe.model.document import Document


class CareContext(Document):
	def validate(self):
		self._idor_check()

	def _idor_check(self):
		"""IDOR: current user must have write access to the linked Patient."""
		if self.patient and not frappe.has_permission("Patient", doc=self.patient, ptype="write"):
			frappe.throw(
				frappe._("Insufficient permissions to manage care contexts for this patient"),
				frappe.PermissionError,
			)
