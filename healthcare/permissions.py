import frappe
from frappe import _


def check_permission(doc, ptype, user):
	if ptype != "delete":
		return None
	if "System Manager" in frappe.get_roles(user):
		return None
	frappe.throw(
		_("You do not have permission to delete records."),
		frappe.PermissionError,
	)
