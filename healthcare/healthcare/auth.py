import frappe


def set_role_based_home_page(login_manager):
	"""Redirect a user to the first non-empty `home_page` from their roles.

	Frappe's `LoginManager.set_user_info` runs *after* the `on_login` trigger
	and overwrites `frappe.local.response["home_page"]` with `get_home_page()`.
	To survive that, we set `frappe.local.flags.home_page` — which
	`frappe.website.utils.get_home_page` honors as a short-circuit before
	consulting its per-user cache (`frappe.cache.hget("home_page", user)`).
	We also evict that cache so subsequent requests recompute against the
	current Role.home_page values.
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
			home_page = home_page.strip().lstrip("/")
			frappe.local.flags.home_page = home_page
			frappe.local.response["home_page"] = "/" + home_page
			frappe.cache.hdel("home_page", user)
			return
