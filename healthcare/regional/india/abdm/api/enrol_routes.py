"""
The two other ways to create an ABHA: by driving licence (with an operator's approval) and by Aadhaar biometric.

Driving licence (SOP section 4). ABDM answers a document enrolment with an *enrolment number*, not an ABHA: it becomes an
ABHA only after the document is checked. So nothing here creates an ABHA Record or writes an ABHA number to the
Patient. The flow is: the OTP verifies the mobile (enrol.generate_dl_otp / verify_dl_otp), staff collect the details and
the two photographs (`submit_for_approval`), a *second* user with the Healthcare Administrator or System Manager role
looks at them and decides (`decide`); only an approval is sent to ABDM. The photographs and details are held encrypted or
private until the decision and deleted straight after.

Aadhaar biometric (SOP section 11.2, a Benefit API). Needs a Benefit name in ABDM Settings and a registered fingerprint
device on the desk; it is switched on in ABDM Settings. UNTESTED against ABDM: see AbhaClient.enrol_by_biometric.

Nothing sensitive (PID block, Aadhaar, document photographs, details) is logged.
"""

import base64
import json
import re
from datetime import date

import frappe
from frappe.utils import getdate, now_datetime
from frappe.utils.password import get_decrypted_password, set_encrypted_password

from healthcare.regional.india.abdm.api import enrol
from healthcare.regional.india.abdm.utils.abha_client import AbhaClient
from healthcare.regional.india.abdm.utils.audit import audit_log
from healthcare.regional.india.abdm.utils.http_guards import require_post
from healthcare.regional.india.abdm.utils.log_utils import abdm_log
from healthcare.regional.india.abdm.utils.rate_limit import check_otp_send, check_txn_not_consumed, mark_txn_consumed

DOCTYPE = "ABHA Document Enrolment"
APPROVER_ROLES = {"Healthcare Administrator", "System Manager"}
MAX_PHOTO_BYTES = 150 * 1024  # decoded; ABDM rejects larger photographs (confirmed in the sandbox)
_NAME = re.compile(r"^[A-Za-z][A-Za-z .'\-]{0,49}$")
_DL_NUMBER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 /\-]{6,24}$")
_PIN = re.compile(r"^\d{6}$")
_ALLOWED = {"documentId", "firstName", "middleName", "lastName", "dob", "gender", "address", "state", "district", "pinCode"}


def _patient(patient: str, ptype: str = "write") -> str:
	patient = (patient or "").strip()
	if not patient or not frappe.db.exists("Patient", patient):
		frappe.throw(frappe._("Patient not found"), frappe.ValidationError)
	if not frappe.has_permission("Patient", ptype, patient):
		frappe.throw(frappe._("Not permitted"), frappe.PermissionError)
	return patient


def _is_approver() -> bool:
	return bool(APPROVER_ROLES & set(frappe.get_roles(frappe.session.user)))


def _require_approver() -> None:
	if not _is_approver():
		frappe.throw(frappe._("Only a Healthcare Administrator can approve or reject a document enrolment."), frappe.PermissionError)


def _validate_details(raw) -> dict:
	"""The licence details as ABDM wants them, from a whitelist; anything else the browser sent is dropped."""
	try:
		data = json.loads(raw) if isinstance(raw, str) else dict(raw or {})
	except (ValueError, TypeError):
		frappe.throw(frappe._("The document details are not valid."), frappe.ValidationError)
	d = {k: str(v).strip() for k, v in data.items() if k in _ALLOWED and v not in (None, "")}

	if not _DL_NUMBER.match(d.get("documentId", "")):
		frappe.throw(frappe._("Enter the driving licence number as printed (7 to 25 letters and digits)."), frappe.ValidationError)
	if not _NAME.match(d.get("firstName", "")):
		frappe.throw(frappe._("Enter the first name as printed on the licence."), frappe.ValidationError)
	for key in ("middleName", "lastName"):
		if key in d and not _NAME.match(d[key]):
			frappe.throw(frappe._("The {0} has characters that are not allowed.").format(key), frappe.ValidationError)
	if "lastName" not in d:
		frappe.throw(frappe._("Enter the last name as printed on the licence."), frappe.ValidationError)
	if d.get("gender") not in ("M", "F", "O"):
		frappe.throw(frappe._("Choose the gender as printed on the licence."), frappe.ValidationError)
	try:
		dob = getdate(d.get("dob"))
	except Exception:
		frappe.throw(frappe._("Enter the date of birth as YYYY-MM-DD."), frappe.ValidationError)
	if dob >= date.today() or dob.year < 1900:
		frappe.throw(frappe._("The date of birth is not possible."), frappe.ValidationError)
	d["dob"] = dob.isoformat()
	if "pinCode" in d and not _PIN.match(d["pinCode"]):
		frappe.throw(frappe._("The PIN code must be 6 digits."), frappe.ValidationError)
	return d


def _decode_photo(b64: str, label: str) -> bytes:
	"""A JPEG, at most 1 MB, from base64 (a data: prefix is tolerated)."""
	b64 = (b64 or "").split(",", 1)[-1].strip()
	try:
		raw = base64.b64decode(b64, validate=True)
	except Exception:
		frappe.throw(frappe._("The {0} photograph could not be read.").format(label), frappe.ValidationError)
	if not raw.startswith(b"\xff\xd8\xff"):
		frappe.throw(frappe._("The {0} photograph must be a JPEG image.").format(label), frappe.ValidationError)
	if len(raw) > MAX_PHOTO_BYTES:
		frappe.throw(frappe._("The {0} photograph is larger than 150 KB.").format(label), frappe.ValidationError)
	return raw


def _save_private_jpeg(file_name: str, content: bytes, record: str):
	"""A private File attached to the record. Built directly with its content: frappe.utils.file_manager.save_file writes
	the bytes first and the File then re-reads them as text, which breaks JPEG handling when Frappe strips EXIF data."""
	file_doc = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": file_name,
			"attached_to_doctype": DOCTYPE,
			"attached_to_name": record,
			"is_private": 1,
			"content": content,
		}
	)
	file_doc.insert(ignore_permissions=True)
	return file_doc


def _discard_held(name: str) -> None:
	"""Delete the held photographs (the File rows and the files on disk) and clear the encrypted details and transaction."""
	import os

	doc = frappe.get_doc(DOCTYPE, name)
	urls = []
	for field in ("front_photo", "back_photo"):
		url = doc.get(field)
		if url:
			urls.append(url)
			fname = frappe.db.get_value("File", {"file_url": url, "attached_to_name": name}, "name")
			if fname:
				frappe.delete_doc("File", fname, ignore_permissions=True, force=True)
	frappe.db.set_value(DOCTYPE, name, {"front_photo": None, "back_photo": None}, update_modified=False)
	# Frappe shares one file between Files with identical content; make sure nothing is left on disk once no File uses it.
	for url in set(urls):
		if not frappe.db.exists("File", {"file_url": url}):
			try:
				os.remove(frappe.get_site_path(url.lstrip("/")))
			except OSError:
				pass
	for field in ("details", "txn_id"):
		set_encrypted_password(DOCTYPE, name, "", fieldname=field)


# ---------------------------------------------------------------------------
# Driving licence: collect, then a second person decides
# ---------------------------------------------------------------------------

@frappe.whitelist()
@require_post
def request_document_otp(patient: str, consent_name: str, mobile: str = "") -> dict:
	"""enrol.generate_dl_otp, but only once the patient's agreement is on record (the same consent as the Aadhaar route)."""
	patient = _patient(patient)
	from healthcare.regional.india.abdm.api.ui import _check_consent, _ten_digits

	_check_consent(patient, consent_name)
	# The number on the patient record is used when none is given, so nobody is asked for it twice.
	mobile = _ten_digits(mobile) or _ten_digits(frappe.db.get_value("Patient", patient, "mobile"))
	if not mobile:
		frappe.throw(frappe._("Enter the mobile number the OTP should go to."), frappe.ValidationError)
	result = enrol.generate_dl_otp(patient, mobile)
	if result.get("txnId") and frappe.db.exists("DocType", "ABDM Consent"):
		frappe.db.set_value("ABDM Consent", consent_name, {"txn_id": result["txnId"], "auth_method": "Driving Licence"}, update_modified=False)
	return result


@frappe.whitelist()
@require_post
def submit_for_approval(patient: str, txn_id: str, details: str, front_photo: str, back_photo: str) -> dict:
	"""Hold the licence details and photographs for an operator's decision. Nothing is sent to ABDM yet."""
	patient = _patient(patient)
	txn_id = (txn_id or "").strip()
	if not txn_id:
		frappe.throw(frappe._("The mobile has not been verified yet."), frappe.ValidationError)
	enrol._assert_no_existing_abha(patient)
	if frappe.db.exists(DOCTYPE, {"patient": patient, "status": "Awaiting approval"}):
		frappe.throw(frappe._("This patient already has a document enrolment waiting for approval."), frappe.ValidationError)

	clean = _validate_details(details)
	front = _decode_photo(front_photo, "front")
	back = _decode_photo(back_photo, "back")

	doc = frappe.new_doc(DOCTYPE)
	doc.patient = patient
	doc.status = "Awaiting approval"
	doc.document_type = "DRIVING_LICENCE"
	doc.requested_by = frappe.session.user
	doc.requested_at = now_datetime()
	doc.insert(ignore_permissions=True)
	set_encrypted_password(DOCTYPE, doc.name, json.dumps(clean), fieldname="details")
	set_encrypted_password(DOCTYPE, doc.name, txn_id, fieldname="txn_id")
	front_file = _save_private_jpeg(f"{doc.name}-front.jpg", front, doc.name)
	back_file = _save_private_jpeg(f"{doc.name}-back.jpg", back, doc.name)
	frappe.db.set_value(DOCTYPE, doc.name, {"front_photo": front_file.file_url, "back_photo": back_file.file_url}, update_modified=False)
	frappe.db.commit()

	abdm_log("info", f"Document enrolment submitted for approval | record={doc.name}")
	audit_log("ABHA_CREATE", patient=patient, result="SUCCESS")
	return {"name": doc.name, "status": doc.status}


@frappe.whitelist()
@require_post
def get_status(patient: str) -> dict:
	"""The latest document enrolment for this patient, without any held details."""
	patient = _patient(patient, "read")
	row = frappe.db.get_value(
		DOCTYPE,
		{"patient": patient},
		["name", "status", "requested_by", "decided_by", "decision_note", "enrolment_number", "enrolment_state", "result_message", "creation"],
		as_dict=True,
		order_by="creation desc",
	)
	return row or {}


@frappe.whitelist()
@require_post
def list_pending() -> list:
	"""Enrolments waiting for a decision, for approvers. Names and times only: the details come from get_for_review."""
	_require_approver()
	return frappe.get_all(
		DOCTYPE,
		filters={"status": "Awaiting approval"},
		fields=["name", "patient", "patient_name", "requested_by", "requested_at"],
		order_by="requested_at asc",
	)


def _review_guard(name: str):
	_require_approver()
	if not name or not frappe.db.exists(DOCTYPE, name):
		frappe.throw(frappe._("Enrolment record not found"), frappe.ValidationError)
	doc = frappe.get_doc(DOCTYPE, name)
	if doc.status != "Awaiting approval":
		frappe.throw(frappe._("This enrolment has already been decided."), frappe.ValidationError)
	if doc.requested_by == frappe.session.user:
		frappe.throw(frappe._("A second person must approve: the person who collected the documents cannot decide."), frappe.PermissionError)
	return doc


def _photo_b64(doc, field: str) -> str:
	url = doc.get(field)
	fname = frappe.db.get_value("File", {"file_url": url, "attached_to_name": doc.name}, "name") if url else None
	return base64.b64encode(frappe.get_doc("File", fname).get_content()).decode() if fname else ""


@frappe.whitelist()
@require_post
def get_for_review(name: str) -> dict:
	"""The details and the two photographs (base64) for the approver. Held in the response only; never stored elsewhere."""
	doc = _review_guard(name)
	details = json.loads(get_decrypted_password(DOCTYPE, name, "details", raise_exception=False) or "{}")

	audit_log("PROFILE_GET", patient=doc.patient, result="SUCCESS")
	return {
		"name": doc.name,
		"patient": doc.patient,
		"patient_name": doc.patient_name,
		"collected_by": doc.requested_by,
		"details": details,
		"front_photo": _photo_b64(doc, "front_photo"),
		"back_photo": _photo_b64(doc, "back_photo"),
	}


@frappe.whitelist()
@require_post
def decide(name: str, decision: str, note: str = "") -> dict:
	"""Approve (and send to ABDM) or reject. Held photographs and details are deleted either way."""
	doc = _review_guard(name)
	decision = (decision or "").strip().lower()
	if decision not in ("approve", "reject"):
		frappe.throw(frappe._("The decision must be approve or reject."), frappe.ValidationError)
	note = (note or "").strip()[:300]
	if decision == "reject" and not note:
		frappe.throw(frappe._("Say why the documents are rejected."), frappe.ValidationError)

	base = {"decided_by": frappe.session.user, "decided_at": now_datetime(), "decision_note": note}

	if decision == "reject":
		frappe.db.set_value(DOCTYPE, name, {**base, "status": "Rejected"})
		_discard_held(name)
		frappe.db.commit()
		return {"name": name, "status": "Rejected"}

	details = json.loads(get_decrypted_password(DOCTYPE, name, "details", raise_exception=False) or "{}")
	txn_id = get_decrypted_password(DOCTYPE, name, "txn_id", raise_exception=False) or ""
	front, back = (_photo_b64(doc, f) for f in ("front_photo", "back_photo"))
	if not (front and back and details):
		frappe.throw(frappe._("The held documents are missing. Collect them again."), frappe.ValidationError)
	check_txn_not_consumed(txn_id)

	try:
		response = AbhaClient().enrol_by_dl(doc.patient, txn_id, {**details, "frontSidePhoto": front, "backSidePhoto": back})
	except frappe.ValidationError as e:
		# ABDM refused (or the OTP session lapsed): record why, drop the held material, and let the collector start again.
		message = re.sub(r"<[^>]+>", " ", str(e)).strip() or "ABDM refused the request."
		frappe.clear_messages()
		frappe.db.set_value(DOCTYPE, name, {**base, "status": "Failed", "result_message": message[:300]})
		_discard_held(name)
		frappe.db.commit()
		frappe.throw(frappe._("ABDM did not accept the documents: {0}").format(message), frappe.ValidationError)

	profile = (response or {}).get("EnrolProfile") or {}
	mark_txn_consumed(txn_id)
	frappe.db.set_value(
		DOCTYPE,
		name,
		{
			**base,
			"status": "Submitted",
			"enrolment_number": profile.get("enrolmentNumber") or "",
			"enrolment_state": profile.get("enrolmentState") or "",
			"result_message": (response or {}).get("message") or "",
		},
	)
	_discard_held(name)
	frappe.db.commit()
	audit_log("ABHA_CREATE", patient=doc.patient, result="SUCCESS")
	return {"name": name, "status": "Submitted", "enrolment_number": profile.get("enrolmentNumber") or "", "enrolment_state": profile.get("enrolmentState") or ""}


# ---------------------------------------------------------------------------
# Aadhaar biometric (Benefit API; hidden until ABDM Settings enables it)
# ---------------------------------------------------------------------------

def biometric_enabled() -> bool:
	settings = frappe.get_single("ABDM Settings")
	return bool(settings.get("enable_biometric_enrolment") and (settings.get("benefit_name") or "").strip())


@frappe.whitelist()
@require_post
def get_routes() -> dict:
	"""Which creation routes this site offers. Aadhaar OTP and driving licence always; biometric only when configured."""
	return {"aadhaar_otp": True, "driving_licence": True, "biometric": biometric_enabled(), "can_approve": _is_approver()}


@frappe.whitelist()
@require_post
def enrol_by_biometric(patient: str, aadhaar: str, pid: str, consent_name: str, mobile: str = "") -> dict:
	"""Create an ABHA from a fingerprint or iris capture. The PID and the Aadhaar number are passed through, never stored."""
	patient = _patient(patient)
	if not biometric_enabled():
		frappe.throw(frappe._("Aadhaar biometric creation is not switched on for this site."), frappe.ValidationError)

	from healthcare.regional.india.abdm.api.ui import _check_consent

	_check_consent(patient, consent_name)
	digits = enrol._validate_aadhaar(enrol._require(aadhaar, "Aadhaar"))
	pid = (pid or "").strip()
	if not pid or len(pid) > 200_000:
		frappe.throw(frappe._("The fingerprint capture is missing or too large. Scan again."), frappe.ValidationError)
	mobile = re.sub(r"\D", "", mobile or "")
	if mobile and len(mobile) != 10:
		frappe.throw(frappe._("Mobile number must be 10 digits."), frappe.ValidationError)
	enrol._assert_no_existing_abha(patient)
	check_otp_send(patient)  # the same per-patient attempt limit as an OTP request

	try:
		response = AbhaClient().enrol_by_biometric(patient, pid, digits, mobile)
	finally:
		pid = ""  # noqa: F841
		digits = "0" * 12  # noqa: F841

	record = enrol._create_abha_record_from_enrolment(patient, response)
	enrol_txn = response.get("txnId")
	from healthcare.healthcare.doctype.abdm_token_registry.abdm_token_registry import store_t_token, store_x_token

	if enrol_txn:
		store_t_token(patient, enrol_txn)  # the address step needs it
	token = (response.get("tokens") or {}).get("token")
	if token:
		store_x_token(patient, token)
	frappe.db.set_value("ABDM Consent", consent_name, {"txn_id": enrol_txn or "", "auth_method": "Aadhaar Biometric"}, update_modified=False) if frappe.db.exists("DocType", "ABDM Consent") else None
	audit_log("ABHA_CREATE", patient=patient, result="SUCCESS")
	return {"abha_number": record.abha_number, "abha_address": record.abha_address, "status": record.status, "mobile_linked": bool(token), "txnId": enrol_txn}
