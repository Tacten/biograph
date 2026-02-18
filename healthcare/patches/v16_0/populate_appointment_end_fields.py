# Copyright (c) 2025, healthcare and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe.utils import get_time, getdate, flt
from datetime import datetime, timedelta


def execute():
	"""
	Populate appointment_end_time and appointment_end_datetime for existing appointments.
	These fields are required for the block-based appointment booking feature.
	"""
	appointments = frappe.get_all(
		"Patient Appointment",
		filters={
			"appointment_time": ["is", "set"],
			"duration": [">", 0]
		},
		fields=["name", "appointment_date", "appointment_time", "duration", "end_time"]
	)

	count = 0
	for appointment in appointments:
		try:
			update_values = {}

			# Calculate end time based on duration
			start_time = get_time(appointment.appointment_time)
			start_dt = datetime.combine(getdate(appointment.appointment_date), start_time)
			end_dt = start_dt + timedelta(minutes=flt(appointment.duration))
			end_time_str = end_dt.time().strftime("%H:%M:%S")
			end_datetime_str = end_dt.strftime("%Y-%m-%d %H:%M:%S")

			update_values["appointment_end_time"] = end_time_str
			update_values["appointment_end_datetime"] = end_datetime_str

			# Also update end_time if not set
			if not appointment.end_time:
				update_values["end_time"] = end_time_str

			frappe.db.set_value(
				"Patient Appointment",
				appointment.name,
				update_values,
				update_modified=False
			)
			count += 1

		except Exception as e:
			frappe.log_error(
				f"Error updating appointment {appointment.name}: {str(e)}",
				"Populate Appointment End Fields Patch"
			)

	if count > 0:
		frappe.db.commit()

	frappe.msgprint(f"Updated end time fields for {count} appointments")
