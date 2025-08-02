# Copyright (c) 2025, earthians and contributors
# For license information, please see license.txt

import json

import shortuuid

import frappe
from frappe import _

from healthcare.healthcare.doctype.imaging_study.imaging_study import humanize_dicom_json

DICOM_TO_FRAPPE_MAP = {
	"00100020": "patient",  # Patient ID
	"00100010": "patient_name",  # Patient Name
	"00100030": "date_of_birth",  # DOB
	"00100040": "gender",  # Gender
	"00400001": "scheduled_date",  # Scheduled Date
	"00400002": "scheduled_date",  # Fallback Scheduled Date
	"00400003": "scheduled_time",  # Scheduled Time
	"00404010": "observation_template",  # Procedure Code
	"00080050": "name",  # Accession Number
	"00081030": "modality",  # Modality
	"0008005A": "station_ae",  # Scheduled Device
}

# supporting "like"
PARTIAL_MATCH_FIELDS = {"00100010"}

# supporting range filters "between"
RANGE_FIELDS = {"00400002"}


def get_ups_tasks(filters=None):
	"""Return DICOMWeb dataset for UPS-RS request"""
	# curl -X POST https://site_url/api/method/healthcare.healthcare.api.ups_rs.get_ups_tasks \
	# -H "Content-Type: application/json" \
	# --data '{"filters": {"00100010": "Jane^", "00400002__from": "20250601", "00400002__to": "20260630"}}'
	frappe_filters = get_filters(filters)
	worklist = frappe.get_all(
		"Imaging Appointment",
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
			"station_ae",
		],
	)
	result = []
	for task in worklist:
		uid = task.get("ups_instance_uid") or str(shortuuid.uuid())

		if not task.get("ups_instance_uid"):
			frappe.db.set_value("Imaging Appointment", task.name, "ups_instance_uid", uid)
		try:

			if task.get("scheduled_date") and task.get("scheduled_time"):
				scheduled_date = task["scheduled_date"].strftime("%Y%m%d")
				scheduled_time = "{:02d}{:02d}{:02d}".format(
					task["scheduled_time"].seconds // 3600,
					(task["scheduled_time"].seconds % 3600) // 60,
					task["scheduled_time"].seconds % 60,
				)

			result.append(
				{
					"00080016": {"vr": "UI", "Value": ["1.2.840.10008.5.1.4.34.5"]},
					"00080018": {"vr": "UI", "Value": [task.get("ups_instance_uid")]},
					"00080050": {"vr": "SH", "Value": [task.get("name")]},
					"00100020": {"vr": "LO", "Value": [task.get("patient").replace(" ", "-")]},
					"00100010": {"vr": "PN", "Value": [task.get("patient_name").replace(" ", "^")]},
					"00100040": {"vr": "CS", "Value": [dicomify_gender(task.get("gender"))]},
					"00100030": {"vr": "DA", "Value": [task.get("date_of_birth").strftime("%Y%m%d")]},
					"00404010": {
						"vr": "SQ",
						"Value": [
							{
								"00080100": {"vr": "SH", "Value": [task.get("observation_template")]},
								"00081030": {"vr": "LO", "Value": [task.get("modality")]},
							}
						],
					},
					"0008005A": {"vr": "AE"},
					"Value": [task.get("station_ae")],
					"00400002": {"vr": "DA", "Value": [scheduled_date]},
					"00404011": {
						"vr": "DT",
						"Value": [scheduled_date + scheduled_time],
					},
				}
			)
		except Exception as e:
			frappe.log_error(
				message=f"Appointment: {task}\nException: {e}",
				title=f"UPS-RS failed for {task.get('ups_instance_uid')}",
			)

	return result


def process_ups_claim(uid, data, ae_title):
	doc = get_imaging_appointment(uid)

	doc.status = "In Progress"  # ds.get("00400275", {}).get("Value", ["In Progress"])[0]
	doc.claimed_by = data.get("00400241", {}).get("Value", [None])[0] or ae_title
	doc.study_instance_uid = data.get("0020000D", {}).get("Value", [None])[0]
	doc.n_create = json.dumps(humanize_dicom_json(data), indent=1)
	doc.save(ignore_permissions=True)

	return {"Status": "Claimed", "UPSInstanceUID": uid}


def cancel_ups(uid, data, ae_title):
	doc = get_imaging_appointment(uid)

	doc.status = "Cancelled"
	doc.cancelled_by = ae_title
	doc.n_cancel = json.dumps(humanize_dicom_json(data), indent=1)
	doc.dataset = json.dumps(data, indent=1)
	doc.save(ignore_permissions=True)

	return {"Status": "Cancelled", "UPSInstanceUID": uid}


def handle_workitem_event(uid, data, ae_title):
	doc = get_imaging_appointment(uid)

	new_status = data.get("Status", "Completed")
	if new_status not in ["In Progress", "Completed"]:
		frappe.throw(f"Invalid workitem status for Imaging Appointment ({uid})")
	doc.status = new_status
	doc.station_ae = ae_title
	doc.n_set = json.dumps(humanize_dicom_json(data), indent=1)
	doc.dataset = json.dumps(data, indent=1)
	doc.save(ignore_permissions=True)

	return {"Status": new_status, "UPSInstanceUID": uid}


def update_from_modality(uid, update_data, ae_title):
	doc = get_existing_imaging_appointment()

	if not doc:
		frappe.throw("Invalid ID for Imaging Appointment, document does not exist")

	for key, val in update_data.items():
		if hasattr(doc, key):
			setattr(doc, key, val)
	doc.save(ignore_permissions=True)

	return {"Status": "Updated", "UPSInstanceUID": uid}


def get_existing_imaging_appointment(id):
	result = frappe.db.get_all(
		"Imaging Appointment",
		or_filters=[
			["ups_instance_uid", "=", id],
			["study_instance_uid", "=", id],
			["name", "=", id],
		],
	)
	return frappe.get_doc("Imaging Appointment", result[0].name) if result and result[0] else None


def get_imaging_appointment(id):
	doc = get_existing_imaging_appointment(id)
	if not doc:
		doc = frappe.get_doc(
			{
				"doctype": "Imaging Appointment",
				"ups_instance_uid": id,  # insert with ups instance id
			}
		).insert(ignore_permissions=True)
		frappe.log_error(f"Imaging Appointment {id} does not exist, created a new one.")

	return doc


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


def get_filters(filters=None):
	if isinstance(filters, str):
		try:
			filters = json.loads(filters)
		except Exception as e:
			frappe.log_error(
				message=f"UPS RS JSON decode error building filters\n{e}", title="UPS RS JSON Decode Error"
			)
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

	return frappe_filters
