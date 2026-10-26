# Copyright (c) 2026, earthians Health Informatics Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe


def execute():
	frappe.reload_doc("healthcare", "doctype", "clinical_note")
	if not frappe.db.has_column("Clinical Note", "fdar_focus"):
		frappe.db.updatedb("Clinical Note")
