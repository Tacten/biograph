# Copyright (c) 2025, earthians and contributors
# For license information, please see license.txt

import json

import frappe


@frappe.whitelist()
def handle_n_create():
	raw = frappe.request.json
	if isinstance(raw, str):
		raw = json.loads(raw)

	ups = frappe.get_doc("Imaging Appointment", raw.get("accession_number"))
	if ups.status in ["In Progress", "Completed"] or ups.claimed_by or ups.study_instance_uid:
		frappe.throw(
			f"{ups.name} already {ups.status}, claimed by {ups.claimed_by}. Study UID {ups.study_instance_uid}"
		)

	ups.study_instance_uid = raw.get("study_instance_uid")
	ups.claimed_by = raw.get("performed_station_ae")
	ups.status = "In Progress"
	ups.study_start_time = raw.get("start_time", frappe.utils.now())
	ups.n_create = json.dumps(raw, indent=1)
	ups.save(ignore_permissions=True)

	return {"status": "ok", "message": "N-CREATE accepted"}


@frappe.whitelist()
def handle_n_set():
	print("handle_n_set")
	raw = frappe.request.json
	if isinstance(raw, str):
		raw = json.loads(raw)
	ups = frappe.get_doc("Imaging Appointment", raw.get("accession_number"))
	ups.status = "Completed"
	ups.study_finish_time = raw.get("end_time", frappe.utils.now())
	ups.n_set = json.dumps(raw, indent=1)
	ups.save(ignore_permissions=True)

	return {"status": "ok", "message": "N-SET applied"}
