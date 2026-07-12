"""FHIR Patient Cache DocType controller — M1-T79."""
import hashlib
import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


class FHIRPatientCache(Document):
	def before_save(self):
		# Auto-compute SHA256 hash of fhir_json for change detection
		if self.fhir_json:
			self.hash = hashlib.sha256(self.fhir_json.encode()).hexdigest()
		self.last_synced = now_datetime()
		# Always set fhir_version and resource_type
		self.fhir_version = "R4"
		self.resource_type = "Patient"
