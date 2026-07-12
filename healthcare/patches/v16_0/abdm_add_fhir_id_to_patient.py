"""
Add fhir_id (UUID) field to existing Patient DocType.
This is the FHIR R4 Patient.id anchor for all cross-resource references.
Run once via: bench migrate
"""
import uuid
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	# Add fhir_id custom field to Patient DocType if it doesn't exist
	if not frappe.db.has_column("Patient", "fhir_id"):
		create_custom_fields(
			{
				"Patient": [
					{
						"fieldname": "fhir_id",
						"fieldtype": "Data",
						"label": "FHIR ID",
						"description": "FHIR R4 Patient.id (UUID) — anchor for all FHIR cross-resource references",
						"read_only": 1,
						"no_copy": 1,
						"insert_after": "patient_name",
						"bold": 0,
						"in_list_view": 0,
						"search_index": 1,
					}
				]
			}
		)

	# Populate fhir_id for all existing Patient records that don't have one
	patients_without_fhir_id = frappe.get_all(
		"Patient",
		filters={"fhir_id": ["is", "not set"]},
		fields=["name"],
	)

	for patient in patients_without_fhir_id:
		frappe.db.set_value("Patient", patient["name"], "fhir_id", str(uuid.uuid4()))

	frappe.db.commit()
	frappe.logger("abdm").info(
		f"fhir_id populated for {len(patients_without_fhir_id)} patients"
	)
