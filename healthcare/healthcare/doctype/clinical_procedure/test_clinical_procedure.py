# Copyright (c) 2017, ESS LLP and Contributors
# See license.txt


import frappe

from healthcare.tests.utils import HealthcareTestSuite


class TestClinicalProcedure(HealthcareTestSuite):
	def test_disable_procedure_template_item(self):
		procedure_template = create_clinical_procedure_template()
		self.assertTrue(frappe.db.exists("Item", procedure_template.item))

		procedure_template.disabled = True
		procedure_template.save()
		self.assertEqual(frappe.db.get_value("Item", procedure_template.item, "disabled"), 1)

	def test_consumables(self):
		patient = frappe.get_list("Patient", pluck="name")[0]
		practitioner = frappe.get_list("Healthcare Practitioner", pluck="name")[0]

		procedure_template = frappe.get_list("Clinical Procedure Template", pluck="name")[0]
		procedure_template = frappe.get_doc("Clinical Procedure Template", procedure_template)
		procedure_template.consume_stock = True
		consumable = create_consumable()
		procedure_template.append(
			"items",
			{
				"item_code": consumable.item_code,
				"qty": 1,
				"uom": consumable.stock_uom,
				"stock_uom": consumable.stock_uom,
			},
		)
		procedure_template.save()
		procedure = create_procedure(procedure_template, patient, practitioner)
		result = procedure.start_procedure()
		if result == "insufficient stock":
			procedure.make_material_receipt(submit=True)
			result = procedure.start_procedure()
		self.assertEqual(procedure.status, "In Progress")
		result = procedure.complete_procedure()
		# check consumption
		self.assertTrue(frappe.db.exists("Stock Entry", result))

	def test_start_and_end_time(self):
		# check planned end time is calculated
		# check start and complete sets actual start / end times
		procedure_template = create_clinical_procedure_template()
		procedure_template.default_duration = 3600
		procedure_template.consume_stock = False
		procedure_template.save()

		patient = frappe.get_list("Patient", pluck="name")[0]
		practitioner = frappe.get_list("Healthcare Practitioner", pluck="name")[0]

		procedure = create_procedure(procedure_template, patient, practitioner)
		self.assertTrue(procedure.planned_end_datetime)

		procedure.start_procedure()
		self.assertEqual(procedure.status, "In Progress")
		self.assertTrue(procedure.actual_start_datetime)

		procedure.complete_procedure()
		self.assertEqual(procedure.status, "Completed")
		self.assertTrue(procedure.actual_end_datetime)


def create_consumable():
	if frappe.db.exists("Item", "Syringe"):
		return frappe.get_doc("Item", "Syringe")
	consumable = frappe.new_doc("Item")
	consumable.item_code = "Syringe"
	consumable.item_group = "_Test Item Group"
	consumable.stock_uom = "Nos"
	consumable.valuation_rate = 5.00
	consumable.save()
	return consumable


def create_procedure(procedure_template, patient, practitioner):
	procedure = frappe.new_doc("Clinical Procedure")
	procedure.procedure_template = procedure_template.name
	procedure.patient = patient
	procedure.practitioner = practitioner
	procedure.consume_stock = procedure_template.consume_stock
	procedure.items = procedure_template.items
	procedure.company = "_Test Company"
	procedure.warehouse = "_Test Warehouse - _TC"
	procedure.start_date = frappe.utils.getdate()
	procedure.start_time = frappe.utils.nowtime()
	procedure.submit()
	return procedure


def create_clinical_procedure_template():
	if frappe.db.exists("Clinical Procedure Template", "Knee Surgery and Rehab"):
		return frappe.get_doc("Clinical Procedure Template", "Knee Surgery and Rehab")

	template = frappe.new_doc("Clinical Procedure Template")
	template.template = "Knee Surgery and Rehab"
	template.item_code = "Knee Surgery and Rehab"
	template.item_group = "Services"
	template.is_billable = 1
	template.description = "Knee Surgery and Rehab"
	template.rate = 50000
	template.save()

	return template
