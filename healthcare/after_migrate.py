import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute_migrate():
    custom_fields = {

        "Notification" : [
			{
				"fieldname": "is_recurring_appointment",
				"label": "Is Recurring Appointments Notifications ?",
				"fieldtype": "Check",
				"insert_after": "channel",
			},
		],
		"Patient Appointment" : [
			{
				"fieldname": "recurring_appointments",
				"label": "Recurring Appointments",
				"fieldtype": "Check",
				"hidden" : 1
			}
		]
    }

    create_custom_fields(custom_fields)  

    print("Custom Fields for Referral Practitioner Integration created successfully") 