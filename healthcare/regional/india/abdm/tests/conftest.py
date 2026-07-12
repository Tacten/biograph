"""
pytest fixtures shared across all healthcare ABDM test modules.

Provides a lightweight Frappe stub so tests run without a full Frappe/ERPNext
install. Only the specific frappe behaviours used by healthcare.regional.india.abdm are stubbed.
"""

import hashlib
import json
import types
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Minimal Frappe stub
# ---------------------------------------------------------------------------

class _FrappeStub(types.ModuleType):
    """
    Replaces the `frappe` module for unit tests. Exposes the subset of the
    frappe API that healthcare.regional.india.abdm actually calls.
    """

    # Exception classes (match Frappe's class names exactly)
    class ValidationError(Exception): pass
    class PermissionError(Exception): pass
    class DoesNotExistError(Exception): pass
    class AuthenticationError(Exception): pass

    def __init__(self):
        super().__init__("frappe")
        self._thrown = None
        self.session = types.SimpleNamespace(user="test@example.com")
        self.form_dict = {}
        self.response = {}
        self.request = MagicMock()
        self.request.method = "POST"
        self.request.headers = {}
        self.request.data = b""
        self.request.environ = {"REMOTE_ADDR": "127.0.0.1"}

    # ── Core helpers ──────────────────────────────────────────────────────

    def _(self, s):
        return s

    def throw(self, message, exc_type=None, title=None):
        exc_type = exc_type or self.ValidationError
        raise exc_type(message)

    def get_single(self, doctype):
        return MagicMock()

    def get_doc(self, *args, **kwargs):
        doc = MagicMock()
        doc.insert = MagicMock()
        doc.save = MagicMock()
        return doc

    def new_doc(self, doctype):
        return MagicMock()

    def db(self):
        pass

    def log_error(self, *a, **kw):
        pass

    def get_traceback(self):
        return ""

    def cache(self):
        # Real Frappe returns one shared Redis connection per request — repeated
        # frappe.cache() calls within a test must see each other's writes.
        if not hasattr(self, "_cache_singleton"):
            self._cache_singleton = _RedisStub()
        return self._cache_singleton

    def whitelist(self, *a, **kw):
        def decorator(fn):
            return fn
        return decorator

    # ── DB stub ───────────────────────────────────────────────────────────

    class _DB:
        def get_value(self, *a, **kw):
            return None
        def exists(self, *a, **kw):
            return True
        def set_value(self, *a, **kw):
            pass
        def commit(self):
            pass
        def table_exists(self, *a, **kw):
            return True
        def get_all(self, *a, **kw):
            return []

    # ── Utils stub ────────────────────────────────────────────────────────

    class utils:
        @staticmethod
        def now_datetime():
            from datetime import datetime
            return datetime(2026, 6, 22, 12, 0, 0)

        @staticmethod
        def get_datetime(val):
            return val

        @staticmethod
        def add_to_date(dt, **kw):
            from datetime import timedelta
            return dt + timedelta(**kw)


class _RedisStub:
    def __init__(self):
        self._store = {}

    def get(self, key):
        return self._store.get(key)

    def set_value(self, key, value, expires_in_sec=None):
        self._store[key] = value

    def delete_value(self, key):
        self._store.pop(key, None)


@pytest.fixture(autouse=True)
def frappe_stub(monkeypatch):
    """
    Replace `frappe` with a stub in every test. Also patches frappe.db so
    individual tests can override behaviour with monkeypatch.
    """
    import sys
    stub = _FrappeStub()
    stub.db = stub._DB()
    monkeypatch.setitem(sys.modules, "frappe", stub)

    # Patch sub-modules that healthcare.regional.india.abdm imports
    for sub in ["frappe.utils", "frappe.model.document", "frappe.utils.typing_validations"]:
        if sub not in sys.modules:
            monkeypatch.setitem(sys.modules, sub, MagicMock())

    return stub


@pytest.fixture
def mock_request(frappe_stub):
    """Return the mocked frappe.request for manipulation in tests."""
    return frappe_stub.request


@pytest.fixture
def redis_cache(frappe_stub):
    """Return the in-memory Redis stub for rate-limit tests."""
    return _RedisStub()
