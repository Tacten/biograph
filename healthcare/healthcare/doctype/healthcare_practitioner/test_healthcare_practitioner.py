# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import frappe

from healthcare.tests.utils import HealthcareTestSuite


class TestHealthcarePractitioner(HealthcareTestSuite):
	def test_practitioner_mandatory_charges(self):
		fieldnames = ["op_consulting_charge", "inpatient_visit_charge"]
		for idx, fieldname in enumerate(fieldnames):
			item_fieldname = f"{fieldname}_item"
			charge_fieldname = f"{fieldname}"
			practitioner = frappe.get_doc(
				{
					"doctype": "Healthcare Practitioner",
					"first_name": f"__Test Healthcare Practitioner {idx}",
					"gender": "Female",
					item_fieldname: "HLC-SI-002",
					charge_fieldname: 0,
				}
			)
			self.assertRaises(frappe.MandatoryError, practitioner.insert)

	def test_practitioner_service_item(self):
		fieldnames = ["op_consulting_charge", "inpatient_visit_charge"]
		for idx, fieldname in enumerate(fieldnames):
			item_fieldname = f"{fieldname}_item"
			charge_fieldname = f"{fieldname}"
			practitioner = frappe.get_doc(
				{
					"doctype": "Healthcare Practitioner",
					"first_name": f"__Test Healthcare Practitioner {idx}",
					"gender": "Male",
					item_fieldname: "HLC-SI-001",
					charge_fieldname: 0,
				}
			)
			self.assertRaises(frappe.ValidationError, practitioner.insert)
