# Copyright (c) 2025, earthians and contributors
# For license information, please see license.txt

import json

import shortuuid

import frappe
from frappe import _

DICOM_TO_FRAPPE_MAP = {
	"00100020": "patient",  # Patient ID
	"00100010": "patient_name",  # Patient Name
	"00100030": "date_of_birth",  # DOB
	"00100040": "gender",  # Gender
	"00400001": "scheduled_date",  # Scheduled Date
	"00400002": "scheduled_date",  # Fallback required?
	"00400003": "scheduled_time",  # Scheduled Time
	"00404010": "observation_template",  # Procedure Code
	"00080050": "name",  # Accession Number
	"00081030": "modality",  # Modality
	"00404011": "scheduled_datetime",  # Scheduled DateTime
}

# supporting "like"
PARTIAL_MATCH_FIELDS = {"00100010"}

# supporting range filters "between"
RANGE_FIELDS = {"00400002"}


def dicomify_gender(value):
	return {
		"male": "M",
		"female": "F",
		"other": "O",
		"unknown": "U",
	}.get(str(value).strip().lower(), "U")


def dicom_to_frappe_value(tag, value):
	"""TODO: handle '*'"""
	if isinstance(value, str):
		if tag in {"00100010", "00081030"}:  # Patient Name, Modality
			return value.replace("^", " ")
	return value


@frappe.whitelist(allow_guest=True)
def get_ups_tasks(filters=None):
	"""Return DICOMWeb dataset for UPS-RS request"""
	# curl -X POST http://v16:8000/api/method/healthcare.healthcare.api.ups_rs.get_ups_tasks \
	# -H "Content-Type: application/json" \
	# --data '{"filters": {"00100010": "Jane^", "00400002__from": "20250601", "00400002__to": "20260630"}}'

	if isinstance(filters, str):
		try:
			filters = json.loads(filters)
		except Exception:
			import traceback

			frappe.log_error(traceback.format_exc(), "UPS RS JSON Decode Error")
			frappe.throw(_("Invalid filters format. Must be valid JSON."))
	elif isinstance(filters, dict):
		pass
	elif filters is None:
		filters = {}
	else:
		frappe.throw(_("Filters must be a JSON string or dictionary."))

	frappe_filters = {}
	for tag, value in filters.items():
		if tag.endswith("__from") or tag.endswith("__to"):
			continue

		frappe_field = DICOM_TO_FRAPPE_MAP.get(tag)
		if not frappe_field:
			continue

		clean_value = dicom_to_frappe_value(tag, value)
		if tag in PARTIAL_MATCH_FIELDS:
			frappe_filters[frappe_field] = ["like", f"%{clean_value}%"]
		else:
			frappe_filters[frappe_field] = clean_value

	for tag in RANGE_FIELDS:
		frappe_field = DICOM_TO_FRAPPE_MAP.get(tag)
		from_val = filters.get(f"{tag}__from")
		to_val = filters.get(f"{tag}__to")

		if from_val and to_val:
			frappe_filters[frappe_field] = ["between", [from_val, to_val]]
		elif from_val:
			frappe_filters[frappe_field] = [">=", from_val]
		elif to_val:
			frappe_filters[frappe_field] = ["<=", to_val]

	frappe_filters.setdefault("status", "Scheduled")
	# frappe.log_error(frappe_filters)
	worklist = frappe.get_all(
		"UPS Appointment",
		filters=frappe_filters,
		fields=[
			"name",
			"appointment",
			"ups_instance_uid",
			"patient",
			"patient_name",
			"gender",
			"date_of_birth",
			"observation_template",
			"scheduled_date",
			"scheduled_time",
			"modality",
		],
	)

	result = []
	for t in worklist:
		uid = t.get("ups_instance_uid") or str(shortuuid.uuid())

		if not t.get("ups_instance_uid"):
			frappe.db.set_value("UPS Appointment", t.name, "ups_instance_uid", uid)
		try:

			if t.get("scheduled_date") and t.get("scheduled_time"):
				scheduled_date = t["scheduled_date"].strftime("%Y%m%d")
				scheduled_time = "{:02d}{:02d}{:02d}".format(
					t["scheduled_time"].seconds // 3600,
					(t["scheduled_time"].seconds % 3600) // 60,
					t["scheduled_time"].seconds % 60,
				)

			result.append(
				{
					"UPSInstanceUID": uid,
					"00080050": {"vr": "SH", "Value": [t.get("name")]},
					"00100020": {"vr": "LO", "Value": [t.get("patient").replace(" ", "-")]},
					"00100010": {"vr": "PN", "Value": [t.get("patient_name").replace(" ", "^")]},
					"00100040": {"vr": "CS", "Value": [dicomify_gender(t.get("gender"))]},
					"00100030": {"vr": "DA", "Value": [t.get("date_of_birth").strftime("%Y%m%d")]},
					"00404010": {
						"vr": "SQ",
						"Value": [
							{
								"00080100": {"vr": "SH", "Value": [t.get("observation_template")]},
								"00081030": {"vr": "LO", "Value": [f"{t.modality} Imaging Procedure"]},
							}
						],
					},
					"00400002": {"vr": "DA", "Value": [scheduled_date]},
					"00404011": {
						"vr": "DT",
						"Value": [scheduled_date + scheduled_time],
					},
				}
			)
		except Exception as e:
			frappe.log_error(
				message=f"Appointment: {t}\nException: {e}",
				title=f"UPS-RS failed for {t.get('ups_instance_uid')}",
			)

	return result
