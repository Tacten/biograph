"""
Patient doc_events hooks — cascade-delete ABDM "convenience" data (cache and
session records, not clinical history) linked to a Patient before Frappe's
link check runs on Patient delete. Without this, deleting any patient that
ever went through Create ABHA / Verify ABHA fails with a LinkExistsError
against whichever of these happens to exist — ABHA Record, ABHA Address
Detail, ABDM Token Registry, ABDM Consent, FHIR Patient Cache.

Genuine clinical doctypes (Patient Encounter, Lab Test, etc.) are deliberately
left alone here — those SHOULD keep blocking a patient delete until handled
explicitly; this hook only clears ABDM's own bookkeeping.
"""
import frappe


def cleanup_abdm_data_before_patient_delete(doc, method=None):
	patient = doc.name

	# ABHA Record's own on_trash cascades ABHA Address Detail and clears the
	# Patient mirror fields / Token Registry / FHIR cache via
	# unlink_abha_from_patient — deleting it here reuses that logic instead
	# of duplicating it. cascade_from_patient_delete bypasses on_trash's
	# still-ACTIVE guard — deleting the whole Patient is already a deliberate
	# action, separate from directly deleting a live ABHA Record.
	for name in frappe.get_all("ABHA Record", filters={"patient": patient}, pluck="name"):
		frappe.delete_doc(
			"ABHA Record", name, ignore_permissions=True, force=True,
			flags={"cascade_from_patient_delete": True},
		)

	# Safety net: a Token Registry row can exist even without a completed
	# ABHA Record (e.g. an OTP was requested but enrolment never finished),
	# so ABHA Record's cascade above won't always have caught it.
	reg_name = frappe.db.get_value("ABDM Token Registry", {"patient": patient}, "name")
	if reg_name:
		frappe.delete_doc("ABDM Token Registry", reg_name, ignore_permissions=True, force=True)

	# ABDM Consent (frappe_abdm) — recorded at the Create ABHA consent step,
	# independent of whether enrolment ever completed.
	if frappe.db.table_exists("ABDM Consent"):
		for name in frappe.get_all("ABDM Consent", filters={"patient": patient}, pluck="name"):
			frappe.delete_doc("ABDM Consent", name, ignore_permissions=True, force=True)

	# FHIR Patient Cache — pure cache, safe to drop regardless of the above.
	cache_name = frappe.db.get_value("FHIR Patient Cache", {"patient": patient}, "name")
	if cache_name:
		frappe.delete_doc("FHIR Patient Cache", cache_name, ignore_permissions=True, force=True)
