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
		],
		"Sales Invoice": [
			{
				"fieldname": "total_insurance_coverage_amount",
				"label": "Total Insurance Coverage Amount",
				"fieldtype": "Currency",
				"insert_after": "total",
				"read_only": True,
				"no_copy": True,
				"in_standard_filter": 1,
			},
			{
				"fieldname": "patient_payable_amount",
				"label": "Patient Payable Amount",
				"fieldtype": "Currency",
				"insert_after": "total_insurance_coverage_amount",
				"read_only": True,
				"no_copy": True,
			},
		],
		"Sales Invoice Item": [
			{
				"fieldname": "healthcare_insurance_section",
				"fieldtype": "Section Break",
				"insert_after": "is_free_item",
			},
			{
				"fieldname": "coverage_rate",
				"label": "Insurance Coverage Approved Rate",
				"fieldtype": "Currency",
				"insert_after": "healthcare_insurance_section",
				"read_only": True,
				"no_copy": True,
			},
			{
				"fieldname": "coverage_qty",
				"label": "Insurance Coverage Approved Qty",
				"fieldtype": "Float",
				"insert_after": "coverage_rate",
				"read_only": True,
				"no_copy": True,
			},
			{
				"fieldname": "coverage_percentage",
				"label": "Insurance Coverage %",
				"fieldtype": "Percent",
				"insert_after": "coverage_qty",
				"read_only": True,
				"no_copy": True,
			},
			{
				"fieldname": "insurance_coverage_amount",
				"label": "Insurance Coverage Amount",
				"fieldtype": "Currency",
				"insert_after": "coverage_percentage",
				"read_only": True,
				"no_copy": True,
			},
			{
				"fieldname": "healthcare_insurance_col_break",
				"fieldtype": "Column Break",
				"insert_after": "insurance_coverage_amount",
			},
			{
				"fieldname": "patient_insurance_policy",
				"label": "Patient Insurance Policy Number",
				"fieldtype": "Data",
				"read_only": True,
				"insert_after": "healthcare_insurance_col_break",
			},
			{
				"fieldname": "insurance_coverage",
				"label": "Patient Insurance Coverage",
				"fieldtype": "Link",
				"read_only": True,
				"insert_after": "patient_insurance_policy",
				"options": "Patient Insurance Coverage",
				"no_copy": True,
			},
			{
				"fieldname": "insurance_payor",
				"label": "Insurance Payor",
				"fieldtype": "Link",
				"read_only": True,
				"insert_after": "insurance_coverage",
				"options": "Insurance Payor",
				"no_copy": True,
			},
		],
		"Journal Entry": [
			{
				"fieldname": "insurance_coverage",
				"label": "For Insurance Coverage",
				"fieldtype": "Link",
				"options": "Patient Insurance Coverage",
				"insert_after": "due_date",
				"read_only": True,
				"no_copy": True,
			}
		],
		"Payment Entry Reference": [
			{
				"fieldname": "insurance_claim",
				"label": "Insurance Claim",
				"fieldtype": "Link",
				"options": "Insurance Claim",
				"insert_after": "reference_name",
				"read_only": True,
				"no_copy": True,
			},
			{
				"fieldname": "insurance_claim_coverage",
				"label": "Insurance Claim Coverage",
				"fieldtype": "Link",
				"options": "Insurance Claim Coverage",
				"insert_after": "insurance_claim",
				"read_only": True,
				"no_copy": True,
			},
		],
    }

    create_custom_fields(custom_fields)

    print("Custom fields for Healthcare Insurance and Referral Practitioner Integration created successfully") 