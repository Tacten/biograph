# Copyright (c) 2025, earthians and contributors
# For license information, please see license.txt

import json
from datetime import datetime

import frappe


@frappe.whitelist()
def handle_n_create():
	raw = frappe.request.json
	if isinstance(raw, str):
		raw = json.loads(raw)

	task = frappe.get_doc("Imaging Appointment", raw.get("accession_number"))
	if task.status in ["In Progress", "Completed"] or task.claimed_by or task.study_instance_uid:
		frappe.throw(
			f"{task.name} already {task.status}, claimed by {task.claimed_by}. Study UID {task.study_instance_uid}"
		)

	task.study_instance_uid = raw.get("study_instance_uid")
	task.claimed_by = raw.get("performed_station_ae")
	task.status = "In Progress"

	if raw.get("start_time"):
		start_datetime = datetime.strptime(raw.get("start_time"), "%Y%m%d%H%M%S")
	else:
		start_datetime = frappe.utils.now()
	task.study_start_time = start_datetime

	task.n_create = json.dumps(raw, indent=1)
	task.save(ignore_permissions=True)

	return {"status": "ok", "message": "N-CREATE accepted"}


@frappe.whitelist()
def handle_n_set():
	raw = frappe.request.json
	if isinstance(raw, str):
		raw = json.loads(raw)
	task = frappe.get_doc("Imaging Appointment", raw.get("accession_number"))
	task.status = "Completed"
	task.study_finish_time = raw.get("end_time", frappe.utils.now())
	task.n_set = json.dumps(raw, indent=1)
	task.save(ignore_permissions=True)

	return {"status": "ok", "message": "N-SET applied"}
