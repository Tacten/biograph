import frappe

from healthcare.healthcare.doctype.insurance_claim.insurance_claim import update_claim_paid_amount


@frappe.whitelist()
def manage_payment_entry_submit_cancel(doc, method):
	"""Handle payment entry submit/cancel for insurance claims and treatment counselling."""
	if doc.treatment_counselling and doc.paid_amount:
		on_cancel = True if method == "on_cancel" else False
		validate_treatment_counselling(doc, on_cancel)

	update_claim_paid_amount(doc, method)


def validate_treatment_counselling(doc, on_cancel=False):
	"""Update Treatment Counselling paid and outstanding amounts."""
	treatment_counselling_doc = frappe.get_doc("Treatment Counselling", doc.treatment_counselling)

	paid_amount = treatment_counselling_doc.paid_amount + doc.paid_amount
	if on_cancel:
		paid_amount = treatment_counselling_doc.paid_amount - doc.paid_amount

	treatment_counselling_doc.paid_amount = paid_amount
	treatment_counselling_doc.outstanding_amount = (
		treatment_counselling_doc.amount - treatment_counselling_doc.paid_amount
	)
	treatment_counselling_doc.save()


@frappe.whitelist()
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
