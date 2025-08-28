import frappe
from erpnext.accounts.doctype.sales_invoice.sales_invoice import SalesInvoice
import json
from erpnext.stock.get_item_details import get_item_details


@frappe.whitelist()
def set_healthcare_services(self, checked_values):
    self = json.loads(self)
    # load actual Sales Invoice (or whatever doctype you're working with)
    self = frappe.get_doc(self)

    checked_values = json.loads(checked_values)

    for checked_item in checked_values:
        # set practitioner if not already set
        if not self.ref_practitioner:
            self.ref_practitioner = checked_item.get("practitioner")

        # create new child row in items table
        item_line = self.append("items", {})

        # get default price list
        price_list, price_list_currency = frappe.db.get_value(
            "Price List", {"selling": 1}, ["name", "currency"]
        )

        args = {
            "doctype": "Sales Invoice",
            "item_code": checked_item.get("item"),
            "company": self.company,
            "customer": frappe.db.get_value("Patient", self.patient, "customer"),
            "selling_price_list": price_list,
            "price_list_currency": price_list_currency,
            "plc_conversion_rate": 1.0,
            "conversion_rate": 1.0,
        }

        item_details = get_item_details(args)

        # set child row values
        item_line.item_code = checked_item.get("item")
        item_line.qty = checked_item.get("qty") or 1
        item_line.rate = checked_item.get("rate") or item_details.price_list_rate
        item_line.amount = float(item_line.rate) * float(item_line.qty)

        if checked_item.get("income_account"):
            item_line.income_account = checked_item.get("income_account")
        if checked_item.get("dt"):
            item_line.reference_dt = checked_item.get("dt")
        if checked_item.get("dn"):
            item_line.reference_dn = checked_item.get("dn")
        if checked_item.get("description"):
            item_line.description = checked_item.get("description")

        # if lab test, fetch extra fields
        if checked_item.get("dt") == "Lab Test":
            lab_test = frappe.get_doc("Lab Test", checked_item.get("dn"))
            item_line.service_unit = lab_test.service_unit
            item_line.practitioner = lab_test.practitioner
            item_line.medical_department = lab_test.department

    # fill defaults & save
    self.set_missing_values(for_validate=True)

    return self
