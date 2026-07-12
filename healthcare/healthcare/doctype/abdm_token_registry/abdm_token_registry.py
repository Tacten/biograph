"""
ABDM Token Registry — M1-T78.
Single source of truth for all ABDM token state per patient.
All token fields are Password type (masked in UI, never appear in logs).
"""
import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime, add_to_date


class ABDMTokenRegistry(Document):
	def validate(self):
		self._idor_check()

	def _idor_check(self):
		"""Ensure the current user has write access to the linked Patient (M1-T4A IDOR guard)."""
		if self.patient and not frappe.has_permission("Patient", doc=self.patient, ptype="write"):
			frappe.throw(
				frappe._("Insufficient permissions to manage ABDM tokens for this patient"),
				frappe.PermissionError,
			)


# --- Module-level helpers used by abha_client.py ---

def get_or_create_registry(patient: str) -> "ABDMTokenRegistry":
	"""Get existing registry or create a new one for the given patient."""
	if frappe.db.exists("ABDM Token Registry", {"patient": patient}):
		return frappe.get_doc("ABDM Token Registry", {"patient": patient})
	doc = frappe.get_doc({
		"doctype": "ABDM Token Registry",
		"patient": patient,
	})
	doc.insert(ignore_permissions=False)
	return doc


def store_t_token(patient: str, t_token: str):
	"""Store the enrolment T-token for a patient."""
	reg = get_or_create_registry(patient)
	reg.t_token = t_token
	reg.t_token_created = now_datetime()
	reg.save(ignore_permissions=False)


def store_x_token(patient: str, x_token: str, expiry_minutes: int = 1440):
	"""Store the X-token (post-login session) for a patient."""
	reg = get_or_create_registry(patient)
	reg.x_token = x_token
	reg.x_token_expiry = add_to_date(now_datetime(), minutes=expiry_minutes)
	reg.save(ignore_permissions=False)


def store_linking_token(patient: str, linking_token: str, expiry_minutes: int = 60):
	"""Store the HIP linking token from share_profile callback."""
	# IDOR: validate patient permission before storing
	if not frappe.has_permission("Patient", doc=patient, ptype="write"):
		frappe.throw(frappe._("IDOR: cannot store linking token for this patient"), frappe.PermissionError)
	reg = get_or_create_registry(patient)
	reg.linking_token = linking_token
	reg.linking_token_expiry = add_to_date(now_datetime(), minutes=expiry_minutes)
	reg.save(ignore_permissions=False)


def get_x_token(patient: str) -> str | None:
	"""Retrieve the X-token for a patient, checking expiry."""
	from frappe.utils import get_datetime
	reg_name = frappe.db.get_value("ABDM Token Registry", {"patient": patient}, "name")
	if not reg_name:
		return None
	reg = frappe.get_doc("ABDM Token Registry", reg_name)
	if not reg.x_token:
		return None
	if reg.x_token_expiry and get_datetime(reg.x_token_expiry) < get_datetime(now_datetime()):
		return None  # Expired
	return reg.get_password("x_token")


def clear_all_tokens(patient: str):
	"""Clear all tokens for a patient — called on logout (M1-T51)."""
	reg_name = frappe.db.get_value("ABDM Token Registry", {"patient": patient}, "name")
	if not reg_name:
		return
	frappe.db.set_value(
		"ABDM Token Registry",
		reg_name,
		{
			"gateway_access_token": None,
			"gateway_token_expiry": None,
			"x_token": None,
			"x_token_expiry": None,
			"linking_token": None,
			"linking_token_expiry": None,
		},
	)
