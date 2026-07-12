"""
M1-T4A: wrapper_client.py — NHA ABDM Wrapper client (localhost:8082).

Covers M2/M3 gateway flows:
- add-patients
- link-carecontexts
- consent-init
- health-information/fetch

IDOR guard on all patient calls.
Reads tokens from ABDM Token Registry.
No PII in logs.
"""
import frappe
import requests

from healthcare.regional.india.abdm.utils.log_utils import abdm_log


class WrapperClient:
	"""
	Client for the NHA ABDM Wrapper running at localhost:8082.
	Used for M2/M3 flows — NOT for M1 direct ABHA V3 calls.
	"""

	TIMEOUT = 15

	def __init__(self):
		self._settings = None

	@property
	def settings(self):
		if self._settings is None:
			self._settings = frappe.get_single("ABDM Settings")
		return self._settings

	@property
	def base_url(self) -> str:
		return (self.settings.wrapper_base_url or "http://localhost:8082").rstrip("/")

	def call_wrapper(
		self,
		endpoint: str,
		payload: dict | None = None,
		method: str = "POST",
		patient: str | None = None,
	) -> dict:
		"""
		Make an authenticated call to the ABDM wrapper.

		:param endpoint: e.g. "/v0.5/patients/link/add-contexts"
		:param payload: Request body
		:param patient: Frappe Patient docname — required for IDOR check
		"""
		if patient:
			self._assert_patient_permission(patient)

		url = f"{self.base_url}{endpoint}"
		headers = self._build_headers(patient)

		try:
			resp = requests.request(
				method, url, json=payload, headers=headers, timeout=self.TIMEOUT
			)
			abdm_log("info", f"Wrapper {method} {endpoint} → {resp.status_code}")
			resp.raise_for_status()
			return resp.json()
		except requests.HTTPError as e:
			self._handle_error(e)
		except requests.ConnectionError:
			frappe.throw(
				frappe._("Cannot connect to ABDM wrapper at {0}. Is it running?").format(self.base_url),
				frappe.ValidationError,
			)
		except requests.Timeout:
			frappe.throw(
				frappe._("ABDM wrapper request timed out. Please try again."),
				frappe.ValidationError,
			)

	def _build_headers(self, patient: str | None) -> dict:
		headers = {"Content-Type": "application/json", "Accept": "application/json"}
		if patient:
			from healthcare.healthcare.doctype.abdm_token_registry.abdm_token_registry import (
				get_or_create_registry,
			)
			reg = get_or_create_registry(patient)
			if reg.gateway_access_token:
				headers["Authorization"] = f"Bearer {reg.get_password('gateway_access_token')}"
		return headers

	def _assert_patient_permission(self, patient: str):
		"""IDOR guard — M1-T4A."""
		if not frappe.has_permission("Patient", doc=patient, ptype="write"):
			frappe.throw(
				frappe._("You do not have permission to perform ABDM operations for this patient"),
				frappe.PermissionError,
			)

	def _handle_error(self, exc: requests.HTTPError):
		try:
			body = exc.response.json()
			msg = body.get("message") or body.get("error", "ABDM wrapper error")
		except Exception:
			msg = "ABDM wrapper request failed"
		abdm_log("error", f"Wrapper error: {exc.response.status_code}")
		frappe.throw(frappe._(msg), frappe.ValidationError)

	# -----------------------------------------------------------------------
	# M2/M3 gateway flows (stubs — implemented in M2)
	# -----------------------------------------------------------------------

	def add_patient(self, patient: str, abha_number: str) -> dict:
		"""M2: Register patient with ABDM gateway."""
		return self.call_wrapper("/v0.5/patients/add", payload={"abhaNumber": abha_number}, patient=patient)

	def link_care_contexts(self, patient: str, care_contexts: list) -> dict:
		"""M2: Link care contexts for a patient."""
		return self.call_wrapper(
			"/v0.5/patients/link/add-contexts",
			payload={"careContexts": care_contexts},
			patient=patient,
		)
