# -*- coding: utf-8 -*-
# Copyright (c) 2020, earthians and Contributors
# See license.txt
from __future__ import unicode_literals

import unittest

import frappe
from frappe.utils import getdate, nowtime

import erpnext

from healthcare.healthcare.doctype.clinical_procedure.test_clinical_procedure import (
	create_procedure,
)
from healthcare.healthcare.doctype.healthcare_settings.healthcare_settings import (
	get_income_account,
	get_receivable_account,
)
from healthcare.healthcare.doctype.lab_test.test_lab_test import (
	create_lab_test,
	create_lab_test_template,
)
from healthcare.healthcare.api.patient_portal import get_data_from_service_requests
from healthcare.healthcare.doctype.observation.observation import (
	get_root_observations,
	set_diagnostic_report_status,
	update_diagnostic_report_status,
)
from healthcare.healthcare.doctype.observation_template.test_observation_template import (
	create_observation_template,
)
from healthcare.healthcare.doctype.patient_appointment.test_patient_appointment import (
	create_appointment_type,
	create_clinical_procedure_template,
	create_healthcare_docs,
	create_patient,
	create_practitioner,
)
from healthcare.healthcare.doctype.patient_encounter.patient_encounter import (
	create_patient_referral,
)
from healthcare.healthcare.doctype.service_request.service_request import (
	make_appointment,
	make_clinical_procedure,
	make_observation,
)
from healthcare.tests.utils import HealthcareTestSuite

WITH_SAMPLE = "_Test Observation with Sample"
WITHOUT_SAMPLE = "_Test Observation without Sample"
OPERAND_2 = "_Test Observation Operand 2"
GROUPED_WITH_SAMPLE = "_Test Observation Grouped with Sample"
RT_PCR = "_Test COVID RT PCR"


class TestServiceRequest(unittest.TestCase):
	def test_creation_on_encounter_submission(self):
		patient, practitioner = create_healthcare_docs()
		insulin_resistance_template = create_lab_test_template()
		procedure_template = create_clinical_procedure_template()
		procedure_template.allow_stock_consumption = 1
		encounter = create_encounter(
			patient,
			practitioner,
			"lab_test_prescription",
			insulin_resistance_template,
			procedure_template,
			submit=True,
		)
		self.assertTrue(frappe.db.exists("Service Request", {"order_group": encounter.name}))
		service_request = frappe.db.get_all(
			"Service Request", {"order_group": encounter.name}, ["name", "template_dt"]
		)
		if service_request:
			for serv in service_request:
				service_request_doc = frappe.get_doc("Service Request", serv.get("name"))
				service_request_doc.submit()
				if serv.get("name"):
					if serv.get("template_dt") == "Lab Test Template":
						template = insulin_resistance_template
						type = "lab_test_prescription"
						doc = "Lab Test"
						test = create_lab_test(template)
						test.service_request = serv.get("name")
						test.descriptive_test_items[0].result_value = 1
						test.descriptive_test_items[1].result_value = 2
						test.descriptive_test_items[2].result_value = 3
						test.submit()
					elif serv.get("template_dt") == "Clinical Procedure Template":
						test = make_clinical_procedure(service_request_doc)
						test.submit()
						doc = "Clinical Procedure"
						template = procedure_template
						type = "procedure_prescription"

					# create sales invoice with service request and check service request and lab test is marked as invoiced
					create_sales_invoice(patient, service_request_doc, template, type)
					self.assertEqual(
						frappe.db.get_value("Service Request", serv.get("name"), "billing_status"), "Invoiced"
					)
					self.assertEqual(
						frappe.db.get_value("Service Request", serv.get("name"), "status"),
						"completed-Request Status",
					)
					self.assertTrue(frappe.db.get_value(doc, test.name, "invoiced"))

	def test_creation_on_encounter_with_create_order_on_save_checked(self):
		patient, practitioner = create_healthcare_docs()
		insulin_resistance_template = create_lab_test_template()
		encounter = create_encounter(
			patient, practitioner, "lab_test_prescription", insulin_resistance_template
		)
		encounter.submit_orders_on_save = True
		encounter.save()
		self.assertTrue(frappe.db.exists("Service Request", {"order_group": encounter.name}))
		encounter.submit()

		# to check if submit creates order
		self.assertEqual(
			frappe.db.count(
				"Service Request",
				filters={"order_group": encounter.name},
			),
			1,
		)

	def test_mark_observation_as_invoiced(self):
		obs_template = create_observation_template("Total Cholesterol")
		patient, practitioner = create_healthcare_docs()
		encounter = create_encounter(
			patient, practitioner, "lab_test_prescription", obs_template, submit=True, obs=True
		)
		service_request = frappe.db.get_value("Service Request", {"order_group": encounter.name}, "name")
		if service_request:
			service_request_doc = frappe.get_doc("Service Request", service_request)
			observation = create_observation(patient, service_request, obs_template.name)
			create_sales_invoice(patient, service_request_doc, obs_template, "observation")
			self.assertEqual(frappe.db.get_value("Observation", observation.name, "invoiced"), 1)

	def test_patient_referral(self):
		patient = create_patient()
		practitioner_1 = create_practitioner(id=1)
		practitioner_2 = create_practitioner(id=2)
		obs_template = create_observation_template("Total Cholesterol")
		encounter = create_encounter(
			patient, practitioner_1, "lab_test_prescription", obs_template, submit=True, obs=True
		)

		appointment_type = create_appointment_type()
		refer_to_practitioner(encounter, practitioner_2, appointment_type.name)

		self.assertTrue(
			frappe.db.exists(
				"Service Request",
				{
					"order_group": encounter.name,
					"template_dt": "Appointment Type",
					"template_dn": appointment_type.name,
				},
			)
		)

		self.assertEqual(
			frappe.db.get_value(
				"Service Request",
				{
					"order_group": encounter.name,
					"template_dt": "Appointment Type",
					"template_dn": appointment_type.name,
				},
				"referred_to_practitioner",
			),
			practitioner_2,
		)

	def test_make_appointment_from_service_request_does_not_copy_order_source(self):
		patient = frappe.get_list("Patient", pluck="name", order_by="name asc")[0]
		practitioners = frappe.get_list("Healthcare Practitioner", pluck="name", order_by="name asc", limit=2)
		referring_practitioner, referred_practitioner = practitioners
		appointment_type = frappe.get_doc("Appointment Type", "_Test Appointment Type with Items")
		referred_practitioner_name = frappe.db.get_value(
			"Healthcare Practitioner", referred_practitioner, "practitioner_name"
		)
		service_request = frappe.get_doc(
			{
				"doctype": "Service Request",
				"order_date": getdate(),
				"order_time": nowtime(),
				"company": "_Test Company",
				"patient": patient,
				"practitioner": referring_practitioner,
				"source": "Direct",
				"template_dt": "Appointment Type",
				"template_dn": appointment_type.name,
				"referred_to_practitioner": referred_practitioner,
				"quantity": 1,
			}
		).insert(ignore_permissions=True)

		appointment = make_appointment(service_request.name)

		self.assertEqual(appointment.service_request, service_request.name)
		self.assertEqual(appointment.practitioner, referred_practitioner)
		self.assertEqual(appointment.practitioner_name, referred_practitioner_name)
		self.assertFalse(appointment.source)

	def test_make_appointment_without_referred_practitioner_returns_draft(self):
		patient = frappe.get_list("Patient", pluck="name", order_by="name asc")[0]
		practitioner = frappe.get_list("Healthcare Practitioner", pluck="name", order_by="name asc")[0]
		appointment_type = frappe.get_doc("Appointment Type", "_Test Appointment Type with Items")
		service_request = frappe.get_doc(
			{
				"doctype": "Service Request",
				"order_date": getdate(),
				"order_time": nowtime(),
				"company": "_Test Company",
				"patient": patient,
				"practitioner": practitioner,
				"source": "Direct",
				"template_dt": "Appointment Type",
				"template_dn": appointment_type.name,
				"quantity": 1,
			}
		).insert(ignore_permissions=True)

		appointment = make_appointment(service_request.name)

		self.assertEqual(appointment.service_request, service_request.name)
		self.assertFalse(appointment.source)


class TestServiceRequestObservation(HealthcareTestSuite):
	"""make_observation for several tests ordered in one Patient Encounter"""

	def setUp(self):
		frappe.db.set_single_value("Healthcare Settings", "process_service_request_only_if_paid", 0)
		self.patient = frappe.get_list("Patient", pluck="name")[0]

	def test_second_test_of_an_encounter_gets_its_own_observation(self):
		encounter, service_requests = create_encounter_with_observations(
			self.patient, [WITHOUT_SAMPLE, RT_PCR]
		)
		make_observation(service_requests[WITHOUT_SAMPLE])
		first_observation = get_root_observation(service_requests[WITHOUT_SAMPLE])
		frappe.db.set_value("Observation", first_observation, "result", "5")
		first_before = frappe.db.get_value(
			"Observation", first_observation, ["name", "result", "status"], as_dict=True
		)

		response = make_observation(service_requests[RT_PCR])

		self.assertTrue(get_root_observation(service_requests[RT_PCR]))
		diagnostic_report = get_encounter_report(self, encounter)
		self.assertEqual(response[0], diagnostic_report)
		self.assertFalse(response[2])
		self.assertEqual(response[3], diagnostic_report)
		self.assertEqual(
			frappe.db.get_value("Observation", first_observation, ["name", "result", "status"], as_dict=True),
			first_before,
		)
		self.assertEqual(
			{obs.service_request for obs in get_root_observations(diagnostic_report)},
			set(service_requests.values()),
		)

	def test_three_tests_in_reverse_order_share_one_report(self):
		templates = [WITHOUT_SAMPLE, RT_PCR, OPERAND_2]
		encounter, service_requests = create_encounter_with_observations(self.patient, templates)

		for template in reversed(templates):
			make_observation(service_requests[template])

		for service_request in service_requests.values():
			self.assertEqual(count_root_observations(service_request), 1)
		diagnostic_report = get_encounter_report(self, encounter)
		self.assertEqual(len(get_root_observations(diagnostic_report)), 3)

	def test_sample_and_non_sample_tests_share_one_report(self):
		encounter, service_requests = create_encounter_with_observations(
			self.patient, [WITHOUT_SAMPLE, WITH_SAMPLE]
		)

		make_observation(service_requests[WITHOUT_SAMPLE])
		diagnostic_report = get_encounter_report(self, encounter)
		self.assertFalse(frappe.db.get_value("Diagnostic Report", diagnostic_report, "sample_collection"))

		sample_collection, doctype = make_observation(service_requests[WITH_SAMPLE])[:2]

		self.assertEqual(doctype, "Sample Collection")
		self.assertTrue(
			frappe.db.exists(
				"Observation Sample Collection",
				{"parent": sample_collection, "service_request": service_requests[WITH_SAMPLE]},
			)
		)
		self.assertEqual(get_encounter_report(self, encounter), diagnostic_report)
		self.assertEqual(
			frappe.db.get_value("Diagnostic Report", diagnostic_report, "sample_collection"),
			sample_collection,
		)
		self.assertEqual(count_root_observations(service_requests[WITHOUT_SAMPLE]), 1)

	def test_repeat_make_observation_is_idempotent(self):
		encounter, service_requests = create_encounter_with_observations(
			self.patient, [WITHOUT_SAMPLE, WITH_SAMPLE]
		)
		make_observation(service_requests[WITHOUT_SAMPLE])
		sample_collection = make_observation(service_requests[WITH_SAMPLE])[0]
		diagnostic_report = get_encounter_report(self, encounter)
		observation_count = frappe.db.count("Observation", {"reference_docname": encounter.name})
		sample_row_count = frappe.db.count("Observation Sample Collection", {"parent": sample_collection})

		self.assertEqual(
			make_observation(service_requests[WITHOUT_SAMPLE]),
			(diagnostic_report, "Diagnostic Report", "New"),
		)
		self.assertEqual(
			make_observation(service_requests[WITH_SAMPLE]),
			(sample_collection, "Sample Collection", "New"),
		)

		self.assertEqual(
			frappe.db.count("Observation", {"reference_docname": encounter.name}), observation_count
		)
		self.assertEqual(
			frappe.db.count("Observation Sample Collection", {"parent": sample_collection}),
			sample_row_count,
		)
		get_encounter_report(self, encounter)

	def test_approved_report_reopens_when_it_gains_a_test(self):
		encounter, service_requests = create_encounter_with_observations(
			self.patient, [WITHOUT_SAMPLE, RT_PCR]
		)
		make_observation(service_requests[WITHOUT_SAMPLE])
		diagnostic_report = get_encounter_report(self, encounter)
		first_observation = get_root_observation(service_requests[WITHOUT_SAMPLE])
		frappe.db.set_value(
			"Observation", first_observation, {"result": "5", "status": "Approved", "docstatus": 1}
		)
		update_diagnostic_report_status(diagnostic_report)
		self.assertEqual(frappe.db.get_value("Diagnostic Report", diagnostic_report, "status"), "Approved")

		make_observation(service_requests[RT_PCR])

		self.assertEqual(
			frappe.db.get_value("Diagnostic Report", diagnostic_report, "status"), "Partially Approved"
		)


class TestEncounterReportMode(HealthcareTestSuite):
	"""Patient Encounter.consolidate_diagnostic_report: one combined report, or one per test"""

	def setUp(self):
		frappe.db.set_single_value("Healthcare Settings", "process_service_request_only_if_paid", 0)
		self.patient = frappe.get_list("Patient", pluck="name")[0]

	def test_new_encounter_consolidates_by_default(self):
		self.assertEqual(frappe.new_doc("Patient Encounter").consolidate_diagnostic_report, 1)

	def test_separate_mode_gives_each_test_its_own_report(self):
		encounter, service_requests = create_encounter_with_observations(
			self.patient, [WITHOUT_SAMPLE, RT_PCR], consolidate=0
		)

		for service_request in service_requests.values():
			response = make_observation(service_request)
			report = get_test_report(self, service_request)
			self.assertEqual(response, (report, "Diagnostic Report"))
			self.assertEqual(
				[obs.service_request for obs in get_root_observations(report)], [service_request]
			)

		reports = frappe.get_all(
			"Diagnostic Report", {"docname": encounter.name, "docstatus": ["!=", 2]}, pluck="name"
		)
		self.assertEqual(len(reports), 2)

		# Again for the same test: the same report, nothing new
		report = get_test_report(self, service_requests[RT_PCR])
		self.assertEqual(make_observation(service_requests[RT_PCR]), (report, "Diagnostic Report", "New"))
		self.assertEqual(frappe.db.count("Diagnostic Report", {"docname": encounter.name}), 2)
		self.assertEqual(count_root_observations(service_requests[RT_PCR]), 1)

	def test_separate_mode_sets_sample_collection_only_for_sample_tests(self):
		encounter, service_requests = create_encounter_with_observations(
			self.patient, [WITHOUT_SAMPLE, WITH_SAMPLE], consolidate=0
		)

		make_observation(service_requests[WITHOUT_SAMPLE])
		sample_collection, doctype = make_observation(service_requests[WITH_SAMPLE])[:2]

		self.assertEqual(doctype, "Sample Collection")
		self.assertFalse(
			frappe.db.get_value(
				"Diagnostic Report",
				get_test_report(self, service_requests[WITHOUT_SAMPLE]),
				"sample_collection",
			)
		)
		self.assertEqual(
			frappe.db.get_value(
				"Diagnostic Report", get_test_report(self, service_requests[WITH_SAMPLE]), "sample_collection"
			),
			sample_collection,
		)

	def test_approving_one_test_leaves_other_separate_reports_alone(self):
		encounter, service_requests = create_encounter_with_observations(
			self.patient, [WITHOUT_SAMPLE, RT_PCR], consolidate=0
		)
		for service_request in service_requests.values():
			make_observation(service_request)
		approved_report = get_test_report(self, service_requests[WITHOUT_SAMPLE])
		other_report = get_test_report(self, service_requests[RT_PCR])

		observation = get_root_observation(service_requests[WITHOUT_SAMPLE])
		frappe.db.set_value("Observation", observation, {"result": "5", "status": "Approved", "docstatus": 1})
		set_diagnostic_report_status(frappe.get_doc("Observation", observation))

		self.assertEqual(frappe.db.get_value("Diagnostic Report", approved_report, "status"), "Approved")
		self.assertEqual(frappe.db.get_value("Diagnostic Report", other_report, "status"), "Open")

	def test_cancelling_sample_collection_deletes_every_linked_report(self):
		encounter, service_requests = create_encounter_with_observations(
			self.patient, [WITH_SAMPLE, GROUPED_WITH_SAMPLE], consolidate=0
		)
		sample_collection = make_observation(service_requests[WITH_SAMPLE])[0]
		self.assertEqual(make_observation(service_requests[GROUPED_WITH_SAMPLE])[0], sample_collection)
		self.assertEqual(frappe.db.count("Diagnostic Report", {"sample_collection": sample_collection}), 2)

		sample_collection_doc = frappe.get_doc("Sample Collection", sample_collection)
		sample_collection_doc.submit()
		sample_collection_doc.cancel()

		self.assertEqual(frappe.db.count("Diagnostic Report", {"sample_collection": sample_collection}), 0)

	def test_choice_is_locked_once_a_report_exists(self):
		encounter, service_requests = create_encounter_with_observations(
			self.patient, [WITHOUT_SAMPLE, RT_PCR]
		)

		# No report yet: the submitted encounter can still switch mode
		encounter.reload()
		encounter.consolidate_diagnostic_report = 0
		encounter.save()
		encounter.reload()
		encounter.consolidate_diagnostic_report = 1
		encounter.save()

		make_observation(service_requests[WITHOUT_SAMPLE])
		encounter.reload()
		encounter.run_method("onload")
		self.assertTrue(encounter.get_onload().get("has_diagnostic_report"))
		encounter.consolidate_diagnostic_report = 0
		self.assertRaises(frappe.ValidationError, encounter.save)
		self.assertEqual(
			frappe.db.get_value("Patient Encounter", encounter.name, "consolidate_diagnostic_report"), 1
		)

	def test_patient_portal_joins_each_test_to_its_own_report(self):
		for consolidate in (0, 1):
			encounter, service_requests = create_encounter_with_observations(
				self.patient, [WITHOUT_SAMPLE, RT_PCR], consolidate=consolidate
			)
			for service_request in service_requests.values():
				make_observation(service_request)

			rows = [
				row
				for row in get_data_from_service_requests([self.patient])
				if row.order_name == encounter.name
			]
			self.assertEqual(sorted(row.service_request for row in rows), sorted(service_requests.values()))
			for row in rows:
				if consolidate:
					expected = get_encounter_report(self, encounter)
				else:
					expected = get_test_report(self, row.service_request)
				self.assertEqual(row.diagnostic_report, expected)


def create_encounter(
	patient, practitioner, type, template, procedure_template=False, submit=False, obs=False
):
	patient_encounter = frappe.new_doc("Patient Encounter")
	patient_encounter.patient = patient
	patient_encounter.practitioner = practitioner
	patient_encounter.encounter_date = getdate()
	patient_encounter.encounter_time = nowtime()
	if not obs:
		if type == "lab_test_prescription":
			patient_encounter.append(
				type, {"lab_test_code": template.item, "lab_test_name": template.lab_test_name}
			)
		elif type == "drug_prescription":
			patient_encounter.append(
				type, {"medication": template.name, "drug_code": template.linked_items[0].get("item")}
			)
	else:
		patient_encounter.append(type, {"observation_template": template.name})

	if procedure_template:
		patient_encounter.append(
			"procedure_prescription",
			{"procedure": procedure_template.template, "procedure_name": procedure_template.item_code},
		)

	if submit:
		patient_encounter.submit()
	else:
		patient_encounter.save()

	return patient_encounter


def create_sales_invoice(patient, service_request, template, type):
	sales_invoice = frappe.new_doc("Sales Invoice")
	sales_invoice.patient = patient
	sales_invoice.customer = frappe.db.get_value("Patient", patient, "customer")
	sales_invoice.due_date = getdate()
	sales_invoice.currency = "INR"
	sales_invoice.company = "_Test Company"
	sales_invoice.debit_to = get_receivable_account("_Test Company")
	if type == "lab_test_prescription":
		sales_invoice.append(
			"items",
			{
				"qty": 1,
				"uom": "Nos",
				"conversion_factor": 1,
				"income_account": get_income_account(None, "_Test Company"),
				"rate": template.lab_test_rate,
				"amount": template.lab_test_rate,
				"reference_dt": service_request.doctype,
				"reference_dn": service_request.name,
				"cost_center": erpnext.get_default_cost_center("_Test Company"),
				"item_code": template.item,
				"item_name": template.lab_test_name,
				"description": template.lab_test_description,
			},
		)
	elif type == "drug_prescription":
		sales_invoice.append(
			"items",
			{
				"qty": 1,
				"uom": "Nos",
				"conversion_factor": 1,
				"income_account": get_income_account(None, "_Test Company"),
				"reference_dt": service_request.doctype,
				"reference_dn": service_request.name,
				"cost_center": erpnext.get_default_cost_center("_Test Company"),
				"item_name": template.name,
				"description": template.name,
			},
		)
	elif type in ["observation", "procedure_prescription"]:
		sales_invoice.append(
			"items",
			{
				"qty": 1,
				"uom": "Nos",
				"conversion_factor": 1,
				"income_account": get_income_account(None, "_Test Company"),
				"rate": template.rate,
				"amount": template.rate,
				"reference_dt": service_request.doctype,
				"reference_dn": service_request.name,
				"cost_center": erpnext.get_default_cost_center("_Test Company"),
				"item_code": template.item,
				"item_name": template.item_code,
				"description": template.description,
			},
		)

	sales_invoice.set_missing_values()

	sales_invoice.submit()
	return sales_invoice


def create_observation(patient, service_request, obs_template):
	observation = frappe.new_doc("Observation")
	observation.patient = patient
	observation.service_request = service_request
	observation.observation_template = obs_template
	observation.insert()
	return observation


def refer_to_practitioner(encounter, practitioner=None, appointment_type=None):
	if not practitioner:
		return

	if not appointment_type:
		return

	references = [
		{
			"refer_to": practitioner,
			"appointment_type": appointment_type,
			"referral_note": f"Patient {encounter.patient} referred to practitioner {practitioner}",
		}
	]

	create_patient_referral(encounter.name, references)


def create_encounter_with_observations(patient, observation_templates, consolidate=1):
	patient_encounter = frappe.new_doc("Patient Encounter")
	patient_encounter.consolidate_diagnostic_report = consolidate
	patient_encounter.patient = patient
	patient_encounter.company = "_Test Company"
	patient_encounter.practitioner = frappe.get_list("Healthcare Practitioner", pluck="name")[0]
	patient_encounter.appointment_type = "_Test Appointment Type"
	patient_encounter.encounter_date = getdate()
	patient_encounter.encounter_time = nowtime()
	for template in observation_templates:
		patient_encounter.append("lab_test_prescription", {"observation_template": template})
	patient_encounter.submit()

	service_requests = {
		template: frappe.db.get_value(
			"Service Request", {"order_group": patient_encounter.name, "template_dn": template}
		)
		for template in observation_templates
	}
	return patient_encounter, service_requests


def get_root_observation(service_request):
	return frappe.db.get_value(
		"Observation", {"service_request": service_request, "parent_observation": ["is", "not set"]}
	)


def count_root_observations(service_request):
	return frappe.db.count(
		"Observation", {"service_request": service_request, "parent_observation": ["is", "not set"]}
	)


def get_encounter_report(test_case, encounter):
	reports = frappe.get_all(
		"Diagnostic Report", {"docname": encounter.name, "docstatus": ["!=", 2]}, pluck="name"
	)
	test_case.assertEqual(len(reports), 1)
	return reports[0]


def get_test_report(test_case, service_request):
	reports = frappe.get_all(
		"Diagnostic Report",
		{"service_request": service_request, "docstatus": ["!=", 2]},
		pluck="name",
	)
	test_case.assertEqual(len(reports), 1)
	return reports[0]
