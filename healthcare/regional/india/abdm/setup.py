import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def setup():
	if not frappe.db.exists("Custom Field", "Patient-abha_address"):
		make_custom_fields()
	setup_abdm_settings_defaults()


def setup_abdm_settings_defaults():
	"""Upsert ABDM Settings — insert if missing, patch blanks if already exists."""
	defaults = {
		"environment": "sandbox",
		"abha_base_url": "https://abhasbx.abdm.gov.in/abha/api",
		"phr_base_url": "https://phrsbx.abdm.gov.in",
		"wrapper_base_url": "http://localhost:8082",
		"fhir_base_url": "https://nrces.in/ndhm/fhir/R4",
		"abdm_gateway_ip_allowlist": "[]",
	}

	if not frappe.db.exists("ABDM Settings", "ABDM Settings"):
		settings = frappe.get_doc({"doctype": "ABDM Settings", **defaults})
		settings.insert(ignore_permissions=True)
	else:
		settings = frappe.get_single("ABDM Settings")
		changed = False
		for field, value in defaults.items():
			if not getattr(settings, field, None):
				settings.set(field, value)
				changed = True
		if changed:
			settings.save(ignore_permissions=True)

	frappe.db.commit()
	frappe.logger("abdm").info("ABDM Settings initialised with sandbox defaults")


def make_custom_fields():
	company = frappe.get_all("Company", filters={"country": "India"})
	if not company:
		return
	custom_fields = get_custom_fields()
	create_custom_fields(custom_fields)


def get_custom_fields():
	custom_fields = {
		"Patient": [
			dict(
				fieldname="abha_address",
				label="PHR Address",
				fieldtype="Data",
				insert_after="status",
				read_only=1,
			),
			dict(
				fieldname="abha_number",
				label="ABHA Number",
				fieldtype="Data",
				insert_after="abha_address",
				read_only=1,
			),
			dict(
				fieldname="abha_card",
				label="ABHA Card",
				fieldtype="Attach",
				insert_after="patient_details",
				hidden=1,
			),
			dict(
				fieldname="consent_for_aadhaar_use",
				label="Consent For Aadhaar Use",
				fieldtype="Attach",
				insert_after="abha_card",
				hidden=1,
			),
		]
	}
	return custom_fields
