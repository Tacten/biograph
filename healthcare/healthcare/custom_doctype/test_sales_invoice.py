import frappe

from healthcare.tests.utils import HealthcareTestSuite


class TestSalesInvoice(HealthcareTestSuite):
	def test_set_healthcare_services_should_preserve_state(self):
		self.load_test_records("Sales Invoice")
		invoice = frappe.copy_doc(self.globalTestRecords["Sales Invoice"][0])

		count = len(invoice.items)
		item = invoice.items[0]
		checked_values = [
			{
				"dt": "Item",
				"dn": item.item_name,
				"item": item.item_code,
				"qty": False,
				"rate": False,
				"income_account": False,
				"description": False,
			}
		]

		invoice.set_healthcare_services(checked_values)
		self.assertEqual(count + 1, len(invoice.items))

		invoice.set_healthcare_services(checked_values)
		self.assertEqual(count + 2, len(invoice.items))
