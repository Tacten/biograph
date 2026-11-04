# Copyright (c) 2026, Healthcare contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ABHADocumentEnrolment(Document):
	"""A patient's ABHA creation by an identity document (driving licence), waiting for or past an operator's decision.

	Created and changed only by healthcare.regional.india.abdm.api.enrol_routes. The document details and photographs
	are held (encrypted, private) only until the decision and are deleted afterwards; what stays is who collected and
	who decided, when, and the enrolment number ABDM returned.
	"""

	def on_trash(self):
		# Held photographs and details must never outlive the record.
		for field in ("front_photo", "back_photo"):
			url = self.get(field)
			if url:
				name = frappe.db.get_value("File", {"file_url": url, "attached_to_name": self.name}, "name")
				if name:
					frappe.delete_doc("File", name, ignore_permissions=True, force=True)
