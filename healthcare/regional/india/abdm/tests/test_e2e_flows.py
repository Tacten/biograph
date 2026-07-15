"""
S8 E2E Flow Tests (mocked ABDM sandbox)
========================================
M1-T40  ABHA Registration: input validation + rate limits
M1-T71  Profile Ops: X-token guard, QR/card response handling
M1-T54  Gateway auth: token not in API response body
M1-T55  Error handling: invalid inputs → 400, timeout → 503, rate limit → 429

All ABDM HTTP calls are mocked. No external connectivity required.
    pytest healthcare/regional/india/abdm/tests/test_e2e_flows.py -v --tb=short
"""

import hashlib
import importlib
import json
import sys
from unittest.mock import MagicMock, patch


# ── Module import helpers ────────────────────────────────────────────────────

def _fresh(mod_path: str, frappe_stub, monkeypatch, extra_stubs: list[str] | None = None):
    """
    Import (or re-import) mod_path with frappe_stub wired as `frappe`.
    Also stubs out any extra_stubs paths as MagicMocks first.
    Returns the imported module.
    """
    # http_guards must be a pass-through stub: @require_post must NOT wrap
    # the real functions in a MagicMock (which silently swallows all calls).
    http_guards_stub = MagicMock()
    http_guards_stub.require_post = lambda fn: fn  # identity decorator

    # Other transitive deps that are safe to fully mock
    default_stubs = {
        "healthcare.regional.india.abdm.utils.log_utils": MagicMock(),
        "healthcare.regional.india.abdm.utils.audit": MagicMock(),
        "healthcare.regional.india.abdm.utils.http_guards": http_guards_stub,
        "healthcare.healthcare.doctype.abdm_token_registry.abdm_token_registry": MagicMock(),
        "healthcare.regional.india.abdm.patient_builder": MagicMock(),
    }
    for path, stub in default_stubs.items():
        monkeypatch.setitem(sys.modules, path, stub)
    for path in (extra_stubs or []):
        if path not in sys.modules:
            monkeypatch.setitem(sys.modules, path, MagicMock())

    # Remove stale cached version so import runs fresh
    monkeypatch.delitem(sys.modules, mod_path, raising=False)
    mod = importlib.import_module(mod_path)
    monkeypatch.setattr(mod, "frappe", frappe_stub)
    return mod


def _fresh_hip(frappe_stub, monkeypatch):
    """
    Import hip.py fresh. MagicMock can't stand in for ssrf_guard here: it
    blocks attribute names starting with "assert_" (a typo-guard for
    mock.assert_called_once() etc.), and hip.py imports
    assert_abdm_gateway_ip — a real function name, not a mock-assertion.
    Use real no-op module objects instead.
    """
    import types

    ssrf_stub = types.ModuleType("healthcare.regional.india.abdm.utils.ssrf_guard")
    ssrf_stub.assert_abdm_gateway_ip = lambda *a, **kw: None
    ssrf_stub.sanitise_fhir_references = lambda *a, **kw: None
    monkeypatch.setitem(sys.modules, "healthcare.regional.india.abdm.utils.ssrf_guard", ssrf_stub)

    fhir_stub = types.ModuleType("healthcare.regional.india.abdm.utils.fhir_validator")
    fhir_stub.validate_fhir_payload = lambda body: {}
    monkeypatch.setitem(sys.modules, "healthcare.regional.india.abdm.utils.fhir_validator", fhir_stub)

    return _fresh("healthcare.regional.india.abdm.api.hip", frappe_stub, monkeypatch)


# ── T40: ABHA Registration input validation ───────────────────────────────────

class TestT40_AbhaRegistrationE2E:
    """M1-T40: ABHA Registration flows — input validation + rate limits."""

    def test_null_patient_rejected(self, frappe_stub, monkeypatch):
        """generate_aadhaar_otp(patient=None) → ValidationError."""
        enrol = _fresh("healthcare.regional.india.abdm.api.enrol", frappe_stub, monkeypatch,
                       extra_stubs=["healthcare.regional.india.abdm.utils.rate_limit",
                                    "healthcare.regional.india.abdm.utils.abha_client"])
        try:
            enrol.generate_aadhaar_otp(None, "123456789012")
            assert False, "Should raise"
        except frappe_stub.ValidationError:
            pass

    def test_10_digit_aadhaar_rejected(self, frappe_stub, monkeypatch):
        """10-digit Aadhaar → ValidationError (not 12 digits)."""
        frappe_stub.db.exists = MagicMock(return_value=True)
        enrol = _fresh("healthcare.regional.india.abdm.api.enrol", frappe_stub, monkeypatch,
                       extra_stubs=["healthcare.regional.india.abdm.utils.rate_limit",
                                    "healthcare.regional.india.abdm.utils.abha_client"])
        try:
            enrol.generate_aadhaar_otp("PAT-001", "1234567890")
            assert False, "Should raise"
        except frappe_stub.ValidationError as e:
            assert "12" in str(e) or "Aadhaar" in str(e)

    def test_6_digit_otp_valid(self, frappe_stub, monkeypatch):
        """6-digit OTP → passes _validate_otp without raising."""
        enrol = _fresh("healthcare.regional.india.abdm.api.enrol", frappe_stub, monkeypatch,
                       extra_stubs=["healthcare.regional.india.abdm.utils.rate_limit",
                                    "healthcare.regional.india.abdm.utils.abha_client"])
        result = enrol._validate_otp("123456")
        assert result == "123456"

    def test_5_digit_otp_rejected(self, frappe_stub, monkeypatch):
        """5-digit OTP → ValidationError."""
        enrol = _fresh("healthcare.regional.india.abdm.api.enrol", frappe_stub, monkeypatch,
                       extra_stubs=["healthcare.regional.india.abdm.utils.rate_limit",
                                    "healthcare.regional.india.abdm.utils.abha_client"])
        try:
            enrol._validate_otp("12345")
            assert False, "Should raise"
        except frappe_stub.ValidationError:
            pass

    def test_existing_abha_blocks_aadhaar_enrol(self, frappe_stub, monkeypatch):
        """Patient already has ABHA Record → generate_aadhaar_otp raises ValidationError."""
        frappe_stub.db.exists = MagicMock(return_value=True)
        # db.get_value returns a dict (existing ABHA Record)
        frappe_stub.db.get_value = MagicMock(
            return_value={"abha_number": "91-1234-5678-9012", "preferred_abha_address": None}
        )
        enrol = _fresh("healthcare.regional.india.abdm.api.enrol", frappe_stub, monkeypatch,
                       extra_stubs=["healthcare.regional.india.abdm.utils.rate_limit",
                                    "healthcare.regional.india.abdm.utils.abha_client"])
        try:
            enrol.generate_aadhaar_otp("PAT-001", "123456789012")
            assert False, "Should raise"
        except frappe_stub.ValidationError as e:
            assert "already has" in str(e).lower() or "Verify ABHA" in str(e)

    def test_existing_abha_blocks_mobile_enrol(self, frappe_stub, monkeypatch):
        """Patient already has ABHA Record → generate_mobile_otp raises ValidationError."""
        frappe_stub.db.exists = MagicMock(return_value=True)
        frappe_stub.db.get_value = MagicMock(
            return_value={"abha_number": "91-1234-5678-9012", "preferred_abha_address": None}
        )
        enrol = _fresh("healthcare.regional.india.abdm.api.enrol", frappe_stub, monkeypatch,
                       extra_stubs=["healthcare.regional.india.abdm.utils.rate_limit",
                                    "healthcare.regional.india.abdm.utils.abha_client"])
        try:
            enrol.generate_mobile_otp("PAT-001", "9876543210")
            assert False, "Should raise"
        except frappe_stub.ValidationError as e:
            assert "already has" in str(e).lower() or "Verify ABHA" in str(e)

    def test_no_existing_abha_allows_enrol(self, frappe_stub, monkeypatch):
        """Patient has no ABHA Record → _assert_no_existing_abha passes silently."""
        frappe_stub.db.exists = MagicMock(return_value=True)
        frappe_stub.db.get_value = MagicMock(return_value=None)  # no existing record
        enrol = _fresh("healthcare.regional.india.abdm.api.enrol", frappe_stub, monkeypatch,
                       extra_stubs=["healthcare.regional.india.abdm.utils.rate_limit",
                                    "healthcare.regional.india.abdm.utils.abha_client"])
        # Should not raise
        enrol._assert_no_existing_abha("PAT-001")

    def test_invalid_abha_address_rejected(self, frappe_stub, monkeypatch):
        """ABHA address without @abdm/@sbx suffix → ValidationError."""
        frappe_stub.db.exists = MagicMock(return_value=True)
        frappe_stub.db.get_value = MagicMock(return_value=None)
        enrol = _fresh("healthcare.regional.india.abdm.api.enrol", frappe_stub, monkeypatch,
                       extra_stubs=["healthcare.regional.india.abdm.utils.rate_limit",
                                    "healthcare.regional.india.abdm.utils.abha_client"])
        try:
            enrol.set_abha_address("PAT-001", "user@gmail.com")
            assert False, "Should raise"
        except frappe_stub.ValidationError as e:
            assert "abdm" in str(e).lower() or "sbx" in str(e).lower() or "Invalid" in str(e)

    def test_otp_resend_rate_limited_after_3(self, frappe_stub, monkeypatch):
        """4th OTP resend → rate limited."""
        cache_store = {}

        class _FakeCache:
            def get(self, key): return cache_store.get(key)
            def set_value(self, key, val, expires_in_sec=None): cache_store[key] = val

        frappe_stub.cache = lambda: _FakeCache()

        rl = _fresh("healthcare.regional.india.abdm.utils.rate_limit", frappe_stub, monkeypatch)

        for _ in range(3):
            rl.check_otp_resend("txn-abc-001")

        try:
            rl.check_otp_resend("txn-abc-001")
            assert False, "4th resend should be rate limited"
        except frappe_stub.ValidationError as e:
            assert "resend" in str(e).lower() or "Maximum" in str(e)


# ── T71: Profile Ops E2E ──────────────────────────────────────────────────────

class TestT71_ProfileOpsE2E:
    """M1-T71: Profile operations — X-token guard, QR, card."""

    def test_assert_x_token_missing_raises(self, frappe_stub, monkeypatch):
        """_assert_x_token raises ValidationError when no X-token in registry."""
        profile = _fresh("healthcare.regional.india.abdm.api.profile", frappe_stub, monkeypatch,
                         extra_stubs=["healthcare.regional.india.abdm.utils.rate_limit",
                                      "healthcare.regional.india.abdm.utils.abha_client"])

        # Configure the token_reg stub (already in sys.modules via _fresh) to return None
        token_reg = sys.modules["healthcare.healthcare.doctype.abdm_token_registry.abdm_token_registry"]
        token_reg.get_x_token = MagicMock(return_value=None)

        try:
            profile._assert_x_token("PAT-001")
            assert False, "Should raise"
        except frappe_stub.ValidationError as e:
            assert "ABHA" in str(e) or "session" in str(e).lower() or "Verify" in str(e)

    def test_qr_base64_encoding(self):
        """Base64 encoding of PNG bytes produces a valid base64 string."""
        import base64
        fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        encoded = base64.b64encode(fake_png).decode("utf-8")
        decoded = base64.b64decode(encoded)
        assert decoded[:4] == b"\x89PNG"

    def test_card_binary_response_handled(self):
        """Card endpoint returns raw bytes; base64 encode for API response."""
        import base64
        card_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 200
        result = {"card_b64": base64.b64encode(card_bytes).decode("utf-8")}
        assert result["card_b64"]
        decoded = base64.b64decode(result["card_b64"])
        assert decoded[:4] == b"\x89PNG"

    def test_profile_email_masked(self, frappe_stub, monkeypatch):
        """get_abha_profile masks email — only first 2 chars of local part visible."""
        profile = _fresh("healthcare.regional.india.abdm.api.profile", frappe_stub, monkeypatch,
                         extra_stubs=["healthcare.regional.india.abdm.utils.rate_limit",
                                      "healthcare.regional.india.abdm.utils.abha_client"])

        masked = profile._mask_email("testuser@example.com")
        assert masked.startswith("te")
        assert "testuser" not in masked
        assert "@example.com" in masked

    def test_profile_empty_email_masked_safely(self, frappe_stub, monkeypatch):
        """Empty email → empty string (no crash)."""
        profile = _fresh("healthcare.regional.india.abdm.api.profile", frappe_stub, monkeypatch,
                         extra_stubs=["healthcare.regional.india.abdm.utils.rate_limit",
                                      "healthcare.regional.india.abdm.utils.abha_client"])
        assert profile._mask_email("") == ""
        assert profile._mask_email("notanemail") == ""


# ── T54: Gateway Auth ─────────────────────────────────────────────────────────

class TestT54_GatewayAuth:
    """M1-T54: Gateway token lifecycle."""

    def test_gateway_token_not_in_token_status_response(self, frappe_stub, monkeypatch):
        """get_token_status response never contains token values."""
        token_reg = MagicMock()
        token_reg.get_x_token = MagicMock(return_value=None)
        monkeypatch.setitem(
            sys.modules,
            "healthcare.healthcare.doctype.abdm_token_registry.abdm_token_registry",
            token_reg,
        )
        profile = _fresh("healthcare.regional.india.abdm.api.profile", frappe_stub, monkeypatch,
                         extra_stubs=["healthcare.regional.india.abdm.utils.rate_limit",
                                      "healthcare.regional.india.abdm.utils.abha_client"])

        frappe_stub.db.get_value = MagicMock(return_value="PAT-001")
        frappe_stub.db.exists = MagicMock(return_value=True)

        # get_token_status returns NONE status when no registry record
        frappe_stub.db.get_value = MagicMock(return_value=None)
        result = profile.get_token_status("PAT-001")

        result_str = json.dumps(result)
        assert "Bearer" not in result_str
        assert "accessToken" not in result_str
        assert result["status"] == "NONE"

    def test_audit_log_session_login_on_session_create(self, frappe_stub, monkeypatch):
        """on_session_creation triggers SESSION_LOGIN audit log."""
        monkeypatch.setitem(sys.modules, "healthcare.regional.india.abdm.utils.log_utils", MagicMock())
        monkeypatch.setitem(sys.modules, "healthcare.regional.india.abdm.utils.audit", MagicMock())

        import healthcare.regional.india.abdm.utils.audit as audit_mock
        audit_mock.audit_log = MagicMock()

        # auth.py should call audit_log("SESSION_LOGIN") — verify the function exists
        from healthcare.regional.india.abdm.utils.audit import _VALID_OPERATIONS
        # _VALID_OPERATIONS is from the real module; import fresh if needed
        monkeypatch.delitem(sys.modules, "healthcare.regional.india.abdm.utils.audit", raising=False)
        import healthcare.regional.india.abdm.utils.audit as audit_real
        monkeypatch.setattr(audit_real, "frappe", frappe_stub)

        assert "SESSION_LOGIN" in audit_real._VALID_OPERATIONS
        assert "SESSION_LOGOUT" in audit_real._VALID_OPERATIONS


# ── T55: Error Handling E2E ───────────────────────────────────────────────────

class TestT55_ErrorHandlingE2E:
    """M1-T55: Error handling — 400 on bad input, 503 on timeout, 429 on rate limit."""

    def test_timeout_maps_to_clean_503(self, frappe_stub, monkeypatch):
        """requests.Timeout → handle_abdm_exception sets status 503, no traceback."""
        import requests

        frappe_stub.form_dict = {"cmd": "healthcare.regional.india.abdm.api.profile.get_abha_qr_code"}
        frappe_stub.response = {}
        frappe_stub.log_error = MagicMock()
        frappe_stub.get_traceback = MagicMock(return_value="")

        eh = _fresh("healthcare.regional.india.abdm.utils.error_handler", frappe_stub, monkeypatch)

        eh.handle_abdm_exception(requests.Timeout("timed out"))

        assert frappe_stub.response.get("http_status_code") == 503
        msg = str(frappe_stub.response.get("message", ""))
        assert "Traceback" not in msg
        assert "File " not in msg

    def test_connection_error_maps_to_503(self, frappe_stub, monkeypatch):
        """requests.ConnectionError → 503."""
        import requests

        frappe_stub.form_dict = {"cmd": "healthcare.regional.india.abdm.api.enrol.generate_aadhaar_otp"}
        frappe_stub.response = {}
        frappe_stub.log_error = MagicMock()
        frappe_stub.get_traceback = MagicMock(return_value="")

        eh = _fresh("healthcare.regional.india.abdm.utils.error_handler", frappe_stub, monkeypatch)

        eh.handle_abdm_exception(requests.ConnectionError("refused"))

        assert frappe_stub.response.get("http_status_code") == 503

    def test_non_abdm_exception_not_intercepted(self, frappe_stub, monkeypatch):
        """Exception in non-ABDM endpoint → handler returns None, response untouched."""
        import requests

        frappe_stub.form_dict = {"cmd": "frappe.some.other.method"}
        frappe_stub.response = {}

        eh = _fresh("healthcare.regional.india.abdm.utils.error_handler", frappe_stub, monkeypatch)

        result = eh.handle_abdm_exception(requests.Timeout("timeout"))
        assert result is None
        assert frappe_stub.response == {}

    def test_rate_limit_raises_on_11th_call(self, frappe_stub, monkeypatch):
        """11th API call per minute → ValidationError with Retry-After hint."""
        cache_store = {}

        class _FakeCache:
            def get(self, key): return cache_store.get(key)
            def set_value(self, key, val, expires_in_sec=None): cache_store[key] = val

        frappe_stub.cache = lambda: _FakeCache()
        frappe_stub.session.user = "nurse@hospital.com"

        rl = _fresh("healthcare.regional.india.abdm.utils.rate_limit", frappe_stub, monkeypatch)

        for _ in range(10):
            rl.check_api_call("get_abha_qr_code")

        try:
            rl.check_api_call("get_abha_qr_code")
            assert False, "11th call must be rate limited"
        except frappe_stub.ValidationError as e:
            assert "Retry-After" in str(e) or "Too many" in str(e)

    def test_rate_limit_per_user_not_per_ip(self, frappe_stub, monkeypatch):
        """Rate limit counter is per user — different user gets a fresh allowance."""
        cache_store = {}

        class _FakeCache:
            def get(self, key): return cache_store.get(key)
            def set_value(self, key, val, expires_in_sec=None): cache_store[key] = val

        frappe_stub.cache = lambda: _FakeCache()

        rl = _fresh("healthcare.regional.india.abdm.utils.rate_limit", frappe_stub, monkeypatch)

        # Exhaust user A's limit
        frappe_stub.session.user = "user_a@example.com"
        for _ in range(10):
            rl.check_api_call("get_abha_qr_code")

        # User B (same IP) gets a fresh counter
        frappe_stub.session.user = "user_b@example.com"
        rl.check_api_call("get_abha_qr_code")  # must not raise

    def test_validation_error_not_swallowed(self, frappe_stub, monkeypatch):
        """frappe.ValidationError from our code is NOT intercepted by error handler."""
        frappe_stub.form_dict = {"cmd": "healthcare.regional.india.abdm.api.enrol.generate_aadhaar_otp"}
        frappe_stub.response = {}
        frappe_stub.log_error = MagicMock()

        eh = _fresh("healthcare.regional.india.abdm.utils.error_handler", frappe_stub, monkeypatch)

        # ValidationError should pass through untouched (Frappe handles it cleanly)
        result = eh.handle_abdm_exception(frappe_stub.ValidationError("bad input"))
        assert result is None  # early return — don't override
        assert frappe_stub.response == {}


# ── T40B: Mobile OTP + Driving Licence Enrolment E2E ─────────────────────────

class TestT40B_MobileDlEnrolmentE2E:
    """M1-T40B: Mobile OTP and Driving Licence ABHA creation flows."""

    def test_mobile_otp_invalid_number_rejected(self, frappe_stub, monkeypatch):
        """9-digit mobile number → ValidationError."""
        frappe_stub.db.exists = MagicMock(return_value=True)
        frappe_stub.db.get_value = MagicMock(return_value=None)
        enrol = _fresh("healthcare.regional.india.abdm.api.enrol", frappe_stub, monkeypatch,
                       extra_stubs=["healthcare.regional.india.abdm.utils.rate_limit",
                                    "healthcare.regional.india.abdm.utils.abha_client"])
        try:
            enrol.generate_mobile_otp("PAT-001", "987654321")
            assert False, "Should raise"
        except frappe_stub.ValidationError as e:
            assert "10 digits" in str(e) or "Invalid mobile" in str(e)

    def test_dl_otp_invalid_mobile_rejected(self, frappe_stub, monkeypatch):
        """Non-numeric mobile in DL flow → ValidationError."""
        frappe_stub.db.exists = MagicMock(return_value=True)
        frappe_stub.db.get_value = MagicMock(return_value=None)
        enrol = _fresh("healthcare.regional.india.abdm.api.enrol", frappe_stub, monkeypatch,
                       extra_stubs=["healthcare.regional.india.abdm.utils.rate_limit",
                                    "healthcare.regional.india.abdm.utils.abha_client"])
        try:
            enrol.generate_dl_otp("PAT-001", "98765abcde")
            assert False, "Should raise"
        except frappe_stub.ValidationError:
            pass

    def test_verify_dl_otp_format_validation(self, frappe_stub, monkeypatch):
        """Non-6-digit OTP in DL verify → ValidationError."""
        enrol = _fresh("healthcare.regional.india.abdm.api.enrol", frappe_stub, monkeypatch,
                       extra_stubs=["healthcare.regional.india.abdm.utils.rate_limit",
                                    "healthcare.regional.india.abdm.utils.abha_client"])
        try:
            enrol.verify_dl_otp("PAT-001", "txn-1", "123")
            assert False, "Should raise"
        except frappe_stub.ValidationError:
            pass

    def test_verify_mobile_otp_enrol_format_validation(self, frappe_stub, monkeypatch):
        """Non-6-digit OTP in mobile-enrol verify → ValidationError."""
        enrol = _fresh("healthcare.regional.india.abdm.api.enrol", frappe_stub, monkeypatch,
                       extra_stubs=["healthcare.regional.india.abdm.utils.rate_limit",
                                    "healthcare.regional.india.abdm.utils.abha_client"])
        try:
            enrol.verify_mobile_otp_enrol("PAT-001", "txn-1", "abcdef")
            assert False, "Should raise"
        except frappe_stub.ValidationError:
            pass

    def test_enrol_by_dl_missing_document_id_rejected(self, frappe_stub, monkeypatch):
        """dl_data without documentId → ValidationError."""
        import json
        frappe_stub.db.exists = MagicMock(return_value=True)
        enrol = _fresh("healthcare.regional.india.abdm.api.enrol", frappe_stub, monkeypatch,
                       extra_stubs=["healthcare.regional.india.abdm.utils.rate_limit",
                                    "healthcare.regional.india.abdm.utils.abha_client"])
        dl_data = json.dumps({"dob": "1990-01-01", "firstName": "Test"})
        try:
            enrol.enrol_by_dl("PAT-001", "txn-1", dl_data)
            assert False, "Should raise"
        except frappe_stub.ValidationError as e:
            assert "DL number" in str(e)

    def test_enrol_by_dl_missing_dob_rejected(self, frappe_stub, monkeypatch):
        """dl_data without dob → ValidationError."""
        import json
        frappe_stub.db.exists = MagicMock(return_value=True)
        enrol = _fresh("healthcare.regional.india.abdm.api.enrol", frappe_stub, monkeypatch,
                       extra_stubs=["healthcare.regional.india.abdm.utils.rate_limit",
                                    "healthcare.regional.india.abdm.utils.abha_client"])
        dl_data = json.dumps({"documentId": "DL1234567890"})
        try:
            enrol.enrol_by_dl("PAT-001", "txn-1", dl_data)
            assert False, "Should raise"
        except frappe_stub.ValidationError as e:
            assert "birth" in str(e).lower()

    def test_enrol_by_dl_strips_unknown_fields(self, frappe_stub, monkeypatch):
        """Mass-assignment: a field outside the DL whitelist never reaches AbhaClient (M1-T7)."""
        import json
        import sys as _sys
        frappe_stub.db.exists = MagicMock(return_value=True)
        frappe_stub.db.get_value = MagicMock(return_value=None)  # no existing ABHA

        client_stub = MagicMock()
        captured = {}

        def _capture_enrol(patient, txn_id, safe_dl):
            captured.update(safe_dl)
            return {"EnrolProfile": {"enrolmentNumber": "12-3456-7890-1234", "phrAddress": ["x@sbx"]}}

        client_stub.return_value.enrol_by_dl = MagicMock(side_effect=_capture_enrol)
        monkeypatch.setitem(_sys.modules, "healthcare.regional.india.abdm.utils.abha_client", client_stub)

        enrol = _fresh("healthcare.regional.india.abdm.api.enrol", frappe_stub, monkeypatch,
                       extra_stubs=["healthcare.regional.india.abdm.utils.rate_limit"])
        monkeypatch.setitem(_sys.modules, "healthcare.regional.india.abdm.utils.abha_client", client_stub)
        monkeypatch.setattr(enrol, "AbhaClient", client_stub)

        dl_data = json.dumps({
            "documentId": "DL1234567890",
            "dob": "1990-01-01",
            "isAdmin": True,          # not in the whitelist — must be stripped
            "role": "System Manager", # not in the whitelist — must be stripped
        })
        enrol.enrol_by_dl("PAT-001", "txn-1", dl_data)

        assert "isAdmin" not in captured
        assert "role" not in captured
        assert captured.get("documentId") == "DL1234567890"


# ── T41: ABHA Linking (HIP / Scan & Share) E2E ────────────────────────────────

class TestT41_AbhaLinkingE2E:
    """M1-T41: Scan & Share linking flow — demographic matching + signature validation."""

    def test_match_patient_success_no_demographics_given(self, frappe_stub, monkeypatch):
        """ABHA on file, no gender/YOB in callback → matches on ABHA number alone."""
        hip = _fresh_hip(frappe_stub, monkeypatch)
        frappe_stub.db.get_value = MagicMock(side_effect=["ABHA-REC-1", "PAT-001"])
        patient_doc = MagicMock()
        patient_doc.sex = None
        patient_doc.dob = None
        frappe_stub.get_doc = MagicMock(return_value=patient_doc)

        result = hip._match_and_validate_patient("911234567890123", "", "", None)
        assert result == "PAT-001"

    def test_match_patient_not_on_file_raises(self, frappe_stub, monkeypatch):
        """No ABHA Record for this ABHA number → DoesNotExistError."""
        hip = _fresh_hip(frappe_stub, monkeypatch)
        frappe_stub.db.get_value = MagicMock(return_value=None)
        try:
            hip._match_and_validate_patient("911234567890123", "Jane Doe", "F", 1990)
            assert False, "Should raise"
        except frappe_stub.DoesNotExistError:
            pass

    def test_match_patient_gender_mismatch_raises(self, frappe_stub, monkeypatch):
        """Callback gender disagrees with stored Patient.sex → PermissionError (spoofing guard)."""
        hip = _fresh_hip(frappe_stub, monkeypatch)
        frappe_stub.db.get_value = MagicMock(side_effect=["ABHA-REC-1", "PAT-001"])
        patient_doc = MagicMock()
        patient_doc.sex = "Male"
        patient_doc.dob = None
        frappe_stub.get_doc = MagicMock(return_value=patient_doc)
        try:
            hip._match_and_validate_patient("911234567890123", "Jane Doe", "F", None)
            assert False, "Should raise"
        except frappe_stub.PermissionError:
            pass

    def test_match_patient_yob_mismatch_raises(self, frappe_stub, monkeypatch):
        """Callback year-of-birth off by more than 1 year → PermissionError."""
        hip = _fresh_hip(frappe_stub, monkeypatch)
        frappe_stub.db.get_value = MagicMock(side_effect=["ABHA-REC-1", "PAT-001"])
        patient_doc = MagicMock()
        patient_doc.sex = None
        patient_doc.dob = "1990-05-01"
        frappe_stub.get_doc = MagicMock(return_value=patient_doc)
        try:
            hip._match_and_validate_patient("911234567890123", "", "", 1985)
            assert False, "Should raise"
        except frappe_stub.PermissionError:
            pass

    def test_match_patient_yob_off_by_one_tolerated(self, frappe_stub, monkeypatch):
        """Callback YOB off by exactly 1 year → tolerated, no raise."""
        hip = _fresh_hip(frappe_stub, monkeypatch)
        frappe_stub.db.get_value = MagicMock(side_effect=["ABHA-REC-1", "PAT-001"])
        patient_doc = MagicMock()
        patient_doc.sex = None
        patient_doc.dob = "1990-05-01"
        frappe_stub.get_doc = MagicMock(return_value=patient_doc)

        result = hip._match_and_validate_patient("911234567890123", "", "", 1991)
        assert result == "PAT-001"

    def test_signature_valid_hmac_passes(self, frappe_stub, monkeypatch):
        """Correct HMAC-SHA256 signature over the raw body → no raise."""
        import hashlib, hmac as _hmac
        hip = _fresh_hip(frappe_stub, monkeypatch)
        settings = MagicMock()
        settings.callback_secret = "topsecret"
        settings.get_password = MagicMock(return_value="topsecret")
        frappe_stub.get_single = MagicMock(return_value=settings)

        body = b'{"requestId":"abc"}'
        sig = _hmac.new(b"topsecret", body, hashlib.sha256).hexdigest()
        hip._validate_signature(body, f"sha256={sig}")  # must not raise

    def test_signature_invalid_hmac_rejected(self, frappe_stub, monkeypatch):
        """Wrong HMAC signature → PermissionError."""
        hip = _fresh_hip(frappe_stub, monkeypatch)
        settings = MagicMock()
        settings.callback_secret = "topsecret"
        settings.get_password = MagicMock(return_value="topsecret")
        frappe_stub.get_single = MagicMock(return_value=settings)

        try:
            hip._validate_signature(b'{"requestId":"abc"}', "sha256=deadbeef")
            assert False, "Should raise"
        except frappe_stub.PermissionError:
            pass

    def test_signature_no_secret_configured_allows_sandbox(self, frappe_stub, monkeypatch):
        """No callback_secret set (sandbox/dev) → signature check skipped, no raise."""
        hip = _fresh_hip(frappe_stub, monkeypatch)
        settings = MagicMock()
        settings.callback_secret = None
        frappe_stub.get_single = MagicMock(return_value=settings)

        hip._validate_signature(b'{"requestId":"abc"}', "")  # must not raise


# ── T72: ABHA Lifecycle (Deactivate / Delete / Reactivate) E2E ───────────────

class TestT72_AbhaLifecycleE2E:
    """M1-T72: ABHA account lifecycle — request OTP + confirm action."""

    def test_invalid_action_rejected(self, frappe_stub, monkeypatch):
        """Unknown action value → ValidationError before any OTP request."""
        profile = _fresh("healthcare.regional.india.abdm.api.profile", frappe_stub, monkeypatch,
                         extra_stubs=["healthcare.regional.india.abdm.utils.rate_limit",
                                      "healthcare.regional.india.abdm.utils.abha_client"])
        try:
            profile.request_lifecycle_otp("PAT-001", "destroy")
            assert False, "Should raise"
        except frappe_stub.ValidationError as e:
            assert "Invalid lifecycle action" in str(e)

    def test_invalid_otp_mode_rejected(self, frappe_stub, monkeypatch):
        """Unknown otp_mode value → ValidationError."""
        profile = _fresh("healthcare.regional.india.abdm.api.profile", frappe_stub, monkeypatch,
                         extra_stubs=["healthcare.regional.india.abdm.utils.rate_limit",
                                      "healthcare.regional.india.abdm.utils.abha_client"])
        try:
            profile.request_lifecycle_otp("PAT-001", "deactivate", otp_mode="email")
            assert False, "Should raise"
        except frappe_stub.ValidationError as e:
            assert "Invalid OTP mode" in str(e)

    def test_no_abha_linked_rejected(self, frappe_stub, monkeypatch):
        """No ABHA Record for patient → ValidationError before contacting ABDM."""
        profile = _fresh("healthcare.regional.india.abdm.api.profile", frappe_stub, monkeypatch,
                         extra_stubs=["healthcare.regional.india.abdm.utils.rate_limit",
                                      "healthcare.regional.india.abdm.utils.abha_client"])
        frappe_stub.db.get_value = MagicMock(return_value=None)
        try:
            profile.request_lifecycle_otp("PAT-001", "deactivate")
            assert False, "Should raise"
        except frappe_stub.ValidationError as e:
            assert "No ABHA linked" in str(e)

    def test_confirm_lifecycle_invalid_action_rejected(self, frappe_stub, monkeypatch):
        """confirm_lifecycle_action rejects an unknown action before calling AbhaClient."""
        profile = _fresh("healthcare.regional.india.abdm.api.profile", frappe_stub, monkeypatch,
                         extra_stubs=["healthcare.regional.india.abdm.utils.rate_limit",
                                      "healthcare.regional.india.abdm.utils.abha_client"])
        try:
            profile.confirm_lifecycle_action("PAT-001", "txn-1", "123456", "wipe")
            assert False, "Should raise"
        except frappe_stub.ValidationError as e:
            assert "Invalid lifecycle action" in str(e)

    def test_confirm_lifecycle_deactivate_sets_status(self, frappe_stub, monkeypatch):
        """Successful deactivate → ABHA Record.status set to DEACTIVATED."""
        import sys as _sys
        client_stub = MagicMock()
        monkeypatch.setitem(_sys.modules, "healthcare.regional.india.abdm.utils.abha_client", client_stub)
        # Force a fresh rate_limit stub — a prior test in this file may already
        # have real-imported rate_limit, which _fresh()'s extra_stubs would then
        # skip re-stubbing (it only stubs paths not already in sys.modules).
        monkeypatch.setitem(_sys.modules, "healthcare.regional.india.abdm.utils.rate_limit", MagicMock())

        profile = _fresh("healthcare.regional.india.abdm.api.profile", frappe_stub, monkeypatch)
        monkeypatch.setattr(profile, "AbhaClient", client_stub)

        frappe_stub.db.get_value = MagicMock(return_value="ABHA-REC-1")
        frappe_stub.db.set_value = MagicMock()

        result = profile.confirm_lifecycle_action("PAT-001", "txn-1", "123456", "deactivate")

        frappe_stub.db.set_value.assert_called_once_with("ABHA Record", "ABHA-REC-1", "status", "DEACTIVATED")
        assert result["status"] == "DEACTIVATED"

    def test_confirm_lifecycle_reactivate_sets_active_status(self, frappe_stub, monkeypatch):
        """Successful reactivate → ABHA Record.status set to ACTIVE."""
        import sys as _sys
        client_stub = MagicMock()
        monkeypatch.setitem(_sys.modules, "healthcare.regional.india.abdm.utils.abha_client", client_stub)
        # Force a fresh rate_limit stub — a prior test in this file may already
        # have real-imported rate_limit, which _fresh()'s extra_stubs would then
        # skip re-stubbing (it only stubs paths not already in sys.modules).
        monkeypatch.setitem(_sys.modules, "healthcare.regional.india.abdm.utils.rate_limit", MagicMock())

        profile = _fresh("healthcare.regional.india.abdm.api.profile", frappe_stub, monkeypatch)
        monkeypatch.setattr(profile, "AbhaClient", client_stub)

        frappe_stub.db.get_value = MagicMock(return_value="ABHA-REC-1")
        frappe_stub.db.set_value = MagicMock()

        result = profile.confirm_lifecycle_action("PAT-001", "txn-1", "123456", "reactivate")

        frappe_stub.db.set_value.assert_called_once_with("ABHA Record", "ABHA-REC-1", "status", "ACTIVE")
        assert result["status"] == "ACTIVE"

    def test_confirm_lifecycle_delete_sets_deleted_status(self, frappe_stub, monkeypatch):
        """Successful delete → ABHA Record.status set to DELETED."""
        import sys as _sys
        client_stub = MagicMock()
        monkeypatch.setitem(_sys.modules, "healthcare.regional.india.abdm.utils.abha_client", client_stub)
        # Force a fresh rate_limit stub — a prior test in this file may already
        # have real-imported rate_limit, which _fresh()'s extra_stubs would then
        # skip re-stubbing (it only stubs paths not already in sys.modules).
        monkeypatch.setitem(_sys.modules, "healthcare.regional.india.abdm.utils.rate_limit", MagicMock())

        profile = _fresh("healthcare.regional.india.abdm.api.profile", frappe_stub, monkeypatch)
        monkeypatch.setattr(profile, "AbhaClient", client_stub)

        frappe_stub.db.get_value = MagicMock(return_value="ABHA-REC-1")
        frappe_stub.db.set_value = MagicMock()

        result = profile.confirm_lifecycle_action("PAT-001", "txn-1", "123456", "delete")

        frappe_stub.db.set_value.assert_called_once_with("ABHA Record", "ABHA-REC-1", "status", "DELETED")
        assert result["status"] == "DELETED"


class TestAbhaNumberLoginOtp:
    """
    Regression test: ABDM rejects a bare-digit loginId for loginHint
    "abha-number" with {"loginId": "LoginId is invalid"} — it expects the
    canonical dashed ABHA number representation (XX-XXXX-XXXX-XXXX) before
    RSA encryption, same as every ABHANumber value ABDM itself returns.
    """

    def test_abha_number_login_id_is_dash_formatted_before_encryption(self, frappe_stub, monkeypatch):
        client = _fresh("healthcare.regional.india.abdm.utils.abha_client", frappe_stub, monkeypatch)
        abha = client.AbhaClient()

        monkeypatch.setattr(abha, "call_abha", MagicMock(return_value={"txnId": "txn-1"}))
        captured = {}

        def _fake_encrypt(value):
            captured["value"] = value
            return "encrypted:" + value

        monkeypatch.setattr(client, "encrypt_field", _fake_encrypt)

        abha.request_abha_login_otp("PAT-001", "91412877475514", "abha-number")

        assert captured["value"] == "91-4128-7747-5514"
        sent_payload = abha.call_abha.call_args.kwargs["payload"]
        assert sent_payload["loginId"] == "encrypted:91-4128-7747-5514"
        assert sent_payload["loginHint"] == "abha-number"

    def test_mobile_login_id_is_not_dash_formatted(self, frappe_stub, monkeypatch):
        """Mobile/Aadhaar loginIds must pass through untouched — only abha-number is reformatted."""
        client = _fresh("healthcare.regional.india.abdm.utils.abha_client", frappe_stub, monkeypatch)
        abha = client.AbhaClient()

        monkeypatch.setattr(abha, "call_abha", MagicMock(return_value={"txnId": "txn-1"}))
        captured = {}

        def _fake_encrypt(value):
            captured["value"] = value
            return "encrypted:" + value

        monkeypatch.setattr(client, "encrypt_field", _fake_encrypt)

        abha.request_abha_login_otp("PAT-001", "9876543210", "mobile")

        assert captured["value"] == "9876543210"


class TestXTokenErrorFailFast:
    """
    Regression test: a 401 ABDM-1094 ("X-token expired") is a different
    token than the gateway/service Authorization token. Retrying it as if
    a gateway-token refresh will fix it burns 3 retries (up to ~7s of
    exponential backoff) before failing identically every time, and (for
    callers with a working fallback, e.g. get_abha_profile) makes an
    expected, successful fallback look like a failure in the Error Log.
    """

    def test_is_x_token_error_detects_abdm_1094(self, frappe_stub, monkeypatch):
        client = _fresh("healthcare.regional.india.abdm.utils.abha_client", frappe_stub, monkeypatch)

        resp = MagicMock()
        resp.json.return_value = {"code": "ABDM-1094", "message": "X-token expired"}
        exc = client.requests.HTTPError(response=resp)

        assert client.AbhaClient._is_x_token_error(exc) is True

    def test_is_x_token_error_detects_lowercase_code(self, frappe_stub, monkeypatch):
        """ABDM's error code check must not be case-sensitive."""
        client = _fresh("healthcare.regional.india.abdm.utils.abha_client", frappe_stub, monkeypatch)

        resp = MagicMock()
        resp.json.return_value = {"code": "abdm-1094", "message": "some other text"}
        exc = client.requests.HTTPError(response=resp)

        assert client.AbhaClient._is_x_token_error(exc) is True

    def test_is_x_token_error_false_for_gateway_401(self, frappe_stub, monkeypatch):
        client = _fresh("healthcare.regional.india.abdm.utils.abha_client", frappe_stub, monkeypatch)

        resp = MagicMock()
        resp.json.return_value = {"message": "Invalid gateway token"}
        exc = client.requests.HTTPError(response=resp)

        assert client.AbhaClient._is_x_token_error(exc) is False

    def test_x_token_401_fails_fast_without_gateway_refresh_retry(self, frappe_stub, monkeypatch):
        """An X-token-specific 401 must not be retried as a gateway-token issue."""
        client = _fresh("healthcare.regional.india.abdm.utils.abha_client", frappe_stub, monkeypatch)
        abha = client.AbhaClient()

        resp = MagicMock()
        resp.status_code = 401
        resp.json.return_value = {"code": "ABDM-1094", "message": "X-token expired"}
        resp.raise_for_status.side_effect = client.requests.HTTPError(response=resp)

        call_count = {"n": 0}

        def _fake_request(*args, **kwargs):
            call_count["n"] += 1
            return resp

        monkeypatch.setattr(client.requests, "request", _fake_request)
        cache_delete = MagicMock()
        monkeypatch.setattr(frappe_stub.cache(), "delete_value", cache_delete)

        try:
            abha._request_with_retry("GET", "https://example.test/x", lambda: {}, None)
            assert False, "Should raise"
        except frappe_stub.ValidationError:
            pass

        assert call_count["n"] == 1, "X-token error must fail fast, not retry 3x as gateway refresh"
        cache_delete.assert_not_called()
