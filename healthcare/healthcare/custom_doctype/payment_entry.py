import frappe

from healthcare.healthcare.doctype.insurance_claim.insurance_claim import update_claim_paid_amount


def manage_payment_entry_submit_cancel(doc, method):
	"""Handle payment entry submit/cancel for insurance claims."""
	update_claim_paid_amount(doc, method)


def set_paid_amount_in_healthcare_docs(doc, method):
	"""Update paid amounts in Treatment Counselling and Package Subscription."""
	if doc.paid_amount:
		on_cancel = True if method == "on_cancel" else False
		if doc.get("treatment_counselling"):
			validate_doc("Treatment Counselling", doc.treatment_counselling, doc.paid_amount, on_cancel)
		if doc.get("package_subscription"):
			validate_doc("Package Subscription", doc.package_subscription, doc.paid_amount, on_cancel)


def validate_doc(doctype, docname, paid_amount, on_cancel=False):
	"""Generic function to update paid and outstanding amounts on healthcare documents."""
	doc = frappe.get_doc(doctype, docname)

	if on_cancel:
		paid_amount = doc.paid_amount - paid_amount
	else:
		paid_amount = doc.paid_amount + paid_amount

	doc.paid_amount = paid_amount
	amount = doc.total_package_amount if doctype == "Package Subscription" else doc.amount

	doc.outstanding_amount = amount - doc.paid_amount
	doc.save()
