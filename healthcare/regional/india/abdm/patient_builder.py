"""
M1-T80: FHIR R4 Patient builder.

Converts Frappe Patient + ABHA Record → complete FHIR R4 Patient JSON
with correct Identifier system URIs, HumanName, gender, birthDate, telecom, Address.
Stores result in FHIR Patient Cache.
Called after every ABHA create/verify/update.
"""
import json
import frappe
from frappe.utils import now_datetime

# FHIR R4 Identifier system URIs (M1 — FHIR Identifier Systems sheet)
ABHA_NUMBER_SYSTEM = "https://healthid.ndhm.gov.in"
ABHA_ADDRESS_SYSTEM = "https://abha.abdm.gov.in"


def build_patient_fhir(patient_name: str) -> dict:
	"""
	Build a complete FHIR R4 Patient resource for the given Frappe Patient.
	Returns the FHIR dict and saves it to FHIR Patient Cache.

	Usage (Frappe console):
	    healthcare.regional.india.abdm.patient_builder.build_patient_fhir('PATIENT-001')
	"""
	import uuid as _uuid

	patient = frappe.get_doc("Patient", patient_name)
	abha_record = _get_abha_record(patient_name)

	# Ensure fhir_id is set — lazily mint one if the patch hasn't run yet
	fhir_id = getattr(patient, "fhir_id", None) or patient.name
	if not getattr(patient, "fhir_id", None):
		try:
			new_id = str(_uuid.uuid4())
			frappe.db.set_value("Patient", patient_name, "fhir_id", new_id)
			fhir_id = new_id
		except Exception:
			pass  # custom field may not exist yet; use patient.name as fallback

	fhir_patient = {
		"resourceType": "Patient",
		"id": fhir_id,
		"meta": {
			"profile": [
				"https://nrces.in/ndhm/fhir/R4/StructureDefinition/Patient"
			]
		},
		"identifier": _build_identifiers(patient, abha_record),
		"active": abha_record.status == "ACTIVE" if abha_record else True,
		"name": _build_human_name(patient),
		"gender": _map_gender(patient.sex),
		"birthDate": str(patient.dob) if patient.dob else None,
		"telecom": _build_telecom(patient),
		"address": _build_address(patient, abha_record),
	}

	# Remove None values
	fhir_patient = {k: v for k, v in fhir_patient.items() if v is not None}

	# Persist to FHIR Patient Cache
	_update_fhir_cache(patient_name, fhir_patient)

	return fhir_patient


def _get_abha_record(patient_name: str):
	"""Return the first ABHA Record for the patient, or None."""
	records = frappe.get_all(
		"ABHA Record",
		filters={"patient": patient_name, "status": "ACTIVE"},
		fields=["name", "abha_number", "abha_address", "preferred_abha_address", "status", "abha_type"],
		limit=1,
	)
	if records:
		return frappe.get_doc("ABHA Record", records[0]["name"])
	return None


def _build_identifiers(patient, abha_record) -> list:
	identifiers = []
	if abha_record:
		identifiers.append({
			"type": {
				"coding": [{"system": "http://terminology.hl7.org/CodeSystem/v2-0203", "code": "MR"}]
			},
			"system": ABHA_NUMBER_SYSTEM,
			"value": abha_record.abha_number,
		})
		identifiers.append({
			"system": ABHA_ADDRESS_SYSTEM,
			"value": abha_record.preferred_abha_address or abha_record.abha_address,
			"use": "preferred" if abha_record.preferred_abha_address else "usual",
		})
	return identifiers


def _build_human_name(patient) -> list:
	name_parts = {"use": "official"}
	if patient.patient_name:
		parts = patient.patient_name.strip().split(" ", 1)
		name_parts["family"] = parts[-1] if len(parts) > 1 else parts[0]
		if len(parts) > 1:
			name_parts["given"] = [parts[0]]
		name_parts["text"] = patient.patient_name
	return [name_parts]


def _map_gender(sex: str) -> str:
	return {"Male": "male", "Female": "female", "Other": "other"}.get(sex or "", "unknown")


def _build_telecom(patient) -> list:
	telecom = []
	if getattr(patient, "mobile", None):
		telecom.append({"system": "phone", "value": patient.mobile, "use": "mobile"})
	if getattr(patient, "email", None):
		telecom.append({"system": "email", "value": patient.email})
	return telecom


def _build_address(patient, abha_record) -> list:
	# Attempt to use ABHA Address Detail if available (M1-T85)
	details = []
	if abha_record:
		try:
			details = frappe.get_all(
				"ABHA Address Detail",
				filters={"abha_record": abha_record.name},
				fields=["address_line", "district_name", "state_name", "pin_code"],
				limit=1,
			)
		except Exception:
			# DocType may not yet be migrated — degrade gracefully
			details = []

	if details:
		d = details[0]
		addr = {"country": "IN"}
		if d.get("address_line"):
			addr["text"] = d["address_line"]
		if d.get("district_name"):
			addr["district"] = d["district_name"]
		if d.get("state_name"):
			addr["state"] = d["state_name"]
		if d.get("pin_code"):
			addr["postalCode"] = d["pin_code"]
		return [addr]
	return []


# ---------------------------------------------------------------------------
# Whitelisted API endpoint — used by patient_abha.js to display FHIR data
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_fhir_patient(patient: str) -> dict:
	"""
	Return the cached FHIR Patient JSON for the given patient.
	Rebuilds the cache if it is stale (> 1 hour old) or missing.
	"""
	import json
	from frappe.utils import get_datetime, add_to_date

	patient = patient.strip()
	if not frappe.db.exists("Patient", patient):
		frappe.throw(frappe._("Patient not found"), frappe.ValidationError)

	if not frappe.has_permission("Patient", doc=patient, ptype="read"):
		frappe.throw(frappe._("Not permitted"), frappe.PermissionError)

	# Check cache freshness
	cache_name = frappe.db.get_value("FHIR Patient Cache", {"patient": patient}, "name")
	if cache_name:
		last_synced = frappe.db.get_value("FHIR Patient Cache", cache_name, "last_synced")
		if last_synced:
			age_cutoff = add_to_date(get_datetime(last_synced), hours=1)
			if get_datetime(frappe.utils.now_datetime()) < age_cutoff:
				fhir_json = frappe.db.get_value("FHIR Patient Cache", cache_name, "fhir_json")
				return {"fhir": json.loads(fhir_json), "cached": True}

	# Build / rebuild
	fhir = build_patient_fhir(patient)
	return {"fhir": fhir, "cached": False}


def _update_fhir_cache(patient_name: str, fhir_dict: dict):
	"""Upsert FHIR Patient Cache with the new FHIR JSON."""
	fhir_json = json.dumps(fhir_dict, indent=2)

	if frappe.db.exists("FHIR Patient Cache", {"patient": patient_name}):
		cache = frappe.get_doc("FHIR Patient Cache", {"patient": patient_name})
	else:
		cache = frappe.get_doc({
			"doctype": "FHIR Patient Cache",
			"patient": patient_name,
			"source": "ABDM",
		})

	cache.fhir_json = fhir_json
	cache.save(ignore_permissions=False)
