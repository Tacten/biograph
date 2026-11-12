"""Host page for the ABHA (ABDM M1) React app, served at /abha.

Same origin and login as the Desk: the page needs a signed-in user holding one of the ABDM staff roles, and hands the
app only what it needs to start (CSRF token, the user's name and roles, the optional patient to open, and the
built asset URLs). The app calls the existing whitelisted methods under /api/method/. No ABDM credential, token or
patient data is put in this HTML.
"""

import json
import os
from urllib.parse import quote

import frappe
import frappe.sessions
import frappe.utils
from frappe import _

no_cache = 1

# Roles that may use the app: the same staff roles abha_client._idor_check admits.
_STAFF_ROLES = ("System Manager", "Healthcare Administrator", "Physician", "Nursing User", "Laboratory User")


def get_context(context):
	if frappe.session.user == "Guest":
		# Send the guest to the login form and back to this page (and patient) afterwards.
		patient = (frappe.form_dict.get("patient") or "").strip()
		target = "/abha" + (f"?patient={quote(patient)}" if patient else "")
		frappe.local.flags.redirect_location = f"/login?redirect-to={quote(target, safe='')}"
		raise frappe.Redirect(302)  # temporary: a cached 301 would keep sending a signed-in user to /login

	roles = set(frappe.get_roles(frappe.session.user))
	staff_roles = [r for r in _STAFF_ROLES if r in roles]
	if not staff_roles:
		frappe.throw(_("You do not have permission to use the ABHA app."), frappe.PermissionError)

	context.no_cache = 1
	context.title = _("ABHA")
	context.js_url, context.css_url = _asset_urls()
	context.build_missing = not context.js_url
	context.boot_json = _safe_json(_boot(staff_roles))
	return context


def _boot(staff_roles):
	return {
		"csrf_token": frappe.sessions.get_csrf_token(),
		"user": {
			"name": frappe.session.user,
			"full_name": frappe.utils.get_fullname(frappe.session.user),
			"roles": staff_roles,
		},
		"patient": _requested_patient(),
		"site": frappe.local.site,
	}


def _requested_patient():
	"""The patient named in ?patient=, only when it exists and this user may read it."""
	name = (frappe.form_dict.get("patient") or "").strip()
	if not name or not frappe.db.exists("Patient", name):
		return None
	if not frappe.has_permission("Patient", "read", name):
		return None
	return {"name": name, "patient_name": frappe.db.get_value("Patient", name, "patient_name") or name}


def _asset_urls():
	"""URLs of the built bundle, with ?v=<mtime> so a rebuild is picked up. (None, None) if it was not built."""
	folder = frappe.get_app_path("healthcare", "public", "abha-ui", "assets")
	urls = {}
	for kind, filename in (("js", "abha-ui.js"), ("css", "abha-ui.css")):
		path = os.path.join(folder, filename)
		if os.path.exists(path):
			urls[kind] = f"/assets/healthcare/abha-ui/assets/{filename}?v={int(os.path.getmtime(path))}"
	return urls.get("js"), urls.get("css")


def _safe_json(data):
	"""JSON that is safe inside a <script type="application/json"> element: no raw <, > or & can close the tag."""
	return json.dumps(data).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
