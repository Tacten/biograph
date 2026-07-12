"""
ABHA Record DocType controller — M1-T2
FHIR R4 Patient.identifier[] compatible.
"""
import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


class ABHARecord(Document):
	# Whitelist: server-set fields that must never come from client input (M1-T7 mass assignment)
	SERVER_ONLY_FIELDS = {"abha_number", "patient", "status", "created_at", "verified_at"}

	def before_insert(self):
		# Always set created_at server-side
		self.created_at = now_datetime()

	def validate(self):
		self._validate_abha_number_format()
		self._validate_patient_permission()

	def _validate_abha_number_format(self):
		"""ABHA numbers are exactly 14 digits."""
		if self.abha_number and not self.abha_number.replace("-", "").isdigit():
			frappe.throw(frappe._("Invalid ABHA number format"), frappe.ValidationError)

	def _validate_patient_permission(self):
		"""IDOR check — current user must have write access to the linked Patient (M1-T4A/T4B)."""
		if self.patient and not frappe.has_permission("Patient", doc=self.patient, ptype="write"):
			frappe.throw(
				frappe._("You do not have permission to create an ABHA Record for this patient"),
				frappe.PermissionError,
			)
