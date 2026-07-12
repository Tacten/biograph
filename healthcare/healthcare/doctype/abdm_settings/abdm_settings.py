"""
ABDM Settings — Single DocType controller.
Consolidated home for ABDM V3 SOP configuration, replacing the old minimal
gateway-era "ABDM Settings" doctype this app previously shipped (retired as
part of folding the standalone frappe_abdm app into this module).
"""
import frappe
from frappe.model.document import Document


class ABDMSettings(Document):
	def validate(self):
		self._validate_ip_allowlist()

	def _validate_ip_allowlist(self):
		import json
		if not self.abdm_gateway_ip_allowlist:
			return
		try:
			ip_list = json.loads(self.abdm_gateway_ip_allowlist)
			if not isinstance(ip_list, list):
				frappe.throw(frappe._("Gateway IP allowlist must be a JSON array"))
		except json.JSONDecodeError:
			frappe.throw(frappe._("Gateway IP allowlist is not valid JSON"))


def get_settings() -> "ABDMSettings":
	"""Convenience helper — returns the ABDM Settings singleton."""
	return frappe.get_single("ABDM Settings")
