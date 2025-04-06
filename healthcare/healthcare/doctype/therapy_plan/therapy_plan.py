# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


import frappe
from frappe.model.document import Document
from frappe.utils import flt, today
import json
from healthcare.healthcare.utils import validate_nursing_tasks
from erpnext.stock.get_item_details import get_item_details, get_pos_profile
from frappe.model.mapper import get_mapped_doc


class TherapyPlan(Document):
	def validate(self):
		self.set_totals()
		self.set_status()
		
	def after_insert(self):
		get_invoiced_details(self)
	
	def on_update(self):
		get_invoiced_details(self)
	def on_submit(self):
		validate_nursing_tasks(self)

	def set_status(self):
		if not self.total_sessions_completed:
			self.status = "Not Started"
		else:
			if self.total_sessions_completed < self.total_sessions:
				self.status = "In Progress"
			elif self.total_sessions_completed == self.total_sessions:
				self.status = "Completed"

	def set_totals(self):
		total_sessions = 0
		total_sessions_completed = 0
		for entry in self.therapy_plan_details:
			if entry.no_of_sessions:
				total_sessions += entry.no_of_sessions
			if entry.sessions_completed:
				total_sessions_completed += entry.sessions_completed

		self.db_set("total_sessions", total_sessions)
		self.db_set("total_sessions_completed", total_sessions_completed)

		# for billing details
		total_charges = 0
		for row in self.therapy_plan_details:
			doc = frappe.get_doc("Therapy Type", row.therapy_type)
			if doc.is_billable:
				no_of_sessions = row.no_of_sessions  or 0
				total_charges += doc.rate * no_of_sessions
		self.total_plan_amount = total_charges

		invoices = frappe.db.sql(f"""
				Select si.name, si.grand_total
				From `tabSales Invoice` as si
				Left Join `tabSales Invoice Item` as sii ON sii.parent = si.name
				Where sii.reference_dt = "Therapy Plan" and sii.reference_dn =  '{self.name}'
				Group by si.name
		""" , as_dict = 1)

		paid_amount = 0
		for row in invoices:
			paid_amount += row.grand_total
		self.invoiced_amount = paid_amount

	@frappe.whitelist()
	def set_therapy_details_from_template(self):
		# Add therapy types in the child table
		self.set("therapy_plan_details", [])
		therapy_plan_template = frappe.get_doc("Therapy Plan Template", self.therapy_plan_template)

		for data in therapy_plan_template.therapy_types:
			self.append(
				"therapy_plan_details",
				{"therapy_type": data.therapy_type, "no_of_sessions": data.no_of_sessions},
			)
		return self



@frappe.whitelist()
def get_invoiced_details(self, on_referesh = False):
	if on_referesh:
		self = frappe._dict(json.loads(self))
	
	data = frappe.db.sql(f"""
		Select si.name, si.grand_total, sum(sii.qty) as no_of_session, sii.item_code as service
		From `tabSales Invoice` as si
		Left Join `tabSales Invoice Item` as sii ON sii.parent = si.name
		Where si.docstatus = 1 and sii.reference_dt = 'Therapy Plan' and sii.reference_dn = '{self.name}'
		Group By sii.item_code
	""", as_dict=1)

	total_amount = frappe.db.sql(f"""
		Select si.name, si.grand_total as grand_total
		From `tabSales Invoice` as si
		Left Join `tabSales Invoice Item` as sii ON sii.parent = si.name
		Where si.docstatus = 1 and sii.reference_dt = 'Therapy Plan' and sii.reference_dn = '{self.name}'
		Group By si.name
	""", as_dict=1)

	grand_total = sum([row.grand_total for row in total_amount])

	htmls = """
		<h3>No of Invoiced Therapy Session</h3>
		<table class="table">
			<tr>
				<th>
					<p>Therapy Type</p>
				</th>
				<th>
					<p>No of Session Invoiced</p>
				</th>
			</tr>
		"""
	for row in data:
		htmls += """
				<tr>
					<td>
						{0}
					</td>
					<td>
						{1}
					</td>
				</tr>

		""".format(row.service, row.no_of_session)
	htmls += "</table>"
	no_of_session = sum([row.no_of_session for row in data])
	return  { "html" : htmls , "data" : str(data), "grand_total" : grand_total, "no_of_session" : no_of_session}


@frappe.whitelist()
def get_services_details(self):
	doc = json.loads(self)
	therapy_data  = []

	if doc.get("invoice_json"):
		invoiced_data = eval(doc.get("invoice_json"))

		for row in doc.get('therapy_plan_details'):
			
			session = 0
			for d in invoiced_data:
				if row.get("therapy_type") == d.get("service"):
					session += d.get("no_of_session")

			therapy_data.append({
				"therapy_type" : row.get("therapy_type"),
				"sessions" : row.get("no_of_sessions") - session
			})
	else:
		for row in doc.get('therapy_plan_details'):
			therapy_data.append({
				"therapy_type" : row.get("therapy_type"),
				"sessions" : row.get("no_of_sessions")
			})
	return therapy_data

	
@frappe.whitelist()
def make_therapy_session(therapy_plan, patient, therapy_type, company, appointment=None):
	therapy_type = frappe.get_doc("Therapy Type", therapy_type)

	therapy_session = frappe.new_doc("Therapy Session")
	therapy_session.therapy_plan = therapy_plan
	therapy_session.company = company
	therapy_session.patient = patient
	therapy_session.therapy_type = therapy_type.name
	therapy_session.duration = therapy_type.default_duration
	therapy_session.rate = therapy_type.rate
	if not therapy_session.exercises and therapy_type.exercises:
		for exercise in therapy_type.exercises:
			therapy_session.append(
				"exercises",
				(frappe.copy_doc(exercise)).as_dict(),
			)
	therapy_session.appointment = appointment

	if frappe.flags.in_test:
		therapy_session.start_date = today()
	return therapy_session.as_dict()


@frappe.whitelist()
def make_sales_invoice(reference_name, patient, company, items, therapy_plan_template=None):
	from erpnext.stock.get_item_details import get_item_details

	si = frappe.new_doc("Sales Invoice")
	si.company = company
	si.patient = patient
	si.customer = frappe.db.get_value("Patient", patient, "customer")

	# if therapy_plan_template:
	# 	item = frappe.db.get_value("Therapy Plan Template", therapy_plan_template, "linked_item")
	price_list, price_list_currency = frappe.db.get_values(
		"Price List", {"selling": 1}, ["name", "currency"]
	)[0]
	
	items =  eval(items)

	for row in items:
		args = {
			"doctype": "Sales Invoice",
			"item_code": row.get("therapy_type"),
			"company": company,
			"customer": si.customer,
			"selling_price_list": price_list,
			"price_list_currency": price_list_currency,
			"plc_conversion_rate": 1.0,
			"conversion_rate": 1.0,
		}

		item_details = get_item_details(args)
		si.append("items", {
			"item_code" :row.get("therapy_type"),
			"qty" : row.get("sessions"),
			"rate": item_details.price_list_rate,
			"amount" : flt(item_details.price_list_rate) * flt(row.get("sessions")),
			"reference_dt" : "Therapy Plan",
			"reference_dn" : reference_name,
			"description" : item_details.description
		})
		
	si.set_missing_values(for_validate=True)
	return si

@frappe.whitelist()
def get_invoice_details(therapy_plan):
	invoices = frappe.db.sql(f"""
					Select  sum(si.grand_total) as total_invoiced , sum(si.outstanding_amount) as unpaid_amount, sum(si.grand_total - si.outstanding_amount) as paid_amount
					From `tabSales Invoice` si
					Left Join `tabSales Invoice Item` sii ON sii.parent = si.name
					Where si.docstatus = 1 and sii.reference_dt = 'Therapy Plan' and sii.reference_dn = '{therapy_plan}'
				""", as_dict=1)

	return invoices[0] if invoices else {}

@frappe.whitelist()
def make_patient_appointment(source_name, target_doc=None):
	def set_missing_values(source, target):
		target.appointment_type = "Therapy Session"


	doclist = get_mapped_doc(
		"Therapy Plan",
		source_name,
		{
			"Therapy Plan": {
				"doctype": "Patient Appointment",
				"field_map": {"name" :"therapy_plan" },
			},
			"Therapy Plan Detail" : {
				"doctype" : "Patient Appointment Therapy",
				"field_map": {"custom_default_duration" :"duration" },
			}	
		},
		target_doc,
		set_missing_values,
	)

	return doclist
