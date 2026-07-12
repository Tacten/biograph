"""
Workarounds for upstream Frappe bugs that affect this site.

Registered via:
  override_whitelisted_methods  — thin API shims
  override_doctype_class        — subclass patches for DocType controllers

Each patch should be removed once the upstream fix lands in the Frappe version
pinned by this project.
"""
import frappe


# ---------------------------------------------------------------------------
# Frappe v16 bug: AuditTrail.get_amended_documents() queries 'amended_from'
# on every doctype, but non-amendable doctypes (Patient, ABHA Record, etc.)
# don't have that column — causing MySQLdb.OperationalError (1054) on every
# Audit Trail view for those documents.
#
# Fix: check meta before querying; for non-amendable doctypes return just the
# single document name (there is no amendment chain to walk).
#
# Track: remove once Frappe guards the query with a meta.has_field() check.
# ---------------------------------------------------------------------------
from frappe.core.doctype.audit_trail.audit_trail import AuditTrail as _AuditTrail


class SafeAuditTrail(_AuditTrail):
	def get_amended_documents(self):
		meta = frappe.get_meta(self.doctype_name)
		if not meta.has_field("amended_from"):
			# Non-amendable doctype: only one version exists, no chain to walk.
			return [self.document]
		return super().get_amended_documents()


@frappe.whitelist()
def safe_get_list_settings(doctype: str | None = None):
	"""
	Frappe v16 bug: get_list_settings() is called without `doctype` by the
	desk JS on certain list navigations, causing a TypeError that floods the
	Error Log.  This shim makes `doctype` optional and returns None (the same
	as the "no settings found" path) when it is absent.

	Track: https://github.com/frappe/frappe/issues — remove once fixed upstream.
	"""
	if not doctype:
		return None
	try:
		return frappe.get_cached_doc("List View Settings", doctype)
	except frappe.DoesNotExistError:
		frappe.clear_messages()
		return None
