# Copyright (c) 2026, Frappe ABDM and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ABDMConsent(Document):
	"""One agreement to the ABDM terms, with who recorded it, when, and the exact wording and version shown.

	Rows are created by healthcare.regional.india.abdm.api.consent.record_consent; moved here from the frappe_abdm app
	when the ABDM code was consolidated into healthcare.
	"""

	pass
