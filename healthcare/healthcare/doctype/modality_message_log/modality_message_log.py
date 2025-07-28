# Copyright (c) 2025, earthians Health Informatics Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ModalityMessageLog(Document):
	pass


def log_modality_message(
	ae_title,
	message_type,
	request_payload=None,
	response_payload=None,
	status_code=None,
	status_text=None,
	modality_type=None,
	reference=None,
):
	try:
		frappe.get_doc(
			{
				"doctype": "Modality Message Log",
				"ae_title": ae_title,
				"message_type": message_type,
				"modality_type": modality_type,
				"status_code": status_code,
				"status_text": status_text,
				"reference": reference,
				"timestamp": frappe.utils.now(),
				"request_payload": frappe.as_json(request_payload, indent=2) if request_payload else None,
				"response_payload": frappe.as_json(response_payload, indent=2) if response_payload else None,
			}
		).insert(ignore_permissions=True)
	except Exception as e:
		frappe.log_error(f"Modality log failed: {e}", "Modality Message Logger")
