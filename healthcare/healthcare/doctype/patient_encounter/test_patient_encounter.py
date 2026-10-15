# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt


import frappe
from frappe.tests import IntegrationTestCase

from healthcare.healthcare.doctype.patient_appointment.test_patient_appointment import (
	create_appointment_type,
)
from healthcare.healthcare.doctype.patient_encounter.patient_encounter import (
	PatientEncounter,
	get_medications_query,
)


class TestPatientEncounter(IntegrationTestCase):
	def setUp(self):
		try:
			gender_m = frappe.get_doc({"doctype": "Gender", "gender": "MALE"}).insert()
			gender_f = frappe.get_doc({"doctype": "Gender", "gender": "FEMALE"}).insert()
		except frappe.exceptions.DuplicateEntryError:
			gender_m = frappe.get_doc({"doctype": "Gender", "gender": "MALE"})
			gender_f = frappe.get_doc({"doctype": "Gender", "gender": "FEMALE"})

		self.patient_male = frappe.get_doc(
			{
				"doctype": "Patient",
				"first_name": "John",
				"sex": gender_m.gender,
			}
		).insert()
		self.patient_female = frappe.get_doc(
			{
				"doctype": "Patient",
				"first_name": "Curie",
				"sex": gender_f.gender,
			}
		).insert()
		self.practitioner = frappe.get_doc(
			{
				"doctype": "Healthcare Practitioner",
				"first_name": "Doc",
				"sex": "MALE",
			}
		).insert()
		try:
			self.care_plan_male = frappe.get_doc(
				{
					"doctype": "Treatment Plan Template",
					"template_name": "test plan - m",
					"gender": gender_m.gender,
				}
			).insert()
			self.care_plan_female = frappe.get_doc(
				{
					"doctype": "Treatment Plan Template",
					"template_name": "test plan - f",
					"gender": gender_f.gender,
				}
			).insert()
		except frappe.exceptions.DuplicateEntryError:
			self.care_plan_male = frappe.get_doc(
				{
					"doctype": "Treatment Plan Template",
					"template_name": "test plan - m",
					"gender": gender_m.gender,
				}
			)
			self.care_plan_female = frappe.get_doc(
				{
					"doctype": "Treatment Plan Template",
					"template_name": "test plan - f",
					"gender": gender_f.gender,
				}
			)

	def test_treatment_plan_template_filter(self):
		encounter = frappe.get_doc(
			{
				"doctype": "Patient Encounter",
				"patient": self.patient_male.name,
				"practitioner": self.practitioner.name,
				"appointment_type": create_appointment_type().name,
			}
		).insert()
		plans = PatientEncounter.get_applicable_treatment_plans(encounter.as_dict())
		self.assertEqual(plans[0]["name"], self.care_plan_male.template_name)

		encounter = frappe.get_doc(
			{
				"doctype": "Patient Encounter",
				"patient": self.patient_female.name,
				"practitioner": self.practitioner.name,
				"appointment_type": create_appointment_type().name,
			}
		).insert()
		plans = PatientEncounter.get_applicable_treatment_plans(encounter.as_dict())
		self.assertEqual(plans[0]["name"], self.care_plan_female.template_name)

	def test_get_medications_query(self):
		medication = frappe.db.get_value("Medication", {"generic_name": "Paracetamol"})
		if not medication:
			self.skipTest("Paracetamol medication fixture not found")
		item = frappe.db.get_value("Medication Linked Item", {"parent": medication}, "item")

		results = get_medications_query("Item", None, "name", 0, 20, {"medication": medication})
		self.assertIn(item, [row[0] for row in results])

	def test_get_medications_query_filters_by_search_text(self):
		medication = frappe.db.get_value("Medication", {"generic_name": "Paracetamol"})
		if not medication:
			self.skipTest("Paracetamol medication fixture not found")
		filters = {"medication": medication}

		self.assertTrue(get_medications_query("Item", "Paracetamol", "name", 0, 20, filters))
		self.assertFalse(get_medications_query("Item", "no such item", "name", 0, 20, filters))

	def test_get_medications_query_shows_stock_in_company_warehouse(self):
		medication = frappe.db.get_value("Medication", {"generic_name": "Paracetamol"})
		if not medication:
			self.skipTest("Paracetamol medication fixture not found")
		company = frappe.db.get_value("Company", {}, "name")
		warehouse = frappe.get_cached_value("Company", company, "default_warehouse")
		if not warehouse:
			self.skipTest("No default warehouse set on company")

		results = get_medications_query(
			"Item", None, "name", 0, 20, {"medication": medication, "company": company}
		)
		self.assertTrue(any("Actual Qty" in str(column) for column in results[0]))
