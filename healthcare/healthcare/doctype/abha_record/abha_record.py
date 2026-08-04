"""
ABHA Record DocType controller — M1-T2
FHIR R4 Patient.identifier[] compatible.
"""
import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


def unlink_abha_from_patient(patient: str) -> None:
	"""
	Clear everything on the Frappe side that points at a patient's ABHA once
	it's gone (whether via local ABHA Record delete, or a real ABDM-side
	delete confirmed through the lifecycle-action flow) — otherwise the
	mirrored Patient fields, stale tokens, and FHIR cache keep referencing
	an account that no longer exists, confusing re-enrolment.

	Does NOT touch the ABHA Record document itself or ABHA Address Detail
	rows — callers that are actually deleting the ABHA Record handle those
	separately (see ABHARecord.on_trash), since a status-only lifecycle
	update (e.g. confirm_lifecycle_action) keeps the record for audit history.
	"""
	if not patient:
		return

	# Clear the denormalised convenience copy on Patient (set by
	# api/enrol.py::_sync_abha_fields_to_patient on creation).
	try:
		frappe.db.set_value("Patient", patient, {
			"abha_number": None,
			"abha_address": None,
		})
	except Exception:
		pass  # fields may not exist outside India regional setup

	# Drop all ABDM token state for this patient — a fresh enrolment
	# needs a fresh T-token, not one left over from the deleted ABHA.
	reg_name = frappe.db.get_value("ABDM Token Registry", {"patient": patient}, "name")
	if reg_name:
		frappe.delete_doc("ABDM Token Registry", reg_name, ignore_permissions=True, force=True)

	# Re-sync FHIR cache so it reflects the ABHA removal too.
	try:
		from healthcare.regional.india.abdm.patient_builder import build_patient_fhir
		build_patient_fhir(patient)
	except Exception as e:
		frappe.log_error(f"FHIR cache sync failed for patient={patient}: {type(e).__name__}", "ABDM FHIR")


class ABHARecord(Document):
	# Whitelist: server-set fields that must never come from client input (M1-T7 mass assignment)
	SERVER_ONLY_FIELDS = {"abha_number", "patient", "status", "created_at", "verified_at"}

	def before_insert(self):
		# Always set created_at server-side
		self.created_at = now_datetime()

	def validate(self):
		self._validate_abha_number_format()
		self._validate_patient_permission()

	def on_trash(self):
		"""
		Unwind everything linked to this ABHA so the patient is left in a clean
		state re-creatable via Create ABHA — otherwise the mirrored Patient
		fields and stale tokens survive the delete and confuse re-enrolment.
		"""
		from healthcare.regional.india.abdm.utils.audit import audit_log

		self._validate_patient_permission()

		# Block deleting a still-live ABHA locally — that would silently orphan
		# it on ABDM's side (local record gone, real account still exists
		# there). No role bypass, including System Manager/Administrator — the
		# OTP-verified "Delete via ABDM" flow is the only way to remove a live
		# ABHA, no exceptions. That flow sets status to DELETED first, which is
		# what actually unblocks the local delete afterward. Deleting the
		# record as a cascade from its Patient being deleted (see
		# patient_hooks.py) is a separate, already-deliberate action and skips
		# this guard via its own flag.
		if self.status != "DELETED" and not self.flags.get("cascade_from_patient_delete"):
			frappe.throw(
				frappe._(
					'This ABHA is still {0} on ABDM. Use "Delete via ABDM (OTP)" on this '
					"record to remove it from ABDM first, rather than deleting the local "
					"record directly."
				).format(self.status),
				frappe.PermissionError,
			)

		# Delete dependent ABHA Address Detail rows first — Frappe's link check
		# runs AFTER on_trash, so without this the whole delete is rejected with
		# "linked with ABHA Address Detail ..." and none of the cleanup below
		# (which happens before that check) ever gets a chance to matter.
		for name in frappe.get_all("ABHA Address Detail", filters={"abha_record": self.name}, pluck="name"):
			frappe.delete_doc("ABHA Address Detail", name, ignore_permissions=True, force=True)

		unlink_abha_from_patient(self.patient)

		audit_log("ABHA_DELETE", patient=self.patient, result="SUCCESS")

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
