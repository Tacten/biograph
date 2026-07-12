"""
M1-T58: RSA encryption utility for ABHA V3 API calls.

SOP §2 requirement:
- Fetch public key via GET /v3/profile/public/certificate
- Encrypt with RSA/ECB/OAEPWithSHA-1AndMGF1Padding
- Cache public key with TTL (default 24 hours)

This utility is called by abha_client.py before every payload that
contains Aadhaar numbers, OTPs, mobile numbers, or passwords.
"""
import base64
import frappe
from frappe.utils import now_datetime, get_datetime, add_to_date

# RSA key cache TTL in hours
_KEY_CACHE_TTL_HOURS = 24


def get_public_key() -> bytes:
	"""
	Fetch and cache the ABHA V3 RSA public key.
	Reads from ABDM Settings cache; refreshes if expired or missing.
	"""
	settings = frappe.get_single("ABDM Settings")

	# Check if cached key is still valid
	if settings.rsa_public_key_cache and settings.rsa_key_cached_at:
		cache_expiry = add_to_date(get_datetime(settings.rsa_key_cached_at), hours=_KEY_CACHE_TTL_HOURS)
		if get_datetime(now_datetime()) < cache_expiry:
			return settings.rsa_public_key_cache.encode()

	# Fetch fresh public key from ABHA V3 API
	return _refresh_public_key(settings)


def _get_gateway_token_for_cert(settings) -> str:
	"""
	Return a gateway Bearer token for the certificate endpoint.
	Reuses AbhaClient's cache (key: 'abdm:gateway_token') to avoid a redundant
	token fetch. Falls back to fetching fresh if not cached.
	Avoids importing AbhaClient to prevent circular imports.
	"""
	import uuid
	import requests
	from urllib.parse import urlparse
	from datetime import datetime, timezone

	cached = frappe.cache().get_value("abdm:gateway_token")
	if cached:
		return cached

	# Mirror AbhaClient._get_gateway_auth_url logic
	raw = (
		getattr(settings, "auth_base_url", None) or "https://dev.abdm.gov.in/gateway"
	).strip().rstrip("/")
	parsed = urlparse(raw)
	host = f"{parsed.scheme}://{parsed.netloc}"
	auth_url = f"{host}/api/hiecm/gateway/v3/sessions"

	client_id = settings.client_id
	# healthcare.regional.india.abdm stores client_secret as a Password field (encrypted in __Auth).
	client_secret = settings.get_password("client_secret", raise_exception=False)

	if not client_id or not client_secret:
		frappe.throw(
			frappe._("ABDM client_id and client_secret must be configured in ABDM Settings."),
			frappe.ValidationError,
		)

	env = getattr(settings, "environment", None) or "sandbox"
	cm_id = "sbx" if "sand" in env.lower() else "abdm"
	from datetime import datetime, timezone
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
	token = data.get("accessToken", "")
	expires_in = int(data.get("expiresIn", 1200))
	frappe.cache().set_value("abdm:gateway_token", token, expires_in_sec=max(expires_in - 60, 60))
	return token


def _refresh_public_key(settings) -> bytes:
	"""Call GET /v3/profile/public/certificate and cache the result.

	The ABDM V3 API doc §2.0 lists this as a public endpoint, but in practice
	the sandbox requires the same Bearer + X-CM-ID + REQUEST-ID + TIMESTAMP
	headers as every other ABHA V3 endpoint.  We always fetch the gateway token
	first and include all required headers.
	"""
	import uuid
	import re
	import requests
	from datetime import datetime, timezone

	abha_base = (
		getattr(settings, "health_id_base_url", None)
		or getattr(settings, "abha_base_url", None)
		or ""
	).rstrip("/")
	if not abha_base:
		frappe.throw(frappe._("Base URL not configured in ABDM Settings!"), frappe.ValidationError)

	# Strip legacy version suffix (e.g. /v1, /v2) if present
	abha_base = re.sub(r"/v\d+(\.\d+)?$", "", abha_base)

	cert_url = f"{abha_base}/v3/profile/public/certificate"

	env = getattr(settings, "environment", None) or "sandbox"
	cm_id = "sbx" if "sand" in env.lower() else "abdm"

	def _cert_headers(token=None):
		h = {
			"Accept": "application/json",
			"X-CM-ID": cm_id,
			"REQUEST-ID": str(uuid.uuid4()),
			"TIMESTAMP": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
		}
		if token:
			h["Authorization"] = f"Bearer {token}"
		return h

	try:
		# Try unauthenticated with required tracking headers first
		resp = requests.get(cert_url, headers=_cert_headers(), timeout=(5, 8))

		# Sandbox sometimes returns 401 or 404 when auth is actually needed
		if resp.status_code in (401, 403, 404):
			token = _get_gateway_token_for_cert(settings)
			resp = requests.get(cert_url, headers=_cert_headers(token), timeout=10)

		resp.raise_for_status()

		# Response is JSON: {"publicKey": "...", "encryptionAlgorithm": "..."}
		try:
			body = resp.json()
			public_key_pem = body.get("publicKey") or body.get("certificate") or resp.text
		except Exception:
			public_key_pem = resp.text
		public_key_pem = public_key_pem.strip()

		# Cache in ABDM Settings
		frappe.db.set_value(
			"ABDM Settings",
			"ABDM Settings",
			{
				"rsa_public_key_cache": public_key_pem,
				"rsa_key_cached_at": now_datetime(),
			},
		)
		frappe.db.commit()
		return public_key_pem.encode()

	except Exception as e:
		frappe.log_error(f"Failed to fetch ABHA RSA public key: {type(e).__name__}", "ABDM RSA")
		raise


def encrypt_field(value: str) -> str:
	"""
	Encrypt a single field value using RSA/ECB/OAEPWithSHA-1AndMGF1Padding.
	Returns a base64-encoded ciphertext string suitable for ABHA V3 API payloads.

	Usage:
	    encrypted_aadhaar = encrypt_field("123456789012")
	    encrypted_otp = encrypt_field("123456")
	"""
	try:
		from cryptography.hazmat.primitives import hashes, serialization
		from cryptography.hazmat.primitives.asymmetric import padding
		from cryptography.hazmat.backends import default_backend
	except ImportError:
		frappe.throw(
			frappe._("cryptography package not installed. Run: pip install cryptography"),
			frappe.ValidationError,
		)

	public_key_raw = get_public_key()

	# ABDM returns a raw base64-encoded DER public key (no PEM headers).
	# Try DER first, then fall back to PEM in case the value was already wrapped.
	import base64 as _b64
	try:
		# Strip PEM headers/footers if already in PEM format
		raw_str = public_key_raw.decode("utf-8").strip()
		if raw_str.startswith("-----"):
			public_key = serialization.load_pem_public_key(public_key_raw, backend=default_backend())
		else:
			# Raw base64 DER — decode and load as DER
			der_bytes = _b64.b64decode(raw_str)
			public_key = serialization.load_der_public_key(der_bytes, backend=default_backend())
	except Exception:
		# Last-resort: try PEM as-is
		public_key = serialization.load_pem_public_key(public_key_raw, backend=default_backend())

	# Encrypt using OAEP with SHA-1 (as required by ABDM SOP §2)
	ciphertext = public_key.encrypt(
		value.encode("utf-8"),
		padding.OAEP(
			mgf=padding.MGF1(algorithm=hashes.SHA1()),  # noqa: S303 — ABDM mandates SHA-1 here
			algorithm=hashes.SHA1(),  # noqa: S303
			label=None,
		),
	)

	return base64.b64encode(ciphertext).decode("utf-8")
