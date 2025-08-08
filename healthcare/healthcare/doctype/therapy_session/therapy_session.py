# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


import datetime

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc
from frappe.utils import flt, get_link_to_form, get_time, getdate, today, nowdate, nowtime

from erpnext.stock.get_item_details import get_item_details
from erpnext.stock.stock_ledger import get_previous_sle

from healthcare.healthcare.doctype.healthcare_settings.healthcare_settings import (
	get_income_account,
	get_receivable_account,
	get_account
)
from healthcare.healthcare.doctype.nursing_task.nursing_task import NursingTask
from healthcare.healthcare.doctype.service_request.service_request import (
	update_service_request_status,
)
from healthcare.healthcare.utils import validate_nursing_tasks


class TherapySession(Document):
	def validate(self):
		self.set_exercises_from_therapy_type()
		self.validate_duplicate()
		self.set_total_counts()
		if self.consume_stock:
			self.set_actual_qty()

		if self.items:
			self.invoice_separately_as_consumables = False
			for item in self.items:
				if item.invoice_separately_as_consumables:
					self.invoice_separately_as_consumables = True

		if(self.therapy_plan):
			therapy_plan = frappe.get_doc("Therapy Plan", self.therapy_plan)
			for row in therapy_plan.therapy_plan_details:
				if row.therapy_type == self.therapy_type:
					if row.no_of_sessions == row.sessions_completed:
						frappe.throw("Maximum number of sessions {0} already created for this Therapy Plan.".format(row.sessions_completed))
	def after_insert(self):
		if self.service_request:
			update_service_request_status(
				self.service_request, self.doctype, self.name, "completed-Request Status"
			)

		self.create_nursing_tasks(post_event=False)

	def on_update(self):
		if self.appointment:
			frappe.db.set_value("Patient Appointment", self.appointment, "status", "Closed")

	def on_cancel(self):
		if self.appointment:
			frappe.db.set_value("Patient Appointment", self.appointment, "status", "Open")
		if self.service_request:
			frappe.db.set_value("Service Request", self.service_request, "status", "active-Request Status")

		self.update_sessions_count_in_therapy_plan(on_cancel=True)

	def validate_duplicate(self):
		end_time = datetime.datetime.combine(
			getdate(self.start_date), get_time(self.start_time)
		) + datetime.timedelta(minutes=flt(self.duration))

		overlaps = frappe.db.sql(
			"""
		select
			name
		from
			`tabTherapy Session`
		where
			start_date=%s and name!=%s and docstatus!=2
			and (practitioner=%s or patient=%s) and
			((start_time<%s and start_time + INTERVAL duration MINUTE>%s) or
			(start_time>%s and start_time<%s) or
			(start_time=%s))
		""",
			(
				self.start_date,
				self.name,
				self.practitioner,
				self.patient,
				self.start_time,
				end_time.time(),
				self.start_time,
				end_time.time(),
				self.start_time,
			),
		)

		if overlaps:
			overlapping_details = _("Therapy Session overlaps with {0}").format(
				get_link_to_form("Therapy Session", overlaps[0][0])
			)
			frappe.throw(overlapping_details, title=_("Therapy Sessions Overlapping"))

	def on_submit(self):
		validate_nursing_tasks(self)
		self.update_sessions_count_in_therapy_plan()

		if self.service_request:
			frappe.db.set_value("Service Request", self.service_request, "status", "Completed")

	def create_nursing_tasks(self, post_event=True):
		template = frappe.db.get_value("Therapy Type", self.therapy_type, "nursing_checklist_template")
		if template:
			NursingTask.create_nursing_tasks_from_template(
				template,
				self,
				start_time=frappe.utils.get_datetime(f"{self.start_date} {self.start_time}"),
				post_event=post_event,
			)

	def update_sessions_count_in_therapy_plan(self, on_cancel=False):
		therapy_plan = frappe.get_doc("Therapy Plan", self.therapy_plan)
		for entry in therapy_plan.therapy_plan_details:
			if entry.therapy_type == self.therapy_type:
				if on_cancel:
					entry.sessions_completed -= 1
				else:
					entry.sessions_completed += 1
		therapy_plan.save()

	def set_total_counts(self):
		target_total = 0
		counts_completed = 0
		for entry in self.exercises:
			if entry.counts_target:
				target_total += entry.counts_target
			if entry.counts_completed:
				counts_completed += entry.counts_completed

		self.db_set("total_counts_targeted", target_total)
		self.db_set("total_counts_completed", counts_completed)

	def set_exercises_from_therapy_type(self):
		if self.therapy_type and not self.exercises:
			therapy_type_doc = frappe.get_cached_doc("Therapy Type", self.therapy_type)
			if therapy_type_doc.exercises:
				for exercise in therapy_type_doc.exercises:
					self.append(
						"exercises",
						(frappe.copy_doc(exercise)).as_dict(),
					)

	def before_insert(self):
		if self.consume_stock:
			self.set_actual_qty()

		if self.service_request:
			therapy_session = frappe.db.exists(
				"Therapy Session",
				{"service_request": self.service_request, "docstatus": ["!=", 2]},
			)
			if therapy_session:
				frappe.throw(
					_("Therapy Session {0} already created from service request {1}").format(
						frappe.bold(get_link_to_form("Therapy Session", therapy_session)),
						frappe.bold(get_link_to_form("Service Request", self.service_request)),
					),
					title=_("Already Exist"),
				)

	@frappe.whitelist()
	def consume_stocks(self):
		if self.consume_stock and self.items:
			stock_entry = make_stock_entry(self)

		if self.items:
			consumable_total_amount = 0
			consumption_details = False
			customer = frappe.db.get_value("Patient", self.patient, "customer")
			if customer:
				for item in self.items:
					if item.invoice_separately_as_consumables:
						price_list, price_list_currency = frappe.db.get_values(
							"Price List", {"selling": 1}, ["name", "currency"]
						)[0]
						args = {
							"doctype": "Sales Invoice",
							"item_code": item.item_code,
							"company": self.company,
							"warehouse": self.warehouse,
							"customer": customer,
							"selling_price_list": price_list,
							"price_list_currency": price_list_currency,
							"plc_conversion_rate": 1.0,
							"conversion_rate": 1.0,
						}
						item_details = get_item_details(args)
						item_price = item_details.price_list_rate * item.qty
						item_consumption_details = (
							item_details.item_name + " " + str(item.qty) + " " + item.uom + " " + str(item_price)
						)
						consumable_total_amount += item_price
						if not consumption_details:
							consumption_details = _("Therapy Session ({0}):").format(self.name)
						consumption_details += "\n\t" + item_consumption_details

				if consumable_total_amount > 0:
					frappe.db.set_value(
						"Therapy Session", self.name, "consumable_total_amount", consumable_total_amount
					)
					frappe.db.set_value(
						"Therapy Session", self.name, "consumption_details", consumption_details
					)
			else:
				frappe.throw(
					_("Please set Customer in Patient {0}").format(frappe.bold(self.patient)),
					title=_("Customer Not Found"),
				)
		self.update_consumption_status("Consumption Completed")

		if self.consume_stock and self.items:
			return stock_entry

	@frappe.whitelist()
	def check_item_stock(self):
		allow_start = self.set_actual_qty()

		if allow_start:
			return "success"

		return "insufficient stock"

	def set_actual_qty(self):
		allow_negative_stock = frappe.db.get_single_value("Stock Settings", "allow_negative_stock")

		allow_start = True
		for d in self.get("items"):
			d.actual_qty = get_stock_qty(d.item_code, self.warehouse)
			# validate qty
			if not allow_negative_stock and d.actual_qty < d.qty:
				allow_start = False
				break

		return allow_start

	@frappe.whitelist()
	def make_material_receipt(self, submit=False):
		stock_entry = frappe.new_doc("Stock Entry")

		stock_entry.stock_entry_type = "Material Receipt"
		stock_entry.to_warehouse = self.warehouse
		stock_entry.company = self.company
		expense_account = get_account(None, "expense_account", "Healthcare Settings", self.company)
		for item in self.items:
			if item.qty > item.actual_qty:
				se_child = stock_entry.append("items")
				se_child.item_code = item.item_code
				se_child.item_name = item.item_name
				se_child.uom = item.uom
				se_child.stock_uom = item.stock_uom
				se_child.qty = flt(item.qty - item.actual_qty)
				se_child.t_warehouse = self.warehouse
				# in stock uom
				se_child.transfer_qty = flt(item.transfer_qty)
				se_child.conversion_factor = flt(item.conversion_factor)
				cost_center = frappe.get_cached_value("Company", self.company, "cost_center")
				se_child.cost_center = cost_center
				se_child.expense_account = expense_account
		if submit:
			stock_entry.submit()
			return stock_entry
		return stock_entry.as_dict()
	
	@frappe.whitelist()
	def update_consumption_status(self, status):
		"""
		Update the consumption status of the therapy session.
		:param status: New status to set for the consumption.
		"""
		if status not in ["Consumption Completed", "Insufficient Stock", "Consumption Pending"]:
			frappe.throw(_("Invalid consumption status: {0}").format(status), title=_("Invalid Status"))
		
		self.db_set("consumption_status", status)


@frappe.whitelist()
def create_therapy_session(source_name, target_doc=None):
	def set_missing_values(source, target):
		therapy_type = frappe.get_doc("Therapy Type", source.therapy_type)
		target.exercises = therapy_type.exercises

	doc = get_mapped_doc(
		"Patient Appointment",
		source_name,
		{
			"Patient Appointment": {
				"doctype": "Therapy Session",
				"field_map": [
					["appointment", "name"],
					["patient", "patient"],
					["patient_age", "patient_age"],
					["gender", "patient_sex"],
					["therapy_type", "therapy_type"],
					["therapy_plan", "therapy_plan"],
					["practitioner", "practitioner"],
					["department", "department"],
					["start_date", "appointment_date"],
					["start_time", "appointment_time"],
					["service_unit", "service_unit"],
					["company", "company"],
					["invoiced", "invoiced"],
				],
			}
		},
		target_doc,
		set_missing_values,
	)

	return doc


@frappe.whitelist()
def invoice_therapy_session(source_name, target_doc=None):
	def set_missing_values(source, target):
		target.customer = frappe.db.get_value("Patient", source.patient, "customer")
		target.due_date = getdate()
		target.debit_to = get_receivable_account(source.company)
		item = target.append("items", {})
		item = get_therapy_item(source, item)
		target.set_missing_values(for_validate=True)

	doc = get_mapped_doc(
		"Therapy Session",
		source_name,
		{
			"Therapy Session": {
				"doctype": "Sales Invoice",
				"field_map": [
					["patient", "patient"],
					["referring_practitioner", "practitioner"],
					["company", "company"],
					["due_date", "start_date"],
				],
			}
		},
		target_doc,
		set_missing_values,
	)

	return doc


def get_therapy_item(therapy, item):
	item.item_code = frappe.db.get_value("Therapy Type", therapy.therapy_type, "item")
	item.description = _("Therapy Session Charges: {0}").format(therapy.practitioner)
	item.income_account = get_income_account(therapy.practitioner, therapy.company)
	item.cost_center = frappe.get_cached_value("Company", therapy.company, "cost_center")
	item.rate = therapy.rate
	item.amount = therapy.rate
	item.qty = 1
	item.reference_dt = "Therapy Session"
	item.reference_dn = therapy.name
	return item


@frappe.whitelist()
def validate_no_of_session(therapy_plan):
	total_sessions, total_sessions_completed, status = frappe.db.get_value('Therapy Plan', therapy_plan, ['total_sessions', 'total_sessions_completed', "status"])
	if (total_sessions == total_sessions_completed) or status == "Completed":
		return True, total_sessions
	return False

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_appointment_query(doctype, txt, searchfield, start, page_len, filters, as_dict=False):
	condition = ''
	if filters.get("therapy_plan"):
		condition += f" AND pa.therapy_plan = '{filters.get('therapy_plan')}'"
	if filters.get("therapy_type"):
		condition += f" AND pat.therapy_type = '{filters.get('therapy_type')}'"
	if txt:
		condition += f" AND ( pa.therapy_plan like '%{txt}%' or pa.name like '%{txt}%' )"
	if filters.get("is_new"):
		condition += f" AND pa.appointment_date >= '{today()}'"
	else:
		condition += f" AND pa.appointment_date >= '{str(getdate(frappe.db.get_value('Therapy Session', filters.get('name'), 'creation')))}'"
	

	data = frappe.db.sql(f"""
					Select pa.name, pa.therapy_plan, pat.therapy_type, pa.patient_name,
					pa.practitioner, pa.practitioner_name, pa.department, pa.appointment_date, pa.appointment_time
					From `tabPatient Appointment` as pa
					Left Join `tabPatient Appointment Therapy` as pat ON pat.parent = pa.name
					Where status in ('Open', 'Scheduled', 'Confirmed') {condition}
	""")

	return data

@frappe.whitelist()
def get_therapy_consumables(therapy_type):
	return get_items("Clinical Procedure Item", therapy_type, "Therapy Type")

def get_items(table, parent, parenttype):
	items = frappe.db.get_all(
		table, filters={"parent": parent, "parenttype": parenttype}, fields=["*"]
	)

	return items

def get_stock_qty(item_code, warehouse):
	return (
		get_previous_sle(
			{
				"item_code": item_code,
				"warehouse": warehouse,
				"posting_date": nowdate(),
				"posting_time": nowtime(),
			}
		).get("qty_after_transaction")
		or 0
	)

@frappe.whitelist()
def make_stock_entry(doc):
	stock_entry = frappe.new_doc("Stock Entry")
	stock_entry = set_stock_items(stock_entry, doc.name, "Therapy Session")
	stock_entry.stock_entry_type = "Material Issue"
	stock_entry.from_warehouse = doc.warehouse
	stock_entry.company = doc.company
	expense_account = get_account(None, "expense_account", "Healthcare Settings", doc.company)

	for item_line in stock_entry.items:
		cost_center = frappe.get_cached_value("Company", doc.company, "cost_center")
		item_line.cost_center = cost_center
		item_line.expense_account = expense_account

	stock_entry.save(ignore_permissions=True)
	stock_entry.submit()
	return stock_entry.name

@frappe.whitelist()
def set_stock_items(doc, stock_detail_parent, parenttype):
	items = get_items("Clinical Procedure Item", stock_detail_parent, parenttype)

	for item in items:
		se_child = doc.append("items")
		se_child.item_code = item.item_code
		se_child.item_name = item.item_name
		se_child.uom = item.uom
		se_child.stock_uom = item.stock_uom
		se_child.qty = flt(item.qty)
		# in stock uom
		se_child.transfer_qty = flt(item.transfer_qty)
		se_child.conversion_factor = flt(item.conversion_factor)
		if item.batch_no:
			se_child.batch_no = item.batch_no
		if parenttype == "Therapy Type":
			se_child.invoice_separately_as_consumables = item.invoice_separately_as_consumables

	return doc
