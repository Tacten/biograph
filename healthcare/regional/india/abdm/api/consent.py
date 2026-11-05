"""
ABDM consent: record the patient's agreement to ABDM's terms before an Aadhaar number is sent.

Moved here from frappe_abdm.abha.api.consent. The wording is ABDM's own text for the `abha-enrollment` consent,
version 1.4 (the version the enrol call declares), stored verbatim with each agreement so the facility can show
exactly what the patient agreed to and when.
"""

import hashlib

import frappe
from frappe.utils import now_datetime

from healthcare.regional.india.abdm.utils.http_guards import require_post

CONSENT_CODE = "abha-enrollment"
CONSENT_VERSION = "1.4"
CONSENT_TITLE = "Terms and Conditions"
CONSENT_TEXT_ABHA_CREATION = (
	"I, hereby declare that I am voluntarily sharing my Aadhaar number and demographic information issued by UIDAI, "
	"with National Health Authority (NHA) for the sole purpose of creation of ABHA number. I understand that my ABHA "
	"number can be used and shared for purposes as may be notified by ABDM from time to time including provision of "
	"healthcare services. Further, I am aware that my personal identifiable information (Name, Address, Age, Date of "
	"Birth, Gender and Photograph) may be made available to the entities working in the National Digital Health "
	"Ecosystem (NDHE) which inter alia includes stakeholders and entities such as healthcare professionals (e.g. "
	"doctors), facilities (e.g. hospitals, laboratories) and data fiduciaries (e.g. health programmes), which are "
	"registered with or linked to the Ayushman Bharat Digital Mission (ABDM), and various processes there under. I "
	"authorize NHA to use my Aadhaar number for performing Aadhaar based authentication with UIDAI as per the "
	"provisions of the Aadhaar (Targeted Delivery of Financial and other Subsidies, Benefits and Services) Act, 2016 "
	"for the aforesaid purpose. I understand that UIDAI will share my e-KYC details, or response of \u201cYes\u201d with "
	"NHA upon successful authentication. I have been duly informed about the option of using other IDs apart from "
	"Aadhaar; however, I consciously choose to use Aadhaar number for the purpose of availing benefits across the "
	"NDHE. I am aware that my personal identifiable information excluding Aadhaar number / VID number can be used and "
	"shared for purposes as mentioned above. I reserve the right to revoke the given consent at any point of time as "
	"per provisions of Aadhaar Act and Regulations."
)
CONSENT_SHA256 = hashlib.sha256(CONSENT_TEXT_ABHA_CREATION.encode("utf-8")).hexdigest()

_ALLOWED_TYPES = {"ABHA Creation", "Scan & Share", "Health Records Access"}


def consent_doctype_ready() -> bool:
	"""True once the ABDM Consent doctype exists on this site (after `bench migrate`)."""
	return bool(frappe.db.exists("DocType", "ABDM Consent"))


@frappe.whitelist()
@require_post
def get_consent_text() -> dict:
	"""The wording that record_consent stores, with its version and hash, so a screen shows exactly what is recorded."""
	return {
		"available": consent_doctype_ready(),
		"title": CONSENT_TITLE,
		"text": CONSENT_TEXT_ABHA_CREATION,
		"code": CONSENT_CODE,
		"version": CONSENT_VERSION,
		"sha256": CONSENT_SHA256,
	}


@frappe.whitelist()
@require_post
def record_consent(
	patient: str,
	consent_type: str = "ABHA Creation",
	source: str = "Registration Desk",
	facility: str = "",
) -> dict:
	"""Record ABDM consent before any OTP is sent. Returns the consent record name."""
	if not patient or not frappe.db.exists("Patient", patient):
		frappe.throw(frappe._("Patient not found"), frappe.ValidationError)
	if not frappe.has_permission("Patient", "write", patient):
		frappe.throw(frappe._("Not permitted"), frappe.PermissionError)
	if consent_type not in _ALLOWED_TYPES:
		frappe.throw(frappe._("Invalid consent type"), frappe.ValidationError)
	if not consent_doctype_ready():
		frappe.throw(
			frappe._("Consent cannot be recorded yet: the ABDM Consent doctype is not on this site. Run bench migrate."),
			frappe.ValidationError,
		)

	ip_address = ""
	if frappe.request:
		ip_address = (
			frappe.request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or frappe.request.remote_addr or ""
		)

	doc = frappe.new_doc("ABDM Consent")
	doc.patient = patient
	doc.consent_type = consent_type
	doc.consent_status = "Granted"
	doc.consent_version = CONSENT_VERSION
	doc.consent_datetime = now_datetime()
	doc.captured_by = frappe.session.user
	doc.facility = facility or ""
	doc.source = source or "Registration Desk"
	doc.consent_text = CONSENT_TEXT_ABHA_CREATION
	doc.ip_address = ip_address
	doc.insert(ignore_permissions=False)
	frappe.db.commit()

	return {"consent_name": doc.name, "consent_version": CONSENT_VERSION, "message": "Consent recorded"}


@frappe.whitelist()
@require_post
def update_consent(consent_name: str, txn_id: str = "", auth_method: str = "") -> dict:
	"""Link a recorded consent to the ABDM transaction and the authentication method, once the OTP has been sent."""
	if not consent_name or not frappe.db.exists("ABDM Consent", consent_name):
		frappe.throw(frappe._("Consent record not found"), frappe.ValidationError)
	if auth_method not in {"Aadhaar OTP", "Mobile OTP", "Driving Licence", "Aadhaar Biometric", ""}:
		frappe.throw(frappe._("Invalid authentication method"), frappe.ValidationError)
	# Only the person who recorded it can link it (prevents tampering by other users).
	if frappe.db.get_value("ABDM Consent", consent_name, "captured_by") != frappe.session.user:
		frappe.throw(frappe._("Not permitted"), frappe.PermissionError)

	update = {}
	if txn_id:
		update["txn_id"] = txn_id
	if auth_method:
		update["auth_method"] = auth_method
	if update:
		frappe.db.set_value("ABDM Consent", consent_name, update)
		frappe.db.commit()
	return {"message": "Consent updated"}
