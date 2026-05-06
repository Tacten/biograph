import frappe


def set_role_based_home_page(login_manager):
	"""Redirect a user to the first non-empty `home_page` from their roles.

	Why: admins set per-role landing pages on the Role doctype; this honors
	that value at login time so the redirect stays in sync with the UI
	without any code change.
	How to apply: wired up via the `on_login` hook in hooks.py.
	"""
	user = login_manager.user
	if not user or user in ("Guest", "Administrator"):
		return

	roles = frappe.get_roles(user)
	if not roles:
		return

	for role in roles:
		home_page = frappe.db.get_value("Role", role, "home_page")
		if home_page and home_page.strip():
			frappe.local.response["home_page"] = home_page.strip()
			return
