"""
S6 Token Security
==================
M1-T30  JWT algorithm confusion: this app must never decode/verify a JWT
        itself — every ABDM-issued token (accessToken, X-token, T-token,
        refreshToken) is stored and forwarded as an opaque bearer string.
        That is what closes off the alg:none / HS-RS confusion attack
        surface: there is no signature verification here to confuse.
M1-T50  Token/txnId replay prevention — a txnId that already completed a
        terminal verify must be rejected on replay.

Run: pytest healthcare/regional/india/abdm/tests/test_token_security.py -v --tb=short
"""

import pathlib
import re

import pytest

_APP_ROOT = pathlib.Path(__file__).resolve().parent.parent  # healthcare/regional/india/abdm
_SOURCE_FILES = [
    p for p in _APP_ROOT.rglob("*.py")
    if "tests" not in p.parts and "__pycache__" not in p.parts
]

_JWT_IMPORT_PATTERN = re.compile(r"^\s*(import\s+jwt|from\s+jwt\b|import\s+jose|from\s+jose\b)", re.MULTILINE)
_JWT_DECODE_PATTERN = re.compile(r"\bjwt\.decode\s*\(")


# ── T30: JWT algorithm confusion ─────────────────────────────────────────────

class TestT30_JWTAlgConfusion:
    """
    T30 — There must be no JWT decode/verify path anywhere in healthcare.regional.india.abdm.
    ABDM-issued tokens are opaque to this app: it never inspects claims or
    re-derives trust from a token's `alg` header, so an attacker cannot
    forge a token by switching algorithms (alg:none, HS256/RS256 confusion)
    against code that isn't there.
    """

    def test_no_jwt_or_jose_library_imports(self):
        offenders = []
        for path in _SOURCE_FILES:
            text = path.read_text(encoding="utf-8", errors="ignore")
            if _JWT_IMPORT_PATTERN.search(text):
                offenders.append(str(path.relative_to(_APP_ROOT)))
        assert not offenders, (
            f"Found JWT/JOSE library imports in {offenders} — if a real reason exists to "
            "decode a token, algorithms=[...] must be explicitly pinned and this test updated."
        )

    def test_no_manual_jwt_decode_calls(self):
        offenders = []
        for path in _SOURCE_FILES:
            text = path.read_text(encoding="utf-8", errors="ignore")
            if _JWT_DECODE_PATTERN.search(text):
                offenders.append(str(path.relative_to(_APP_ROOT)))
        assert not offenders, f"Found jwt.decode(...) calls in {offenders}"

    def test_token_registry_fields_are_password_type(self):
        """
        All token fields on ABDM Token Registry must be Password fieldtype —
        i.e. treated as opaque secrets, never as structured/parseable data.
        """
        import json as _json
        doctype_path = (
            _APP_ROOT.parent.parent.parent / "healthcare" / "doctype" / "abdm_token_registry" / "abdm_token_registry.json"
        )
        spec = _json.loads(doctype_path.read_text())
        token_fields = [
            f for f in spec["fields"]
            if f["fieldname"] in {
                "gateway_access_token", "x_token", "linking_token", "t_token",
            }
        ]
        assert len(token_fields) == 4
        for field in token_fields:
            assert field["fieldtype"] == "Password", (
                f"{field['fieldname']} must be Password fieldtype, got {field['fieldtype']}"
            )


# ── T50: txnId replay prevention ─────────────────────────────────────────────

class TestT50_TxnReplayPrevention:
    """T50 — a txnId that already completed a terminal verify cannot be reused."""

    def test_fresh_txn_passes(self, frappe_stub):
        from healthcare.regional.india.abdm.utils.rate_limit import check_txn_not_consumed
        check_txn_not_consumed("txn-fresh-001")  # must not raise

    def test_consumed_txn_is_rejected(self, frappe_stub):
        from healthcare.regional.india.abdm.utils.rate_limit import check_txn_not_consumed, mark_txn_consumed
        mark_txn_consumed("txn-used-002")
        with pytest.raises(frappe_stub.ValidationError):
            check_txn_not_consumed("txn-used-002")

    def test_different_txn_ids_are_independent(self, frappe_stub):
        from healthcare.regional.india.abdm.utils.rate_limit import check_txn_not_consumed, mark_txn_consumed
        mark_txn_consumed("txn-a-003")
        check_txn_not_consumed("txn-b-003")  # different id — must not raise
