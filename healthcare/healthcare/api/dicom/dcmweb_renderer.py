# Copyright (c) 2025, earthians and contributors
# For license information, please see license.txt

import json

from werkzeug.wrappers import Response

import frappe
from frappe.website.page_renderers.base_renderer import BaseRenderer

from healthcare.healthcare.api.dicom.actions import (
	cancel_ups,
	get_ups_tasks,
	handle_workitem_event,
	process_ups_claim,
	update_from_modality,
)
from healthcare.healthcare.api.dicom.capabilities import (
	get_conformance_statement,
	get_dicomweb_verification,
)
from healthcare.healthcare.doctype.modality_message_log.modality_message_log import (
	log_modality_message,
)

DICOM_STATUS_CODES = {
	"Success": "0000H",
	"ProcessingFailure": "0110H",
	"InvalidArgumentValue": "0106H",
	"InvalidAttributeValue": "0107H",
	"MissingAttribute": "0120H",
	"NoSuchObjectInstance": "0112H",
	"UPSAlreadyClaimed": "C301H",
	"UPSNotYetClaimed": "C302H",
	"UPSAlreadyInProgress": "C303H",
	"UPSAlreadyCompleted": "C304H",
}


class DICOMWebRenderer(BaseRenderer):
	def __init__(self, path, http_status_code=None):
		super().__init__(path, http_status_code)

	def can_render(self):
		return self.path.startswith("dicom-web")

	def render(self):
		path = frappe.request.path
		method = frappe.request.method
		path = path.rstrip("/")

		if path == "/dicom-web/workitems":
			if method == "GET":
				filters = frappe.request.args or {}
				return self.handle_get_workitems(filters)
			elif method == "POST":
				try:
					filters = json.loads(frappe.request.get_data(as_text=True) or "{}")
				except Exception:
					return self.respond(400, self.dicom_error("InvalidAttributeValue", "Invalid JSON body"))
				return self.handle_get_workitems(filters)

		elif path.startswith("/dicom-web/workitems/"):
			workitem_id = path.split("/")[-2]

			if method == "POST" and path.endswith("/claim"):
				return self.handle_claim(workitem_id)

			elif method == "POST" and path.endswith("/cancelrequest"):
				return self.handle_cancel(workitem_id)

			elif method == "POST" and path.endswith("/workitemevent"):
				return self.handle_workitem_event(workitem_id)

			elif method == "PUT":
				return self.handle_update_workitem(workitem_id)

		elif path == "/dicom-web/echo":  # no auth
			result = get_dicomweb_verification()
			log_modality_message(
				ae_title=frappe.get_request_header("X-AE-TITLE") or "Unknown",
				message_type="Verification",
				response_payload=result,
				status_code="0000H",
				status_text="DICOMWeb Verification completed successfully",
			)
			return self.respond(200, result)

		elif path == "/dicom-web/conformance":  # no auth
			result = get_conformance_statement()
			log_modality_message(
				ae_title=frappe.get_request_header("X-AE-TITLE") or "Unknown",
				message_type="Conformance",
				response_payload=result,
				status_code="0000H",
				status_text="DICOM Conformance served successfully",
			)
			return self.respond(200, result)

		return self.respond(404, self.dicom_error("NoSuchObjectInstance", "UPS task not found"))

	def handle_get_workitems(self, filters):
		# self.authenticate_request()
		ae_title = frappe.get_request_header("X-AE-TITLE")
		try:
			result = get_ups_tasks(filters=filters)
			log_modality_message(
				ae_title=ae_title,
				message_type="UPS RS",
				request_payload=filters,
				response_payload=result,
				status_code="0000H",
				status_text="UPS RS served",
			)
			return self.respond(200, result)
		except Exception as e:
			log_modality_message(
				ae_title=ae_title,
				message_type="UPS RS",
				request_payload=filters,
				status_code="0110H",
				status_text=str(e),
			)
			return self.respond(400, self.dicom_error("ProcessingFailure", f"UPS-RS failed: {e}"))

	def handle_claim(self, workitem_id):
		# self.authenticate_request()
		ae_title = frappe.get_request_header("X-AE-TITLE")

		try:
			body = json.loads(frappe.request.get_data(as_text=True) or "{}")
			result = process_ups_claim(workitem_id, body, ae_title)

			log_modality_message(
				ae_title=ae_title,
				message_type="UPS Claim",
				request_payload=body,
				response_payload=result,
				status_code="0000H",
				status_text="Claim accepted",
				reference=workitem_id,
			)
			return self.respond(200, result)
		except Exception as e:
			log_modality_message(
				ae_title=ae_title,
				message_type="UPS Claim",
				request_payload=body,
				status_code="0110H",
				status_text=str(e),
				reference=workitem_id,
			)
			return self.respond(400, self.dicom_error("ProcessingFailure", f"Claim failed: {e}"))

	def handle_cancel(self, workitem_id):
		# self.authenticate_request()
		ae_title = frappe.get_request_header("X-AE-TITLE")

		try:
			body = json.loads(frappe.request.get_data(as_text=True) or "{}")
			result = cancel_ups(workitem_id, body, ae_title)
			log_modality_message(
				ae_title=ae_title,
				message_type="UPS Cancel",
				request_payload=None,
				response_payload=result,
				status_code="0000H",
				status_text="Cancelled",
				reference=workitem_id,
			)
			return self.respond(200, result)
		except Exception as e:
			log_modality_message(
				ae_title=ae_title,
				message_type="UPS Cancel",
				request_payload=None,
				status_code="0110H",
				status_text=str(e),
				reference=workitem_id,
			)
			return self.respond(400, self.dicom_error("ProcessingFailure", f"Cancel failed: {e}"))

	def handle_workitem_event(self, workitem_id):
		# self.authenticate_request()
		ae_title = frappe.get_request_header("X-AE-TITLE")

		try:
			body = json.loads(frappe.request.get_data(as_text=True) or "{}")
			result = handle_workitem_event(workitem_id, body, ae_title)

			log_modality_message(
				ae_title=ae_title,
				message_type="UPS WorkitemEvent",
				request_payload=body,
				response_payload=result,
				status_code="0000H",
				status_text="Workitem updated",
				reference=workitem_id,
			)
			return self.respond(200, result)
		except Exception as e:
			log_modality_message(
				ae_title=ae_title,
				message_type="UPS WorkitemEvent",
				request_payload=body,
				status_code="0110H",
				status_text=str(e),
				reference=workitem_id,
			)
			return self.respond(400, self.dicom_error("ProcessingFailure", f"Workitem event failed: {e}"))

	def handle_update_workitem(self, workitem_id):
		# self.authenticate_request()
		ae_title = frappe.get_request_header("X-AE-TITLE")

		try:
			body = json.loads(frappe.request.get_data(as_text=True) or "{}")
			result = update_from_modality(workitem_id, body, ae_title)

			log_modality_message(
				ae_title=ae_title,
				message_type="UPS Update",
				request_payload=body,
				response_payload=result,
				status_code="0000H",
				status_text="Updated",
				reference=workitem_id,
			)
			return self.respond(200, result)
		except Exception as e:
			log_modality_message(
				ae_title=ae_title,
				message_type="UPS Update",
				request_payload=body,
				status_code="0110H",
				status_text=str(e),
				reference=workitem_id,
			)
			return self.respond(400, self.dicom_error("ProcessingFailure", f"Update failed: {e}"))

	def respond(self, status, data, content_type="application/json"):
		return Response(
			response=json.dumps(data, indent=2),
			status=status,
			content_type=content_type,
		)

	def dicom_error(self, code_key, message):
		return {"Status": DICOM_STATUS_CODES.get(code_key, "0110H"), "ErrorComment": message}

	def authenticate_request(self):
		ae_title = frappe.get_request_header("X-AE-TITLE")
		token = frappe.get_request_header("X-AE-TOKEN")

		if not ae_title or not token:
			frappe.throw("Missing AE credentials", title="401 Unauthorized")

		ae = frappe.get_value("DICOMWeb AE", {"ae_title": ae_title, "enabled": 1}, ["name", "token"])
		if not ae or token != ae.token:
			frappe.throw("Unauthorized DICOMWeb AE", title="401 Unauthorized")
