# Copyright (c) 2026, earthians Health Informatics Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import now_datetime, time_diff_in_seconds


def execute(filters=None):
	filters = filters or {}
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{
			"fieldname": "name",
			"label": _("Emergency Record"),
			"fieldtype": "Link",
			"options": "Emergency Record",
			"width": 150,
		},
		{"fieldname": "acuity", "label": _("Acuity"), "fieldtype": "Data", "width": 130},
		{"fieldname": "patient_name", "label": _("Patient"), "fieldtype": "Data", "width": 160},
		{"fieldname": "chief_complaint", "label": _("Chief Complaint"), "fieldtype": "Data", "width": 200},
		{"fieldname": "status", "label": _("Status"), "fieldtype": "Data", "width": 120},
		{
			"fieldname": "service_unit",
			"label": _("Bed"),
			"fieldtype": "Link",
			"options": "Healthcare Service Unit",
			"width": 120,
		},
		{
			"fieldname": "attending_practitioner",
			"label": _("Attending"),
			"fieldtype": "Link",
			"options": "Healthcare Practitioner",
			"width": 150,
		},
		{"fieldname": "minutes_in_department", "label": _("Mins in Dept"), "fieldtype": "Int", "width": 110},
	]


def get_data(filters):
	conditions = {"status": ["not in", ["Closed", "Cancelled"]]}
	if filters.get("company"):
		conditions["company"] = filters.get("company")

	records = frappe.get_all(
		"Emergency Record",
		filters=conditions,
		fields=[
			"name",
			"patient_name",
			"chief_complaint",
			"status",
			"service_unit",
			"attending_practitioner",
			"triage_level",
			"arrival_datetime",
		],
	)

	for record in records:
		set_acuity(record)
		set_minutes_in_department(record)

	return sorted(
		records, key=lambda row: (row.get("priority") or 9999, row.get("arrival_datetime") or now_datetime())
	)


def set_acuity(record):
	record["priority"] = 9999
	record["acuity"] = ""
	if not record.get("triage_level"):
		return

	color, priority = frappe.db.get_value("Triage Level", record["triage_level"], ["color", "priority"]) or (
		None,
		None,
	)
	record["priority"] = priority or 9999
	record["acuity"] = (
		f'<span style="display:inline-flex;align-items:center;gap:6px">'
		f'<span style="width:10px;height:10px;border-radius:50%;background:{color or "#a6b1b9"}"></span>'
		f"{frappe.utils.escape_html(record['triage_level'])}</span>"
	)


def set_minutes_in_department(record):
	if record.get("arrival_datetime"):
		record["minutes_in_department"] = max(
			0, int(time_diff_in_seconds(now_datetime(), record["arrival_datetime"]) // 60)
		)
	else:
		record["minutes_in_department"] = 0
