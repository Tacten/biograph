import frappe


def execute():
	"""
	Rebrand Marley Health to Biograph in Desktop Icon and Workspace Sidebar records.

	This patch:
	1. Deletes the old "Marley Health" Desktop Icon record
	2. Updates any Desktop Icons with parent_icon = "Marley Health" to "Biograph"
	3. Deletes any Workspace Sidebar records with old naming
	4. Ensures the new Biograph Desktop Icon exists
	"""
	rebrand_desktop_icons()
	rebrand_workspace_sidebars()
	frappe.db.commit()


def rebrand_desktop_icons():
	"""Handle Desktop Icon rebranding"""
	if not frappe.db.exists("DocType", "Desktop Icon"):
		return

	# Delete old "Marley Health" parent icon if exists
	if frappe.db.exists("Desktop Icon", "Marley Health"):
		frappe.delete_doc("Desktop Icon", "Marley Health", force=True, ignore_permissions=True)
		frappe.db.commit()

	# Update any child icons that still reference "Marley Health" as parent
	frappe.db.sql(
		"""
		UPDATE `tabDesktop Icon`
		SET parent_icon = %s
		WHERE parent_icon = %s
		""",
		("Biograph", "Marley Health"),
	)

	# Delete all healthcare app Desktop Icons to force re-sync from fixtures
	frappe.db.sql(
		"""
		DELETE FROM `tabDesktop Icon`
		WHERE app = %s
		""",
		("healthcare",),
	)


def rebrand_workspace_sidebars():
	"""Handle Workspace Sidebar rebranding"""
	if not frappe.db.exists("DocType", "Workspace Sidebar"):
		return

	# Delete all healthcare module Workspace Sidebars to force re-sync from fixtures
	frappe.db.sql(
		"""
		DELETE FROM `tabWorkspace Sidebar`
		WHERE module = %s
		""",
		("Healthcare",),
	)

	# Also delete child items
	if frappe.db.exists("DocType", "Workspace Sidebar Item"):
		frappe.db.sql(
			"""
			DELETE FROM `tabWorkspace Sidebar Item`
			WHERE parenttype = %s
			AND parent NOT IN (SELECT name FROM `tabWorkspace Sidebar`)
			""",
			("Workspace Sidebar",),
		)
