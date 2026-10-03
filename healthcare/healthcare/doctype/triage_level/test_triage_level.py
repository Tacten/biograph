# Copyright (c) 2026, earthians Health Informatics Pvt. Ltd. and Contributors
# See license.txt

import frappe

from healthcare.tests.utils import HealthcareTestSuite


class TestTriageLevel(HealthcareTestSuite):
	def test_default_levels_present(self):
		for level in ("Emergency", "Urgent", "Non-urgent"):
			self.assertTrue(frappe.db.exists("Triage Level", level))
		self.assertTrue(frappe.db.get_value("Triage Level", "Emergency", "color"))

	def test_priority_order(self):
		priorities = frappe.get_all(
			"Triage Level", fields=["priority"], order_by="priority asc", pluck="priority"
		)
		self.assertEqual(priorities, sorted(priorities))
		self.assertEqual(frappe.db.get_value("Triage Level", "Emergency", "priority"), 1)
