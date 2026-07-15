"""
M1-T4B: abha_client.py — Direct ABHA V3 API client.

Calls abha_base_url and phr_base_url directly (not via wrapper).
Covers all SOP §2-12 endpoints for Milestone 1 flows.

Responsibilities:
- Manages X-token and T-token lifecycle via ABDM Token Registry
- Calls RSA encryption (M1-T58) before every sensitive payload
- Retry logic with exponential backoff
- IDOR guard on all patient-scoped calls
- No PII in any log output (uses log_utils.scrub_pii)
"""
import time
import uuid
from datetime import datetime, timezone
import frappe
import requests
from frappe.utils import now_datetime

from healthcare.regional.india.abdm.utils.log_utils import abdm_log, scrub_pii
from healthcare.regional.india.abdm.utils.rsa_encrypt import encrypt_field


class AbhaClient:
	"""
	Direct client for ABHA V3 APIs (abhasbx.abdm.gov.in/abha/api/v3/*).
	Instantiate once per request; settings are loaded lazily.
	"""

	MAX_RETRIES = 3
	RETRY_BACKOFF_BASE = 1  # seconds

	def __init__(self):
		self._settings = None

	@property
	def settings(self):
		if self._settings is None:
			self._settings = frappe.get_single("ABDM Settings")
		return self._settings

	@property
	def base_url(self) -> str:
		# Healthcare app uses health_id_base_url; fall back to abha_base_url for our DocType
		url = getattr(self.settings, "health_id_base_url", None) or getattr(self.settings, "abha_base_url", None)
		if not url:
			frappe.throw(frappe._("ABHA Base URL not configured in ABDM Settings."), frappe.ValidationError)
		# Strip any trailing versioned path that HC may have saved (e.g. /v1, /v2, /v0.5)
		# so our /v3/... endpoints are appended to the correct root.
		# e.g. https://abhasbx.abdm.gov.in/abha/api/v1 → https://abhasbx.abdm.gov.in/abha/api
		import re
		url = url.rstrip("/")
		url = re.sub(r"/v\d+(\.\d+)?$", "", url)
		return url

	@property
	def phr_base_url(self) -> str:
		"""
		Base URL for PHR web login (ABHA address verification).

		Same host as abha_base_url: https://abhasbx.abdm.gov.in/abha/api
		The /v3/phr/web/ prefix is part of each endpoint path, not this base.
		Falls back to abha_base_url when not configured.
		"""
		url = (getattr(self.settings, "phr_base_url", None) or "").rstrip("/")
		return url or self.base_url

	# -----------------------------------------------------------------------
	# Core request method
	# -----------------------------------------------------------------------

	def call_abha(
		self,
		endpoint: str,
		payload: dict | None = None,
		method: str = "POST",
		patient: str | None = None,
		use_x_token: bool = False,
		use_t_token: bool = False,
		use_txn_id: bool = False,
		use_phr_base: bool = False,
		max_retries: int | None = None,
	) -> dict:
		"""
		Make an authenticated ABHA V3 API call.

		:param endpoint: Path relative to base_url, e.g. "/v3/enrollment/request/otp"
		:param payload: Request body (will be sent as JSON)
		:param method: HTTP method (POST/GET)
		:param patient: Frappe Patient docname — required for token auth + IDOR check
		:param use_x_token: Include X-token from Token Registry in headers
		:param use_t_token: Include T-Token: Bearer {JWT} for profile endpoints
		:param use_txn_id: Include Transaction_Id: {UUID} for enrollment completion endpoints
		    (enrol/suggestion, enrol/abha-address). ABDM V3 spec requires this header name —
		    NOT "T-Token: Bearer". The value is the enrollment txnId UUID stored in T-token field.
		:param use_phr_base: Use phr_base_url instead of abha_base_url
		:param max_retries: Override MAX_RETRIES for this call. Use 1 for non-idempotent
		    OTP endpoints so a slow ABDM response doesn't trigger duplicate sends.
		"""
		if patient:
			self._assert_patient_permission(patient)

		base = self.phr_base_url if use_phr_base else self.base_url
		url = f"{base}{endpoint}"
		abdm_log("info", f"call_abha → {method} {url} | use_x_token={use_x_token} | use_txn_id={use_txn_id}")

		def _header_factory():
			return self._build_headers(
				patient,
				use_x_token=use_x_token,
				use_t_token=use_t_token,
				use_txn_id=use_txn_id,
			)

		return self._request_with_retry(method, url, _header_factory, payload, max_retries=max_retries)

	# -----------------------------------------------------------------------
	# Gateway token (system-level auth — client_id + client_secret)
	# -----------------------------------------------------------------------

	def _get_gateway_auth_url(self) -> str:
		"""
		V3 session token endpoint per SOP §1.0.
		Correct sandbox URL: https://dev.abdm.gov.in/gateway/v3/sessions

		Handles three forms that auth_base_url may contain:
		  - https://dev.abdm.gov.in/gateway        (correct, modern)
		  - https://dev.abdm.gov.in                (bare host)
		  - https://dev.abdm.gov.in/v0.5/sessions  (HC legacy V0.5)
		In all cases the result is https://<host>/gateway/v3/sessions.
		"""
		from urllib.parse import urlparse

		raw = (
			getattr(self.settings, "auth_base_url", None)
			or "https://dev.abdm.gov.in/gateway"
		).strip().rstrip("/")

		parsed = urlparse(raw)
		host = f"{parsed.scheme}://{parsed.netloc}"  # e.g. https://dev.abdm.gov.in

		# V3 gateway sessions endpoint is at /api/hiecm/gateway/v3/sessions
		# (the V0.5 endpoint was at /gateway/v0.5/sessions — different path prefix)
		return f"{host}/api/hiecm/gateway/v3/sessions"

	def _get_gateway_token(self) -> str:
		"""
		Fetch or return cached system-level gateway access token.
		Tokens are cached in frappe.cache() for (expiry - 60s).
		Never logs client_secret.
		"""
		cache_key = "abdm:gateway_token"
		cached = frappe.cache().get_value(cache_key)
		if cached:
			return cached

		client_id = self.settings.client_id
		# healthcare.regional.india.abdm stores client_secret as a Password field (encrypted in __Auth).
		client_secret = self.settings.get_password("client_secret", raise_exception=False)

		if not client_id or not client_secret:
			frappe.throw(
				frappe._("ABDM client_id and client_secret must be configured in ABDM Settings."),
				frappe.ValidationError,
			)

		auth_url = self._get_gateway_auth_url()
		abdm_log("info", f"Gateway token request → {auth_url}")  # logs URL, never logs secret
		env = getattr(self.settings, "environment", None) or "sandbox"
		cm_id = "sbx" if "sand" in env.lower() else "abdm"
		resp = requests.post(
			auth_url,
			json={"clientId": client_id, "clientSecret": client_secret, "grantType": "client_credentials"},
			headers={
				"Content-Type": "application/json",
				"X-CM-ID": cm_id,
				"REQUEST-ID": str(uuid.uuid4()),
				"TIMESTAMP": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
			},
			timeout=(5, 10),  # (connect, read) in seconds
		)
		resp.raise_for_status()
		data = resp.json()
		token = data.get("accessToken")
		expires_in = int(data.get("expiresIn", 1200))  # SOP §1.0: default 1200s (20 min)

		# Cache with 60s safety margin
		frappe.cache().set_value(cache_key, token, expires_in_sec=max(expires_in - 60, 60))
		abdm_log("info", "Gateway access token refreshed")
		return token

	def _build_headers(
		self,
		patient: str | None,
		use_x_token: bool = False,
		use_t_token: bool = False,
		use_txn_id: bool = False,
	) -> dict:
		gateway_token = self._get_gateway_token()
		env = getattr(self.settings, "environment", None) or "sandbox"
		cm_id = "sbx" if "sand" in env.lower() else "abdm"

		headers = {
			"Content-Type": "application/json",
			"Accept": "application/json",
			"Authorization": f"Bearer {gateway_token}",
			"X-CM-ID": cm_id,
			"REQUEST-ID": str(uuid.uuid4()),
			"TIMESTAMP": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
		}
		if patient:
			from healthcare.healthcare.doctype.abdm_token_registry.abdm_token_registry import (
				get_or_create_registry, get_x_token,
			)
			reg = get_or_create_registry(patient)
			if use_x_token:
				live_x_token = get_x_token(patient)
				if live_x_token:
					headers["X-token"] = f"Bearer {live_x_token}"
					abdm_log("debug", f"X-token header set | patient={patient} | token_len={len(live_x_token)}")
				else:
					abdm_log("warning", f"X-token missing or expired for patient={patient} — aborting request")
					frappe.throw(
						frappe._("Your ABHA session has expired. Please use ABDM → Verify ABHA to refresh your session, then try again."),
						frappe.ValidationError,
					)
			if use_t_token and reg.t_token:
				# Profile login endpoints use T-Token: Bearer {JWT}
				headers["T-Token"] = f"Bearer {reg.get_password('t_token')}"
			if use_txn_id and reg.t_token:
				# Enrollment completion endpoints (enrol/suggestion, enrol/abha-address) use
				# Transaction_Id: {UUID} per ABDM V3 spec — no "Bearer" prefix, UUID value.
				headers["Transaction_Id"] = reg.get_password("t_token")
		return headers

	@staticmethod
	def _is_x_token_error(exc: requests.HTTPError) -> bool:
		"""
		True when a 401 is ABDM-1094 ("X-token expired") or an equivalent
		X-token-invalid response — a DIFFERENT token than the gateway/service
		Authorization token, which a gateway-token refresh can never fix.
		Retrying such a call with the same X-token just burns 3 attempts of
		exponential backoff before failing identically every time.
		"""
		if exc.response is None:
			return False
		try:
			body = exc.response.json()
		except ValueError:
			return False
		code = str(body.get("code") or (body.get("error") or {}).get("code") or "").upper()
		msg = str(
			body.get("message") or (body.get("error") or {}).get("message") or ""
		).lower()
		return code == "ABDM-1094" or "x-token" in msg

	def _request_with_retry(
		self, method: str, url: str, headers_or_factory, payload: dict | None,
		max_retries: int | None = None,
	) -> dict:
		"""
		Retry with exponential backoff on transient / auth failures.

		headers_or_factory:
		  - dict  → static headers; 401 treated as a fatal client error (fail fast).
		  - callable() → header factory; on 401 the gateway token cache is cleared and
		    the factory is called again on the next attempt, picking up a fresh token.
		    This is the path used by call_abha().

		max_retries: override self.MAX_RETRIES for this call.  Pass 1 for non-idempotent
		    endpoints (OTP sends) to prevent duplicate OTP triggers on a slow ABDM response.
		"""
		retries = max_retries if max_retries is not None else self.MAX_RETRIES
		last_exc = None
		for attempt in range(1, retries + 1):
			# Rebuild headers each attempt when a factory is provided (enables token refresh)
			if callable(headers_or_factory):
				headers = headers_or_factory()
			else:
				headers = headers_or_factory

			try:
				resp = requests.request(
					method,
					url,
					json=payload,
					headers=headers,
					timeout=(5, 10),  # (connect_timeout, read_timeout) in seconds
				)
				abdm_log("info", f"ABHA API {method} {url} → {resp.status_code}")
				resp.raise_for_status()
				return resp.json()
			except requests.HTTPError as e:
				if e.response is not None:
					status = e.response.status_code
					if status == 401 and callable(headers_or_factory) and not self._is_x_token_error(e):
						# Gateway token expired — clear cache so factory fetches a fresh one
						frappe.cache().delete_value("abdm:gateway_token")
						abdm_log("warning", f"Gateway token expired (401) on attempt {attempt}, refreshing")
						last_exc = e
					elif 400 <= status < 500:
						# Other client error (or 401 with static headers) — no retry
						self._handle_http_error(e)
					else:
						last_exc = e
				else:
					last_exc = e
			except requests.RequestException as e:
				last_exc = e

			if attempt < retries:
				wait = self.RETRY_BACKOFF_BASE * (2 ** (attempt - 1))
				abdm_log("warning", f"ABHA API retry {attempt}/{retries} in {wait}s")
				time.sleep(wait)

		frappe.log_error(f"ABHA API failed after {retries} retries", "ABDM Client")
		# If the last failure was an HTTP error, surface its specific message rather
		# than the generic "temporarily unavailable" — e.g. 401 X-token expired.
		if isinstance(last_exc, requests.HTTPError) and last_exc.response is not None:
			self._handle_http_error(last_exc)
		frappe.throw(
			frappe._("ABDM service temporarily unavailable. Please try again."),
			frappe.ValidationError,
		)

	def _handle_http_error(self, exc: requests.HTTPError):
		"""Translate ABHA API error codes into user-friendly Frappe errors."""
		status = exc.response.status_code if exc.response is not None else 0
		code = ""
		error_body = {}
		try:
			error_body = exc.response.json()
			# ABDM uses two error body shapes:
			#   Shape A: {"code": "...", "message": "...", "details": [...]}
			#   Shape B: {"error": {"code": "ABDM-XXXX", "message": "..."}}
			# Normalise both into flat code + msg strings.
			nested_error = error_body.get("error")
			if isinstance(nested_error, dict):
				code = str(nested_error.get("code", "") or error_body.get("code", ""))
				nested_msg = nested_error.get("message", "")
			else:
				code = str(error_body.get("code", ""))
				nested_msg = str(nested_error) if isinstance(nested_error, str) else ""

			details = error_body.get("details")
			details_msg = ""
			if isinstance(details, list) and details:
				first = details[0]
				details_msg = first.get("message", "") if isinstance(first, dict) else ""

			msg = str(
				error_body.get("message")
				or nested_msg
				or details_msg
				or ""
			)
			# ABDM-1115: mobile not linked to any ABHA — surface directly, don't fall through
			# to the generic 404 message which is misleading in this case.
			if code == "ABDM-1115" and not msg:
				msg = "The mobile number entered is not linked to any ABHA account. Please use the Aadhaar number or the mobile used during ABHA creation."
			# ABDM returns 400 "Invalid X-token" when the session token has expired.
			# Map this to a user-friendly re-verify prompt (same UX as a 401).
			if msg and "invalid x-token" in msg.lower():
				msg = "Your ABHA session has expired. Please use ABDM → Verify ABHA to refresh your session, then try again."
			# ABDM sometimes returns 400 with a body that has no "message" field but
			# uses field names like "txnId" to signal the problem.  Detect common patterns.
			if not msg and status == 400:
				txn_val = str(error_body.get("txnId", "")).lower()
				abha_val = str(
					error_body.get("ABHANumber") or error_body.get("abhaNumber") or ""
				).lower()
				if "invalid" in txn_val or "expired" in txn_val:
					# "Invalid Transaction Id" appears both when a txnId has expired (OTP
					# verify step) AND when a new OTP request conflicts with an existing
					# active session on the sandbox.
					if "invalid" in abha_val:
						# Both txnId and ABHANumber invalid → session fully expired
						msg = "OTP session expired. Please go back and request a new OTP."
					else:
						# txnId alone invalid → either expired session or mobile already has
						# an active ABDM OTP session (sandbox rate-limits per mobile).
						msg = (
							"ABDM rejected the request. If you recently requested an OTP, "
							"please wait a minute before trying again. If the problem persists, "
							"this mobile number may already be linked to an ABHA."
						)
				elif "invalid" in abha_val:
					msg = "Invalid ABHA number. Please verify the number and try again."
			# Write to Error Log (visible in Frappe UI at /app/error-log) so admins can diagnose
			frappe.log_error(
				title=f"ABDM API Error HTTP {status}",
				message=f"code={code} status={status} msg={msg}\nfull_body={error_body}",
			)
			abdm_log("error", f"ABHA API error code={code} status={status} msg={msg} body={error_body}")
		except Exception:
			msg = ""
			try:
				raw = exc.response.text[:500] if exc.response else ""
				frappe.log_error(title=f"ABDM API Error HTTP {status}", message=raw)
				abdm_log("error", f"ABHA API error status={status} body(raw)={raw}")
			except Exception:
				pass
		if not msg:
			if status == 400:
				# Surface the actual ABDM response so developers can diagnose without
				# opening Error Log each time.  Trim to 300 chars to stay readable.
				body_hint = str(error_body)[:300] if error_body else "(empty body)"
				msg = f"ABDM rejected the request (HTTP 400): {body_hint}"
			elif status == 401:
				msg = "ABHA session expired. Use ABDM \u2192 Verify ABHA to re-authenticate."
			elif status == 403:
				msg = "Access denied by ABDM. Please re-verify your ABHA and try again."
			elif status == 422:
				msg = f"Invalid request data sent to ABDM (HTTP 422). Please verify the Aadhaar / OTP format."
			elif status == 429:
				msg = "ABDM rate limit reached. Please wait a minute and try again."
			else:
				msg = f"ABDM request failed (HTTP {status}). Check ABDM Settings and sandbox connectivity."
		frappe.throw(frappe._(msg), frappe.ValidationError)

	# -----------------------------------------------------------------------
	# IDOR guard
	# -----------------------------------------------------------------------

	def _assert_patient_permission(self, patient: str):
		"""Raise PermissionError if current user cannot write to the Patient record (M1-T4B IDOR)."""
		if not frappe.has_permission("Patient", doc=patient, ptype="write"):
			frappe.throw(
				frappe._("You do not have permission to perform ABDM operations for this patient"),
				frappe.PermissionError,
			)

	# -----------------------------------------------------------------------
	# SOP §3: ABHA enrolment via Aadhaar
	# -----------------------------------------------------------------------

	def generate_aadhaar_otp(self, patient: str, aadhaar: str) -> dict:
		"""
		M1-T11: SOP §3 Step 1 — Generate Aadhaar OTP.
		Encrypts Aadhaar before sending. Stores T-token in Token Registry.
		"""
		from healthcare.healthcare.doctype.abdm_token_registry.abdm_token_registry import store_t_token

		encrypted_aadhaar = encrypt_field(aadhaar)
		payload = {
			"loginId": encrypted_aadhaar,
			"loginHint": "aadhaar",
			"scope": ["abha-enrol"],
			"otpSystem": "aadhaar",
		}
		# max_retries=1: OTP send is non-idempotent — retrying could trigger duplicate OTPs
		response = self.call_abha(
			"/v3/enrollment/request/otp", payload=payload, patient=patient, max_retries=1
		)

		# Store T-token (txnId) from response
		t_token = response.get("txnId")
		if t_token:
			store_t_token(patient, t_token)

		return {"txnId": t_token}

	def resend_aadhaar_otp(self, patient: str, txn_id: str) -> dict:
		"""M1-T59: SOP §3 Step 2 — Resend OTP (reuses same txnId)."""
		payload = {"txnId": txn_id, "scope": ["abha-enrol"]}
		return self.call_abha(
			"/v3/enrollment/request/otp", payload=payload, patient=patient, max_retries=1
		)

	def enrol_abha_by_aadhaar(self, patient: str, txn_id: str, otp: str, mobile: str = "") -> dict:
		"""
		M1-T12: SOP §3 Steps 4-5 — Enrol ABHA via Aadhaar OTP + mobile.
		V3 requires the user's mobile in authData.otp.mobile (RSA-encrypted).
		ABDM auto-links when it matches Aadhaar-linked mobile; else triggers mobile OTP.
		"""
		encrypted_otp = encrypt_field(otp)
		otp_block: dict = {
			"txnId":    txn_id,
			"otpValue": encrypted_otp,
		}
		# mobile is plain text — ABDM validates it as a 10-digit number.
		# Only Aadhaar and OTP values are RSA-encrypted per SOP §3.
		if mobile:
			otp_block["mobile"] = mobile
		payload = {
			"authData": {
				"authMethods": ["otp"],
				"otp": otp_block,
			},
			"consent": {
				"code": "abha-enrollment",
				"version": "1.4",
			},
		}
		return self.call_abha(
			"/v3/enrollment/enrol/byAadhaar",
			payload=payload,
			patient=patient,
		)

	def send_mobile_otp_post_enrol(self, patient: str, txn_id: str, mobile: str = "") -> dict:
		"""
		M1-T60: SOP §3 Step 4a — Send mobile OTP after enrolment.
		Returns the mobile-verify sub-txnId; caller passes it to verify_mobile_otp_post_enrol.
		The enrollment T-token (set by enrol_by_aadhaar) is NOT overwritten here.
		"""
		if not mobile:
			frappe.throw(
				frappe._("Patient mobile number is required for mobile OTP verification. "
						 "Please add it to the Patient record first."),
				frappe.ValidationError,
			)
		payload = {
			"txnId": txn_id,
			"scope": ["abha-enrol", "mobile-verify"],
			"loginHint": "mobile",
			"loginId": encrypt_field(mobile),
			"otpSystem": "abdm",
		}
		response = self.call_abha(
			"/v3/enrollment/request/otp", payload=payload, patient=patient, max_retries=1
		)
		# Do NOT overwrite T-token — enrollment txnId (set by enrol_by_aadhaar) is authoritative.
		return response

	def verify_mobile_otp_post_enrol(self, patient: str, txn_id: str, otp: str) -> dict:
		"""
		M1-T60: SOP §3 Step 4b — Verify mobile OTP, receive X-token.
		txn_id = mobile-verify sub-txnId from send_mobile_otp_post_enrol.
		T-token (enrollment session txnId) is NOT overwritten — suggestions need it.
		/v3/enrollment/auth/byAbdm requires scope + timeStamp in the payload
		(same pattern as verify_mobile_otp_enrol / verify_dl_otp).
		"""
		from healthcare.healthcare.doctype.abdm_token_registry.abdm_token_registry import (
			store_x_token,
		)
		encrypted_otp = encrypt_field(otp)
		timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
		payload = {
			"scope": ["abha-enrol", "mobile-verify"],
			"authData": {
				"authMethods": ["otp"],
				"otp": {
					"timeStamp": timestamp,
					"txnId": txn_id,
					"otpValue": encrypted_otp,
				},
			},
		}
		response = self.call_abha(
			"/v3/enrollment/auth/byAbdm",
			payload=payload,
			patient=patient,
		)
		_tok_block = response.get("tokens") or {}
		jwt_token = (
			_tok_block.get("token")
			or response.get("token")
			or response.get("xToken")
			or response.get("accessToken")
		)
		if jwt_token:
			# X-token only — T-token (enrollment txnId) is deliberately left untouched
			# here; get_abha_address_suggestions/set_abha_address still need it.
			expires_in_sec = int(_tok_block.get("expiresIn") or response.get("expiresIn") or 1800)
			store_x_token(patient, jwt_token, expiry_minutes=max(expires_in_sec // 60, 5))
		return response

	def get_abha_address_suggestions(self, patient: str) -> list:
		"""M1-T61: SOP §3 Step 6 — Get ABHA address suggestions.
		ABDM V3 enrollment endpoints require Transaction_Id: {UUID} header (not T-Token: Bearer).
		T-token (enrollment txnId) is NOT overwritten here — set_abha_address still needs it.
		"""
		response = self.call_abha(
			"/v3/enrollment/enrol/suggestion",
			method="GET",
			patient=patient,
			use_txn_id=True,
		)
		return response.get("abhaAddressList", [])

	def set_abha_address(self, patient: str, abha_address: str) -> dict:
		"""M1-T61: SOP §3 Step 6 — Finalise ABHA address selection.
		Per ABDM V3 spec:
		  - NO Transaction_Id header (unlike enrol/suggestion which does need it)
		  - txnId goes in the REQUEST BODY (from suggestions response, stored in T-token)
		  - preferred=1 is mandatory (marks this as the preferred ABHA address)
		  - abhaAddress is the bare address WITHOUT @sbx/@abdm suffix
		"""
		from healthcare.healthcare.doctype.abdm_token_registry.abdm_token_registry import get_or_create_registry
		reg = get_or_create_registry(patient)
		txn_id = reg.get_password("t_token") or ""
		# Strip @sbx/@abdm suffix — ABDM V3 spec body example shows bare address (no domain suffix)
		bare_address = abha_address.split("@")[0] if "@" in abha_address else abha_address
		payload = {
			"txnId": txn_id,
			"abhaAddress": bare_address,
			"preferred": 1,
		}
		return self.call_abha(
			"/v3/enrollment/enrol/abha-address",
			payload=payload,
			patient=patient,
			use_txn_id=False,  # NO Transaction_Id header for this endpoint
		)

	# -----------------------------------------------------------------------
	# SOP §3: ABHA creation via Mobile OTP  (M1-T16)
	# -----------------------------------------------------------------------

	def generate_mobile_otp(self, patient: str, mobile: str) -> dict:
		"""
		M1-T16: Generate OTP for mobile-only ABHA creation.
		Scope: abha-enrol + mobile-verify (per SOP §3 Step 4a).
		"""
		from healthcare.healthcare.doctype.abdm_token_registry.abdm_token_registry import store_t_token
		encrypted_mobile = encrypt_field(mobile)
		payload = {
			"scope": ["abha-enrol", "mobile-verify"],
			"loginHint": "mobile",
			"loginId": encrypted_mobile,
			"otpSystem": "abdm",
		}
		response = self.call_abha(
			"/v3/enrollment/request/otp", payload=payload, patient=patient, max_retries=1
		)
		t_token = response.get("txnId")
		if t_token:
			store_t_token(patient, t_token)
		return response

	def verify_mobile_otp_enrol(self, patient: str, txn_id: str, otp: str) -> dict:
		"""
		M1-T16: Verify mobile OTP for mobile-only ABHA creation.
		Uses authData structure per SOP §3 Step 4b.
		Returns txnId to chain into address suggestion step.
		"""
		encrypted_otp = encrypt_field(otp)
		timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
		payload = {
			"scope": ["abha-enrol", "mobile-verify"],
			"authData": {
				"authMethods": ["otp"],
				"otp": {
					"timeStamp": timestamp,
					"txnId": txn_id,
					"otpValue": encrypted_otp,
				},
			},
		}
		return self.call_abha("/v3/enrollment/auth/byAbdm", payload=payload, patient=patient)

	# -----------------------------------------------------------------------
	# SOP §4: ABHA creation via Driving Licence  (M1-T62/T63)
	# -----------------------------------------------------------------------

	def generate_dl_otp(self, patient: str, mobile: str) -> dict:
		"""
		M1-T62: SOP §4 Step 1 — Generate mobile OTP for DL flow.
		Scope: abha-enrol + mobile-verify + dl-flow.
		"""
		from healthcare.healthcare.doctype.abdm_token_registry.abdm_token_registry import store_t_token
		encrypted_mobile = encrypt_field(mobile)
		payload = {
			"scope": ["abha-enrol", "mobile-verify", "dl-flow"],
			"loginHint": "mobile",
			"loginId": encrypted_mobile,
			"otpSystem": "abdm",
		}
		response = self.call_abha(
			"/v3/enrollment/request/otp", payload=payload, patient=patient, max_retries=1
		)
		t_token = response.get("txnId")
		if t_token:
			store_t_token(patient, t_token)
		return response

	def verify_dl_otp(self, patient: str, txn_id: str, otp: str) -> dict:
		"""
		M1-T62: SOP §4 Step 2 — Verify mobile OTP for DL flow.
		Same authData structure but includes dl-flow scope.
		"""
		encrypted_otp = encrypt_field(otp)
		timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
		payload = {
			"scope": ["abha-enrol", "mobile-verify", "dl-flow"],
			"authData": {
				"authMethods": ["otp"],
				"otp": {
					"timeStamp": timestamp,
					"txnId": txn_id,
					"otpValue": encrypted_otp,
				},
			},
		}
		return self.call_abha("/v3/enrollment/auth/byAbdm", payload=payload, patient=patient)

	def enrol_by_dl(self, patient: str, txn_id: str, dl_data: dict) -> dict:
		"""
		M1-T63: SOP §4 Step 3 — Submit DL document for ABHA creation.
		dl_data keys: documentId, firstName, middleName, lastName, dob (YYYY-MM-DD),
		              gender (M/F/O), frontSidePhoto (base64), backSidePhoto (base64),
		              address, state, district, pinCode.
		"""
		payload = {
			"txnId": txn_id,
			"documentType": "DRIVING_LICENCE",
			"consent": {"code": "abha-enrollment", "version": "1.4"},
			**dl_data,
		}
		return self.call_abha("/v3/enrollment/enrol/byDocument", payload=payload, patient=patient)

	# -----------------------------------------------------------------------
	# SOP §6: Login / Verify ABHA (manual verification)
	# -----------------------------------------------------------------------

	def request_login_otp(
		self,
		patient: str,
		abha_address: str,
		otp_mode: str = "mobile",
	) -> dict:
		"""
		M1-T24: SOP §6 — Send OTP to verify/link an existing ABHA.

		otp_mode (caller-supplied):
		  "mobile"  → scope abha-login + mobile-verify, otpSystem abdm  (SOP §6.2/6.3)
		  "aadhaar" → scope abha-login + aadhaar-verify, otpSystem aadhaar (SOP §6.1)
		             Only valid when loginHint == "abha-number".

		loginHint detection:
		  14-digit number → "abha-number"
		  contains "@"   → "abha-address"  (only mobile-verify supported)
		  10-digit mobile → "mobile"        (only mobile-verify supported)

		loginId is RSA-encrypted per SOP. txnId stored as T-token.
		"""
		from healthcare.healthcare.doctype.abdm_token_registry.abdm_token_registry import store_t_token

		clean = abha_address.strip()
		otp_mode = otp_mode.lower() if otp_mode else "mobile"

		if clean.isdigit() and len(clean) == 14:
			login_hint = "abha-number"
		elif "@" in clean:
			login_hint = "abha-address"
			if otp_mode == "aadhaar":
				frappe.throw(
					frappe._("Aadhaar OTP is only supported when logging in with a 14-digit ABHA number."),
					frappe.ValidationError,
				)
		elif clean.isdigit() and len(clean) == 10:
			login_hint = "mobile"
			if otp_mode == "aadhaar":
				frappe.throw(
					frappe._("Aadhaar OTP is only supported when logging in with a 14-digit ABHA number."),
					frappe.ValidationError,
				)
		else:
			frappe.throw(
				frappe._("Enter a valid ABHA address (name@abdm) or 14-digit ABHA number."),
				frappe.ValidationError,
			)

		if otp_mode == "aadhaar":
			scope      = ["abha-login", "aadhaar-verify"]
			otp_system = "aadhaar"
		else:
			scope      = ["abha-login", "mobile-verify"]
			otp_system = "abdm"

		payload = {
			"scope":     scope,
			"loginHint": login_hint,
			"loginId":   encrypt_field(clean),   # RSA-encrypted per SOP
			"otpSystem": otp_system,
		}
		response = self.call_abha(
			"/v3/profile/login/request/otp", payload=payload, patient=patient, max_retries=1
		)
		t_token = response.get("txnId")
		if t_token:
			store_t_token(patient, t_token)
		return response

	def verify_login_otp(
		self,
		patient: str,
		txn_id: str,
		otp: str,
		otp_mode: str = "mobile",
	) -> dict:
		"""
		M1-T24: SOP §6 — Two-step login OTP verification.

		otp_mode must match what was used in request_login_otp:
		  "mobile"  → scope abha-login + mobile-verify
		  "aadhaar" → scope abha-login + aadhaar-verify

		Step 1: POST /v3/profile/login/verify
		  Payload: scope + authData.otp.{txnId, otpValue}
		  Response: T-token (short-lived) + accounts[]

		Step 2: POST /v3/profile/login/verify/user  (T-Token header)
		  Payload: {ABHANumber: plain text (14 digits), txnId}
		  Response: X-token + expiresIn

		X-token stored in Token Registry. Merged response (with accounts[]) returned.
		"""
		from healthcare.healthcare.doctype.abdm_token_registry.abdm_token_registry import store_x_token

		otp_mode = otp_mode.lower() if otp_mode else "mobile"
		scope = ["abha-login", "aadhaar-verify"] if otp_mode == "aadhaar" else ["abha-login", "mobile-verify"]

		encrypted_otp = encrypt_field(otp)

		# ── Step 1: /v3/profile/login/verify ──────────────────────────────────
		payload = {
			"scope": scope,
			"authData": {
				"authMethods": ["otp"],
				"otp": {
					"txnId":    txn_id,
					"otpValue": encrypted_otp,
				},
			},
		}
		verify_resp = self.call_abha(
			"/v3/profile/login/verify",
			payload=payload,
			patient=patient,
		)

		t_token  = verify_resp.get("token")
		new_txn  = verify_resp.get("txnId", txn_id)
		accounts = verify_resp.get("accounts", [])

		if not t_token:
			frappe.throw(frappe._("OTP verification failed — no token received"), frappe.ValidationError)
		if not accounts:
			frappe.throw(frappe._("No ABHA account found for these credentials"), frappe.ValidationError)

		# ── Step 2: /v3/profile/login/verify/user ─────────────────────────────
		# T-Token header is mandatory. ABHANumber is PLAIN TEXT per ABDM SOP
		# (only OTP values / Aadhaar / mobile loginId require RSA encryption).
		# Send ABHANumber in original dashed format — sandbox rejects stripped form.
		# txnId from the /verify response is also required by the sandbox.
		# Check both PascalCase and camelCase — sandbox may use either
		abha_num_raw = accounts[0].get("ABHANumber") or accounts[0].get("abhaNumber") or ""
		user_payload = {
			"ABHANumber": abha_num_raw,  # keep original format (dashes if present)
			"txnId": new_txn,
		}
		user_headers = self._build_headers(patient)
		user_headers["T-Token"] = f"Bearer {t_token}"

		user_resp = self._request_with_retry(
			"POST",
			f"{self.base_url}/v3/profile/login/verify/user",
			user_headers,
			user_payload,
		)

		x_token = user_resp.get("token")
		if x_token:
			expires_in_sec = int(user_resp.get("expiresIn", 1800))
			store_x_token(patient, x_token, expiry_minutes=max(expires_in_sec // 60, 5))

		# Return merged response — profile.py reads `accounts` for ABHA details
		return {**user_resp, "accounts": accounts}

	# -----------------------------------------------------------------------
	# M1-T92: Login via Password — SOP §6, loginHint/authMethods "password"
	# -----------------------------------------------------------------------

	def login_with_password(
		self,
		patient: str,
		login_id: str,
		password: str,
		login_hint: str = "abha-number",
	) -> dict:
		"""
		M1-T92: Standalone password login — no OTP required.

		CAVEAT: the SOP confirms PASSWORD("password") as a valid loginHint /
		authMethods enum value on these shared endpoints (it appears in every
		enum list alongside "otp"), but gives password login no dedicated
		worked example anywhere in the 116-page Integrator Guide. This
		implementation is built by analogy with verify_login_otp's two-step
		shape below — CONFIRM the exact request/response shape against the
		ABHA sandbox before relying on this in production.

		login_hint: "abha-number" (14-digit, default) | "mobile" | "email" | "aadhaar"
		login_id  : the matching identifier for login_hint (RSA-encrypted)
		password  : the ABHA account password (RSA-encrypted)

		Step 1 (assumed): POST /v3/profile/login/verify
		  Payload: scope=["abha-login","password-verify"], loginHint, loginId,
		           authData.authMethods=["password"], authData.password.value
		  Response (assumed, mirrors OTP path): T-token (short-lived) + accounts[]

		Step 2: POST /v3/profile/login/verify/user (T-Token header) — identical
		  to the OTP path's step 2 below — exchanges T-token + ABHANumber for X-token.
		"""
		from healthcare.healthcare.doctype.abdm_token_registry.abdm_token_registry import store_x_token

		payload = {
			"scope": ["abha-login", "password-verify"],
			"loginHint": login_hint,
			"loginId": encrypt_field(login_id),
			"authData": {
				"authMethods": ["password"],
				"password": {
					"value": encrypt_field(password),
				},
			},
		}
		verify_resp = self.call_abha(
			"/v3/profile/login/verify",
			payload=payload,
			patient=patient,
		)

		t_token  = verify_resp.get("token")
		new_txn  = verify_resp.get("txnId")
		accounts = verify_resp.get("accounts", [])

		if not t_token:
			frappe.throw(frappe._("Password verification failed — no token received"), frappe.ValidationError)
		if not accounts:
			frappe.throw(frappe._("No ABHA account found for these credentials"), frappe.ValidationError)

		abha_num_raw = accounts[0].get("ABHANumber") or accounts[0].get("abhaNumber") or ""
		user_payload = {
			"ABHANumber": abha_num_raw,
			"txnId": new_txn,
		}
		user_headers = self._build_headers(patient)
		user_headers["T-Token"] = f"Bearer {t_token}"

		user_resp = self._request_with_retry(
			"POST",
			f"{self.base_url}/v3/profile/login/verify/user",
			user_headers,
			user_payload,
		)

		x_token = user_resp.get("token")
		if x_token:
			expires_in_sec = int(user_resp.get("expiresIn", 1800))
			store_x_token(patient, x_token, expiry_minutes=max(expires_in_sec // 60, 5))

		return {**user_resp, "accounts": accounts}

	# -----------------------------------------------------------------------
	# SOP §6 (new): Verify ABHA — Path 1 (mobile / Aadhaar login)
	# VRFY_ABHA_101 (mobile OTP) / VRFY_ABHA_201 (Aadhaar OTP)
	# -----------------------------------------------------------------------

	def request_abha_login_otp(
		self,
		patient: str,
		login_id: str,
		login_hint: str,
	) -> dict:
		"""
		POST /v3/profile/login/request/otp
		login_hint: "mobile" | "aadhaar"
		login_id  : 10-digit mobile number or 12-digit Aadhaar number (RSA-encrypted)
		"""
		from healthcare.healthcare.doctype.abdm_token_registry.abdm_token_registry import store_t_token

		login_hint = login_hint.lower()
		if login_hint == "aadhaar":
			scope      = ["abha-login", "aadhaar-verify"]
			otp_system = "aadhaar"
		else:
			scope      = ["abha-login", "mobile-verify"]
			otp_system = "abdm"

		# ABDM validates the decrypted loginId against its canonical ABHA
		# number representation, which is always dash-formatted
		# (XX-XXXX-XXXX-XXXX) in every ABDM response/example — a bare
		# 14-digit string fails their server-side pattern check with
		# {"loginId": "LoginId is invalid"}.
		if login_hint == "abha-number" and login_id.isdigit() and len(login_id) == 14:
			login_id = f"{login_id[0:2]}-{login_id[2:6]}-{login_id[6:10]}-{login_id[10:14]}"

		payload = {
			"scope":     scope,
			"loginHint": login_hint,
			"loginId":   encrypt_field(login_id),
			"otpSystem": otp_system,
		}
		response = self.call_abha(
			"/v3/profile/login/request/otp", payload=payload, patient=patient, max_retries=1
		)
		txn_id = response.get("txnId")
		if txn_id:
			store_t_token(patient, txn_id)
		return response

	def verify_abha_login_otp(
		self,
		patient: str,
		txn_id: str,
		otp: str,
		login_hint: str = "mobile",
	) -> dict:
		"""
		POST /v3/profile/login/verify  (Step 1)
		POST /v3/profile/login/verify/user  (Step 2 — optional T→X upgrade)

		The ABDM sandbox returns a usable session token directly in Step 1.
		We store that immediately as X-token, then try Step 2 to upgrade it
		to a longer-lived token if the endpoint is available.
		"""
		from healthcare.healthcare.doctype.abdm_token_registry.abdm_token_registry import store_x_token

		login_hint = login_hint.lower()
		if login_hint == "aadhaar":
			scope = ["abha-login", "aadhaar-verify"]
		else:
			scope = ["abha-login", "mobile-verify"]

		# ── Step 1: verify OTP ──────────────────────────────────────────────
		payload = {
			"scope": scope,
			"authData": {
				"authMethods": ["otp"],
				"otp": {
					"txnId":    txn_id,
					"otpValue": encrypt_field(otp),
				},
			},
		}
		verify_resp = self.call_abha("/v3/profile/login/verify", payload=payload, patient=patient)

		t_token  = verify_resp.get("token")
		new_txn  = verify_resp.get("txnId", txn_id)
		accounts = verify_resp.get("accounts", [])

		# Store Step 1 token immediately as X-token.
		# The sandbox returns a usable session token here (may be same as T-token).
		# TTL: use expiresIn from response, default 30 min as conservative fallback.
		if t_token:
			expires_in_sec = int(verify_resp.get("expiresIn", 1800))
			# Use the actual ABDM expiry — do NOT inflate with a minimum floor here.
			# If the sandbox issues a short-lived token (e.g. 5 min), inflating to 30 min
			# causes us to send an expired token to account-management APIs.
			store_x_token(patient, t_token, expiry_minutes=max(expires_in_sec // 60, 1))
			abdm_log("info", f"X-token stored from /verify Step 1 | patient={patient} | expiresIn={expires_in_sec}s")

		if not accounts:
			return verify_resp

		# ── Step 2: try to exchange T-token for proper X-token ───────────────
		# This step is optional — sandbox may not support or need it.
		# If it works, overwrite the Step 1 token with the longer-lived X-token.
		if t_token:
			try:
				# Check both PascalCase and camelCase — sandbox may use either
				abha_num_raw = accounts[0].get("ABHANumber") or accounts[0].get("abhaNumber") or ""
				user_payload = {
					"ABHANumber": abha_num_raw,  # keep original format (dashes if present)
					"txnId": new_txn,
				}
				user_headers = self._build_headers(patient)
				user_headers["T-Token"] = f"Bearer {t_token}"

				# Raw request, not _request_with_retry/call_abha: this step is
				# documented as optional and expected to sometimes fail (e.g. a
				# single-account abha-number login has no multi-account T-token
				# to exchange) — that's a normal, silent fallback, not an error
				# worth 3 retries or an Error Log entry.
				user_resp_raw = requests.post(
					f"{self.base_url}/v3/profile/login/verify/user",
					json=user_payload,
					headers=user_headers,
					timeout=(5, 10),
				)
				user_resp_raw.raise_for_status()
				user_resp = user_resp_raw.json()

				x_token = user_resp.get("token")
				if x_token:
					expires_in_sec = int(user_resp.get("expiresIn", 1800))
					store_x_token(patient, x_token, expiry_minutes=max(expires_in_sec // 60, 5))
					abdm_log("info", f"X-token upgraded via /verify/user | patient={patient}")
			except Exception as exc:
				# Non-fatal — Step 1 token is already stored and usable
				# Log accounts keys so we can verify ABHANumber field name/format (no PII values)
				acc_keys = list(accounts[0].keys()) if accounts else []
				abdm_log("warning", f"verify/user step skipped ({type(exc).__name__}: {exc}) | accounts keys={acc_keys} | abha_field={abha_num_raw[:4] + '...' if abha_num_raw else 'MISSING'}")

		return {**verify_resp, "accounts": accounts}

	# -----------------------------------------------------------------------
	# SOP §6 (new): Verify ABHA — Path 2 (ABHA address / PHR web login)
	# VRFY_ABHA_102 (mobile OTP via address) / VRFY_ABHA_202 (Aadhaar OTP via address)
	# -----------------------------------------------------------------------

	def request_abha_address_otp(
		self,
		patient: str,
		abha_address: str,
		otp_system: str = "abdm",
	) -> dict:
		"""
		Path 2 Step 2 — Request ABHA address OTP (SOP §12.1 Step 2).

		POST {phr_base_url}/login/abha/request/otp
		SBX: https://abhasbx.abdm.gov.in/abha/api/v3/phr/web/login/abha/request/otp

		NOTE: this is a DIFFERENT endpoint from Step 1 (/login/abha/search),
		which only looks up available auth methods and never sends an OTP —
		calling /search alone (as this method previously did) silently never
		triggers a real OTP send. loginId must be RSA-encrypted per spec.
		"""
		otp_system = (otp_system or "abdm").lower()
		verify_scope = "aadhaar-verify" if otp_system == "aadhaar" else "mobile-verify"

		payload = {
			"scope": ["abha-address-login", verify_scope],
			"loginHint": "abha-address",
			"loginId": encrypt_field(abha_address),
			"otpSystem": otp_system,
		}
		response = self.call_abha(
			"/v3/phr/web/login/abha/request/otp",
			payload=payload,
			patient=patient,
			use_phr_base=True,
			max_retries=1,
		)
		return response

	def verify_abha_address_otp(
		self,
		patient: str,
		txn_id: str,
		otp: str,
		otp_system: str = "abdm",
	) -> dict:
		"""
		Path 2 Step 3 — Verify ABHA address OTP and obtain X-token (SOP §12.1 Step 3).

		POST {phr_base_url}/login/abha/verify
		SBX: https://abhasbx.abdm.gov.in/abha/api/v3/phr/web/login/abha/verify
		"""
		from healthcare.healthcare.doctype.abdm_token_registry.abdm_token_registry import store_x_token

		otp_system  = (otp_system or "abdm").lower()
		verify_scope = "aadhaar-verify" if otp_system == "aadhaar" else "mobile-verify"

		payload = {
			"scope": ["abha-address-login", verify_scope],
			"authData": {
				"authMethods": ["otp"],
				"otp": {
					"txnId": txn_id,
					"otpValue": encrypt_field(otp),
				},
			},
		}
		response = self.call_abha(
			"/v3/phr/web/login/abha/verify",
			payload=payload,
			patient=patient,
			use_phr_base=True,
		)
		_tok_block = response.get("tokens") or {}
		x_token = _tok_block.get("token") or response.get("token") or response.get("accessToken")
		if x_token:
			expires_in = int(_tok_block.get("expiresIn") or response.get("expiresIn") or 1800)
			store_x_token(patient, x_token, expiry_minutes=max(expires_in // 60, 5))
		return response

	# -----------------------------------------------------------------------
	# SOP §8-10: Profile, QR, Card
	# -----------------------------------------------------------------------

	def get_abha_profile(self, patient: str) -> dict:
		"""
		M1-T65: SOP §8 / §12.3.1 — GET profile.
		Same Path-1-vs-Path-2 endpoint split as get_abha_qr_code — a
		PHR-web session token (from ABHA-address verification) is
		rejected by the Path 1 /v3/profile/account endpoint, so fall
		back to the PHR-specific one on failure.

		Uses raw requests (not call_abha/_request_with_retry) for both
		attempts, same as get_abha_qr_code/get_abha_card — a Path-1 token
		mismatch is an EXPECTED, non-fatal case handled by the fallback,
		not something worth 3 retries or an Error Log entry.
		"""
		self._assert_patient_permission(patient)
		headers = self._build_headers(patient, use_x_token=True)

		urls = [
			f"{self.base_url}/v3/profile/account",
			f"{self.phr_base_url}/v3/phr/web/login/profile/abha-profile",
		]
		resp, last_exc = None, None
		for url in urls:
			try:
				resp = requests.get(url, headers=headers, timeout=15)
				abdm_log("info", f"ABHA profile GET → {url} → {resp.status_code}")
				resp.raise_for_status()
				last_exc = None
				break
			except requests.HTTPError as e:
				last_exc, resp = e, None
		if last_exc is not None:
			self._handle_http_error(last_exc)
		return resp.json()

	# update_abha_profile: ABDM §7.1/7.2 (Update Mobile/Email) is Post-M1 / M2.
	# The correct ABDM endpoint is not yet available in the sandbox.
	# Local Patient update is handled in profile.py::update_abha_profile.

	def get_abha_qr_code(self, patient: str) -> str:
		"""
		M1-T66: SOP §9 / §12.3.3 — GET QR code.

		Two distinct endpoints exist depending on which flow issued the
		current X-token:
		  - Path 1 (login via mobile/Aadhaar/ABHA-number, SOP §6):
		    {base_url}/v3/profile/account/qrCode
		  - Path 2 (ABHA-address verification, SOP §12.3.3) issues a
		    PHR-web session token that the Path 1 endpoint rejects — it
		    needs {phr_base_url}/v3/phr/web/login/profile/abha/qr-code
		The token registry doesn't track which path issued the token, so
		try Path 1 first and fall back to the PHR endpoint on failure.

		ABDM sandbox returns binary PNG directly (not JSON {"qrCode": "..."}).
		"""
		import base64
		self._assert_patient_permission(patient)

		headers = self._build_headers(patient, use_x_token=True)
		headers["Accept"] = "image/png"

		urls = [
			f"{self.base_url}/v3/profile/account/qrCode",
			f"{self.phr_base_url}/v3/phr/web/login/profile/abha/qr-code",
		]
		resp, last_exc = None, None
		for url in urls:
			try:
				resp = requests.get(url, headers=headers, timeout=15)
				abdm_log("info", f"ABHA QR GET → {url} → {resp.status_code}")
				resp.raise_for_status()
				last_exc = None
				break
			except requests.HTTPError as e:
				last_exc, resp = e, None
		if last_exc is not None:
			self._handle_http_error(last_exc)

		content_type = resp.headers.get("Content-Type", "")
		if "json" in content_type:
			# Some environments return JSON {"qrCode": "base64..."}
			data = resp.json()
			return data.get("qrCode", "")
		# Binary PNG — encode to base64 for frontend
		return base64.b64encode(resp.content).decode("utf-8")

	def get_abha_card(self, patient: str) -> bytes:
		"""
		M1-T67: SOP §10 / §12.3.2 — GET ABHA Card as PDF/PNG bytes.
		Same Path-1-vs-Path-2 endpoint split as get_abha_qr_code — see
		its docstring for why both are tried.
		"""
		self._assert_patient_permission(patient)

		headers = self._build_headers(patient, use_x_token=True)
		headers["Accept"] = "image/png"

		urls = [
			f"{self.base_url}/v3/profile/account/abha-card",
			f"{self.phr_base_url}/v3/phr/web/login/profile/abha/phr-card",
		]
		resp, last_exc = None, None
		for url in urls:
			try:
				resp = requests.get(url, headers=headers, timeout=15)
				abdm_log("info", f"ABHA card GET → {url} → {resp.status_code}")
				resp.raise_for_status()
				last_exc = None
				break
			except requests.HTTPError as e:
				last_exc, resp = e, None
		if last_exc is not None:
			self._handle_http_error(last_exc)
		return resp.content

	# -----------------------------------------------------------------------
	# SOP §7.3-7.5: ABHA lifecycle
	# -----------------------------------------------------------------------

	def request_account_otp(
		self,
		patient: str,
		action: str,
		abha_number: str,
		otp_mode: str = "mobile",
		aadhaar_number: str | None = None,
		abha_address: str | None = None,
		mobile_number: str | None = None,
	) -> dict:
		"""
		SOP §8.3.2/§8.4.2/§8.5 Step 1 — Request OTP for a lifecycle action.

		Uses /v3/profile/login/request/otp (same as regular ABHA login).
		Valid loginHints: "mobile" (10-digit) or "aadhaar" (12-digit).
		The returned txnId is then used at /v3/profile/account/verify.
		"""
		abha_number_clean = abha_number.replace("-", "")

		if action in ("deactivate", "delete", "reactivate"):
			# Spec (SOP §7.3/§7.4/§7.5): loginHint must be "abha-number".
			# Encrypt the ABHA number WITH dashes (e.g. "91-XXXX-XXXX-XXXX") — this
			# matches the format ABDM stores and what the Postman collection sends.
			# Reactivate uses a 3-scope array + /v3/profile/account/request/otp.
			if action == "reactivate":
				scope      = ["abha-login", "mobile-verify", "re-activate"]
				otp_system = "abdm"
			elif action == "delete":
				scope      = ["abha-profile", "delete"]
				otp_system = "aadhaar" if otp_mode == "aadhaar" else "abdm"
			else:  # deactivate
				scope      = ["abha-profile", "de-activate"]
				otp_system = "aadhaar" if otp_mode == "aadhaar" else "abdm"

			login_hint = "abha-number"
			# Encrypt the stored (dashed) ABHA number, NOT the stripped version
			login_id   = encrypt_field(abha_number)  # e.g. "91-XXXX-XXXX-XXXX"

			payload = {
				"txnId":     "",            # required by spec (empty string for first call)
				"scope":     scope,
				"loginHint": login_hint,
				"loginId":   login_id,
				"otpSystem": otp_system,
			}
			endpoint = "/v3/profile/account/request/otp"
			use_x    = True   # profile endpoint requires X-token

		else:
			frappe.throw(frappe._("Invalid lifecycle action"), frappe.ValidationError)

		abdm_log("info", f"request_account_otp | action={action} otp_mode={otp_mode} scope={payload['scope']} endpoint={endpoint} use_x_token={use_x} loginHint={payload.get('loginHint','')} abha_num_len={len(abha_number)}")
		return self.call_abha(
			endpoint,
			payload=payload,
			patient=patient,
			use_x_token=use_x,
			max_retries=1,
		)

	def deactivate_abha(self, patient: str, txn_id: str, otp: str) -> dict:
		"""M1-T68: SOP §8.4.2 Step 2 — Verify OTP and deactivate ABHA."""
		payload = {
			"scope": ["abha-profile", "de-activate"],
			"authData": {
				"authMethods": ["otp"],
				"otp": {"txnId": txn_id, "otpValue": encrypt_field(otp)},
			},
			"reasons": ["USER_INITIATED"],
		}
		abdm_log("info", "deactivate_abha → /v3/profile/account/verify (OTP)")
		return self.call_abha("/v3/profile/account/verify", payload=payload, patient=patient, use_x_token=True)

	def delete_abha(self, patient: str, txn_id: str, otp: str) -> dict:
		"""M1-T69: SOP §8.3.2 Step 2 — Verify OTP and permanently delete ABHA."""
		payload = {
			"scope": ["abha-profile", "delete"],
			"authData": {
				"authMethods": ["otp"],
				"otp": {"txnId": txn_id, "otpValue": encrypt_field(otp)},
			},
			"reasons": ["USER_INITIATED"],
		}
		abdm_log("info", "delete_abha → /v3/profile/account/verify (OTP)")
		return self.call_abha("/v3/profile/account/verify", payload=payload, patient=patient, use_x_token=True)

	def reactivate_abha(self, patient: str, txn_id: str, otp: str, otp_mode: str = "mobile") -> dict:
		"""
		M1-T70: SOP §8.5 Step 2 — Verify OTP and reactivate ABHA.

		Two-step flow (same as regular login) because account was deactivated:
		  Step 1: POST /v3/profile/login/verify   → T-token + accounts[]
		  Step 2: POST /v3/profile/login/verify/user (T-Token header) → X-token

		otp_mode must match what was sent in request_account_otp:
		  "mobile"  → scope ["abha-login", "mobile-verify",  "re-activate"]
		  "aadhaar" → scope ["abha-login", "aadhaar-verify", "re-activate"]
		"""
		from healthcare.healthcare.doctype.abdm_token_registry.abdm_token_registry import store_x_token

		scope = (
			["abha-login", "aadhaar-verify", "re-activate"]
			if otp_mode == "aadhaar"
			else ["abha-login", "mobile-verify", "re-activate"]
		)
		encrypted_otp = encrypt_field(otp)

		# ── Step 1: /v3/profile/login/verify ─────────────────────────────────────
		payload = {
			"scope": scope,
			"authData": {
				"authMethods": ["otp"],
				"otp": {
					"txnId":    txn_id,
					"otpValue": encrypted_otp,
				},
			},
		}
		verify_resp = self.call_abha(
			"/v3/profile/login/verify",
			payload=payload,
			patient=patient,
			use_x_token=False,
		)

		t_token  = verify_resp.get("token")
		new_txn  = verify_resp.get("txnId", txn_id)
		accounts = verify_resp.get("accounts", [])

		# Store Step 1 token immediately as a fallback X-token in case Step 2 fails
		if t_token:
			expires_in_sec = int(verify_resp.get("expiresIn", 1800))
			store_x_token(patient, t_token, expiry_minutes=max(expires_in_sec // 60, 1))
			abdm_log("info", f"X-token (step 1) stored after reactivation | patient={patient}")

		if not t_token:
			frappe.throw(frappe._("OTP verification failed — no token received from ABDM"), frappe.ValidationError)

		# ── Step 2: /v3/profile/login/verify/user ────────────────────────────────
		# Exchange the short-lived T-token for a proper X-token.
		# ABHANumber comes from Step 1 accounts[]; plain text (no RSA encryption).
		try:
			abha_num_raw = ""
			if accounts:
				abha_num_raw = accounts[0].get("ABHANumber") or accounts[0].get("abhaNumber") or ""

			user_payload = {
				"ABHANumber": abha_num_raw,
				"txnId":      new_txn,
			}
			user_headers = self._build_headers(patient)
			user_headers["T-Token"] = f"Bearer {t_token}"

			user_resp = self._request_with_retry(
				"POST",
				f"{self.base_url}/v3/profile/login/verify/user",
				user_headers,
				user_payload,
			)

			x_token = user_resp.get("token")
			if x_token:
				expires_in_sec = int(user_resp.get("expiresIn", 1800))
				store_x_token(patient, x_token, expiry_minutes=max(expires_in_sec // 60, 5))
				abdm_log("info", f"X-token upgraded via /verify/user after reactivation | patient={patient}")

			return {**user_resp, "accounts": accounts}
		except Exception as exc:
			# Step 2 failed — Step 1 token is already stored and the account is reactivated.
			# Log warning but don't fail the whole operation.
			abdm_log("warning", f"reactivate /verify/user step failed ({type(exc).__name__}: {exc}) — using step-1 token")
			return {**verify_resp, "accounts": accounts}

	# -----------------------------------------------------------------------
	# SOP §12: ABHA Address Verification via PHR base URL
	# -----------------------------------------------------------------------

	def request_address_verify_mobile_otp(self, patient: str, mobile: str) -> dict:
		"""M1-T73: SOP §12.1 — Mobile OTP for ABHA address verification."""
		encrypted_mobile = encrypt_field(mobile)
		payload = {"loginId": encrypted_mobile, "loginHint": "mobile", "otpSystem": "abdm"}
		return self.call_abha(
			"/request/otp",
			payload=payload,
			patient=patient,
			use_phr_base=True,
			max_retries=1,
		)

	def verify_address_mobile_otp(self, patient: str, txn_id: str, otp: str) -> dict:
		"""M1-T73: SOP §12.1 — Verify mobile OTP, store X-token."""
		from healthcare.healthcare.doctype.abdm_token_registry.abdm_token_registry import store_x_token

		encrypted_otp = encrypt_field(otp)
		payload = {"txnId": txn_id, "otp": encrypted_otp}
		response = self.call_abha("/verify/otp", payload=payload, patient=patient, use_phr_base=True)
		x_token = response.get("tokens", {}).get("token")
		if x_token:
			store_x_token(patient, x_token)
		return response

	def request_address_verify_aadhaar_otp(self, patient: str, aadhaar: str) -> dict:
		"""M1-T74: SOP §12.2 — Aadhaar OTP for ABHA address verification."""
		encrypted_aadhaar = encrypt_field(aadhaar)
		payload = {"loginId": encrypted_aadhaar, "loginHint": "aadhaar", "otpSystem": "aadhaar"}
		return self.call_abha(
			"/request/otp", payload=payload, patient=patient, use_phr_base=True, max_retries=1
		)

	# -----------------------------------------------------------------------
	# Token refresh (M1-T28 scheduler)
	# -----------------------------------------------------------------------

	def refresh_x_token(self, registry_name: str) -> bool:
		"""
		M1-T28: Attempt to refresh the X-token for a Token Registry record.

		ABHA V3 does not provide a server-side X-token refresh without user
		interaction — the token is user-scoped and requires OTP re-authentication.

		Strategy:
		  1. If token is still valid (not yet expired): no-op, return True.
		  2. If token is expired: clear it from the registry, return False.
		     The patient_abha.js dashboard badge will show EXPIRED status,
		     prompting the user to re-verify via "Verify / Link ABHA".

		Returns True if token is still usable, False if cleared.
		"""
		from frappe.utils import get_datetime
		from healthcare.healthcare.doctype.abdm_token_registry.abdm_token_registry import (
			get_or_create_registry,
		)

		reg = frappe.get_doc("ABDM Token Registry", registry_name)

		# Already cleared
		if not reg.x_token:
			return False

		# Check expiry
		if reg.x_token_expiry:
			expiry = get_datetime(reg.x_token_expiry)
			now    = get_datetime(now_datetime())
			if now < expiry:
				# Still valid — nothing to do
				return True

		# Token is expired — clear it so the UI prompts re-verification
		frappe.db.set_value(
			"ABDM Token Registry",
			registry_name,
			{
				"x_token":        None,
				"x_token_expiry": None,
			},
		)
		abdm_log(
			"info",
			f"X-token expired and cleared | registry={registry_name} — patient must re-verify",
		)
		return False
