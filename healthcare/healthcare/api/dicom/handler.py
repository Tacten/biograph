# Copyright (c) 2025, earthians and contributors
# For license information, please see license.txt

import json
import frappe

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
from frappe.website.page_renderers.base_renderer import BaseRenderer
from frappe.website.utils import build_response

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
			uid = path.split("/")[-1]

			if method == "POST" and path.endswith("/claim"):
				return self.handle_claim(uid)

			elif method == "POST" and path.endswith("/cancelrequest"):
				return self.handle_cancel(uid)

			elif method == "POST" and path.endswith("/workitemevent"):
				return self.handle_workitem_event(uid)

			elif method == "PUT":
				return self.handle_update_workitem(uid)

		elif path == "/dicom-web/echo":
			result = get_dicomweb_verification()
			log_modality_message(
				ae_title=frappe.get_request_header("X-AE-TITLE") or "Unknown",
				type="Verification",
				response_payload=result,
				status_code="0000H",
				status_text="DICOMWeb Verification successful",
			)
			return self.respond(200, result)

		elif path == "/dicom-web/conformance":
			result = get_conformance_statement()
			log_modality_message(
				ae_title=frappe.get_request_header("X-AE-TITLE") or "Unknown",
				type="Conformance",
				response_payload=result,
				status_code="0000H",
				status_text="Conformance served successfully",
			)
			return self.respond(200, result)

		return self.respond(404, self.dicom_error("NoSuchObjectInstance", "UPS task not found"))

	def handle_get_workitems(self, filters):
		self.authenticate_request()
		ae_title = frappe.get_request_header("X-AE-TITLE")
		try:
			result = get_ups_tasks(filters=filters)
			log_modality_message(
				ae_title=ae_title,
				type="UPS RS",
				request_payload=filters,
				response_payload=result,
				status_code="0000H",
				status_text="Claim accepted",
			)
			return self.respond(200, result)
		except Exception as e:
			log_modality_message(
				ae_title=ae_title,
				type="UPS Claim",
				request_payload=filters,
				status_code="0110H",
				status_text=str(e),
			)
			return self.respond(400, self.dicom_error("ProcessingFailure", f"UPS-RS failed: {e}"))

	def handle_claim(self, uid):
		self.authenticate_request()
		self.validate_uid(uid)
		ae_title = frappe.get_request_header("X-AE-TITLE")

		try:
			body = json.loads(frappe.request.get_data(as_text=True) or "{}")
			result = process_ups_claim(uid, body, ae_title)

			log_modality_message(
				ae_title=ae_title,
				type="UPS Claim",
				request_payload=body,
				response_payload=result,
				status_code="0000H",
				status_text="Claim accepted",
				reference=uid,
			)
			return self.respond(200, result)
		except Exception as e:
			log_modality_message(
				ae_title=ae_title,
				type="UPS Claim",
				request_payload=body,
				status_code="0110H",
				status_text=str(e),
				reference=uid,
			)
			return self.respond(400, self.dicom_error("ProcessingFailure", f"Claim failed: {e}"))

	def handle_cancel(self, uid):
		self.authenticate_request()
		self.validate_uid(uid)
		ae_title = frappe.get_request_header("X-AE-TITLE")

		try:
			result = cancel_ups(uid, ae_title)
			log_modality_message(
				ae_title=ae_title,
				type="UPS Cancel",
				request_payload=None,
				response_payload=result,
				status_code="0000H",
				status_text="Cancelled",
				reference=uid,
			)
			return self.respond(200, result)
		except Exception as e:
			log_modality_message(
				ae_title=ae_title,
				type="UPS Cancel",
				request_payload=None,
				status_code="0110H",
				status_text=str(e),
				reference=uid,
			)
			return self.respond(400, self.dicom_error("ProcessingFailure", f"Cancel failed: {e}"))

	def handle_workitem_event(self, uid):
		self.authenticate_request()
		self.validate_uid(uid)
		ae_title = frappe.get_request_header("X-AE-TITLE")

		try:
			body = json.loads(frappe.request.get_data(as_text=True) or "{}")
			result = handle_workitem_event(uid, body)

			log_modality_message(
				ae_title=ae_title,
				type="UPS WorkitemEvent",
				request_payload=body,
				response_payload=result,
				status_code="0000H",
				status_text="Workitem updated",
				reference=uid,
			)
			return self.respond(200, result)
		except Exception as e:
			log_modality_message(
				ae_title=ae_title,
				type="UPS WorkitemEvent",
				request_payload=body,
				status_code="0110H",
				status_text=str(e),
				reference=uid,
			)
			return self.respond(400, self.dicom_error("ProcessingFailure", f"Workitem event failed: {e}"))

	def handle_update_workitem(self, uid):
		self.authenticate_request()
		self.validate_uid(uid)
		ae_title = frappe.get_request_header("X-AE-TITLE")

		try:
			body = json.loads(frappe.request.get_data(as_text=True) or "{}")
			result = update_from_modality(uid, body)

			log_modality_message(
				ae_title=ae_title,
				type="UPS Update",
				request_payload=body,
				response_payload=result,
				status_code="0000H",
				status_text="Updated",
				reference=uid,
			)
			return self.respond(200, result)
		except Exception as e:
			log_modality_message(
				ae_title=ae_title,
				type="UPS Update",
				request_payload=body,
				status_code="0110H",
				status_text=str(e),
				reference=uid,
			)
			return self.respond(400, self.dicom_error("ProcessingFailure", f"Update failed: {e}"))


	def respond(self, status, data, content_type="application/json"):
		from werkzeug.wrappers import Response

		return Response(
			response=json.dumps(data, indent=2),
			status=status,
			content_type=content_type,
		)

	def dicom_error(self, code_key, message):
		return {"Status": DICOM_STATUS_CODES.get(code_key, "0110H"), "ErrorComment": message}

	def validate_uid(self, uid):
		if not uid or not isinstance(uid, str) or len(uid.split(".")) < 4:
			frappe.throw("Invalid UPS UID format", title="UPS-RS Error")
		exists = frappe.db.exists("Imaging Appointment", {"ups_instance_uid": uid})
		if not exists:
			frappe.throw("UPS instance not found", title="UPS-RS Error")

	def authenticate_request(self):
		ae_title = frappe.get_request_header("X-AE-TITLE")
		token = frappe.get_request_header("X-AE-TOKEN")

		if not ae_title or not token:
			frappe.throw("Missing AE credentials", title="401 Unauthorized")

		ae = frappe.get_value("DICOMWeb AE", {"ae_title": ae_title, "enabled": 1}, ["name", "token"])
		if not ae or token != ae.token:
			frappe.throw("Unauthorized DICOMWeb AE", title="401 Unauthorized")
