import frappe


def execute():
	if not frappe.db.has_column("Therapy Plan", "source_doc"):
		return

	plans = frappe.get_all("Therapy Plan", filters={"source_doc": ["is", "not set"]}, pluck="name")
	for plan in plans:
		encounter = frappe.db.get_value("Patient Encounter", {"therapy_plan": plan}, "name")
		if not encounter:
			continue
		frappe.db.set_value(
			"Therapy Plan",
			plan,
			{"source_doc": "Patient Encounter", "order_group": encounter},
			update_modified=False,
		)
