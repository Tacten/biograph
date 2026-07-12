"""
Consolidates the standalone frappe_abdm app's ABDM V3 implementation into
this app's native regional/india/abdm module, reclaiming the "ABDM Settings"
name from the old gateway-era doctype and retiring "ABDM Request" (superseded
by ABDM Audit Log + ABDM Token Registry).

On a site that never ran the old native code, both old tables are already
absent and this is a no-op. On a site that did run it, this guards against
silent data loss: if either old doctype's table still holds real rows, this
patch raises rather than let schema sync silently reshape or drop that data
out from under the site. Export the data, then re-run migrate.

Row counts are read via raw SQL rather than frappe.db.count(), since that
API requires DocType metadata to exist — but a site mid-cleanup can have an
orphaned physical table with no metadata row (metadata already deleted,
table not yet dropped). A harmless empty orphan table is dropped outright.
"""
import frappe


def execute():
	_guard_old_settings()
	_guard_old_request()
	frappe.logger("abdm").info(
		"ABDM consolidation: 'ABDM Settings' reclaimed as the ABHA V3 Single "
		"doctype, 'ABDM Request' retired in favour of ABDM Audit Log / "
		"ABDM Token Registry."
	)


def _row_count(doctype: str) -> int:
	return frappe.db.sql(f"SELECT COUNT(*) FROM `tab{doctype}`")[0][0]


def _guard_old_settings():
	"""The old native 'ABDM Settings' was a multi-record doctype
	(gateway_name/company); the consolidated one is a Single. If the old
	table still has rows, letting schema sync take over the name would
	destroy them."""
	if not frappe.db.table_exists("ABDM Settings"):
		return
	is_single = frappe.db.get_value("DocType", "ABDM Settings", "issingle")
	if is_single:
		return  # already the consolidated shape — nothing to guard
	count = _row_count("ABDM Settings")
	if count:
		frappe.throw(
			f"{count} row(s) found in the old multi-record 'ABDM Settings' "
			"doctype. This migrate replaces it with a new Single-type doctype "
			"of the same name, which would destroy that data. Export it first, "
			"then re-run migrate."
		)
	if not frappe.db.exists("DocType", "ABDM Settings"):
		# Orphan table: metadata already gone, table empty — safe to drop.
		frappe.db.sql("DROP TABLE IF EXISTS `tabABDM Settings`")


def _guard_old_request():
	if not frappe.db.table_exists("ABDM Request"):
		return
	count = _row_count("ABDM Request")
	if count:
		frappe.throw(
			f"{count} row(s) found in the old 'ABDM Request' doctype, which "
			"this migrate retires (superseded by ABDM Audit Log + ABDM Token "
			"Registry). Export it first, then re-run migrate."
		)
	if not frappe.db.exists("DocType", "ABDM Request"):
		frappe.db.sql("DROP TABLE IF EXISTS `tabABDM Request`")
