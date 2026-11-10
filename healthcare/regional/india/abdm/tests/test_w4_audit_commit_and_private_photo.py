"""
w4: audit_log commit parameter, private ABHA KYC photo, ABHA Record on_trash.

These are module-level pytest functions that mock the Frappe layer (see
conftest.py), like the sibling abdm/tests modules. They are NOT collected by
`bench run-tests`; run them with pytest, from the worktree/app root:

    ../../../../env/bin/python -m pytest \
        healthcare/regional/india/abdm/tests/test_w4_audit_commit_and_private_photo.py -v
"""

import contextlib
import importlib
import importlib.util
import sys
import types
from unittest.mock import MagicMock, patch

import pytest

# NOTE: frappe and the modules under test are deliberately NOT imported at module
# level. conftest.py installs a stub `frappe` per test; importing real modules at
# collection time would cache them in sys.modules bound to real frappe and break
# later tests. Everything is imported lazily via the `mods` fixture instead.


_FRESH = (
	"healthcare.healthcare.doctype.abha_record.abha_record",
	"healthcare.regional.india.abdm.api.profile",
	"healthcare.regional.india.abdm.utils.audit",
)


@pytest.fixture
def mods(frappe_stub, monkeypatch):
	"""Import the modules under test, fresh, after the stub frappe is installed.

	The modules under test (and anything they transitively import) are bound to this
	test's stub frappe, so every healthcare.* entry in sys.modules, and the matching
	attribute on its parent package, is restored at teardown; nothing leaks into
	other tests. A real Document base class replaces conftest's MagicMock so
	ABHARecord is a usable class.
	"""
	saved = {k: v for k, v in sys.modules.items() if k.startswith("healthcare.")}
	for name in _FRESH:
		sys.modules.pop(name, None)
	doc_mod = types.ModuleType("frappe.model.document")
	doc_mod.Document = type("Document", (), {})
	monkeypatch.setitem(sys.modules, "frappe.model.document", doc_mod)
	audit = importlib.import_module("healthcare.regional.india.abdm.utils.audit")
	# test_e2e_flows overwrites audit.audit_log on the shared module at run time, so
	# load a private copy of audit.py (not registered in sys.modules) to get the real
	# audit_log without polluting anything.
	spec = importlib.util.spec_from_file_location("_w4_real_audit", audit.__file__)
	real_audit = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(real_audit)
	try:
		yield types.SimpleNamespace(
			audit=audit,
			real_audit=real_audit,
			abha_record=importlib.import_module("healthcare.healthcare.doctype.abha_record.abha_record"),
			profile=importlib.import_module("healthcare.regional.india.abdm.api.profile"),
		)
	finally:
		for name in [k for k in sys.modules if k.startswith("healthcare.") and k not in saved]:
			del sys.modules[name]
			parent, _, child = name.rpartition(".")
			if parent in sys.modules and hasattr(sys.modules[parent], child):
				delattr(sys.modules[parent], child)
		for name, mod in saved.items():
			sys.modules[name] = mod
			parent, _, child = name.rpartition(".")
			if parent in sys.modules:
				setattr(sys.modules[parent], child, mod)


@contextlib.contextmanager
def _fake_audit_env(real_audit):
	"""Patch the frappe layer used by audit_log; yields (db, get_doc mock)."""
	db = MagicMock()
	db.table_exists.return_value = True
	with (
		patch.object(real_audit.frappe, "db", db, create=True),
		patch.object(
			real_audit.frappe, "session", types.SimpleNamespace(user="test@example.com"), create=True
		),
		patch.object(real_audit.frappe, "get_doc", create=True) as get_doc,
		patch.object(real_audit, "_get_client_ip", return_value="127.0.0.1"),
		patch.object(real_audit.frappe.utils, "now_datetime", create=True),
	):
		yield db, get_doc


def _record():
	return types.SimpleNamespace(
		status="DELETED",
		patient="P1",
		name="ABHA-1",
		flags={},
		_validate_patient_permission=MagicMock(),
	)


def _run_audit_log(mods, **kwargs):
	with _fake_audit_env(mods.real_audit) as (db, get_doc):
		mods.real_audit.audit_log("ABHA_DELETE", patient="P1", **kwargs)
	return db.commit, get_doc.return_value


def test_audit_log_commits_by_default(mods):
	commit, doc = _run_audit_log(mods)
	assert doc.insert.call_count == 1
	assert commit.call_count == 1


def test_audit_log_commit_false_skips_commit(mods):
	commit, doc = _run_audit_log(mods, commit=False)
	assert doc.insert.call_count == 1
	assert commit.call_count == 0


def test_abha_kyc_photo_saved_as_private_file(mods, monkeypatch):
	profile = mods.profile
	save_file = MagicMock(return_value=types.SimpleNamespace(file_url="/private/files/P1-abha-photo.jpg"))
	db = MagicMock()
	db.get_value.return_value = None
	# profile.py imports save_file inside the function (at call time), so a fake
	# module in sys.modules is picked up.
	fm = types.ModuleType("frappe.utils.file_manager")
	fm.save_file = save_file
	monkeypatch.setitem(sys.modules, "frappe.utils.file_manager", fm)
	with patch.object(profile.frappe, "db", db, create=True):
		url = profile.sync_profile_photo_to_patient("P1", "aGVsbG8=")
	assert save_file.call_args.kwargs["is_private"] == 1
	assert url == "/private/files/P1-abha-photo.jpg"
	db.set_value.assert_called_once_with("Patient", "P1", "image", url)


def test_abha_record_on_trash_audits_without_commit(mods):
	abha_record = mods.abha_record
	with (
		patch.object(abha_record.frappe, "get_all", return_value=[], create=True),
		patch.object(abha_record, "unlink_abha_from_patient"),
		patch("healthcare.regional.india.abdm.utils.audit.audit_log") as audit_log,
	):
		abha_record.ABHARecord.on_trash(_record())
	audit_log.assert_called_once_with("ABHA_DELETE", patient="P1", result="SUCCESS", commit=False)


def test_abha_record_on_trash_never_commits_audit_row(mods):
	"""
	PROXY for the acceptance criterion "a rejected delete leaves no committed
	audit row". Frappe runs the link check AFTER on_trash, so on_trash must insert
	the audit row but never commit; a later rollback then discards it. This test
	asserts only that on_trash never commits (the real audit_log runs against a
	fake frappe.db), NOT the full criterion.
	A true end-to-end test (delete_doc raising LinkExistsError and the
	tabABDM Audit Log row being absent afterwards) needs a live site/DB and is
	not feasible in this stubbed unit-test setup.
	"""
	abha_record = mods.abha_record
	with (
		_fake_audit_env(mods.real_audit) as (db, get_doc),
		# on_trash resolves audit_log from the shared audit module; point it at the real one.
		patch.object(mods.audit, "audit_log", mods.real_audit.audit_log),
		patch.object(abha_record.frappe, "get_all", return_value=[], create=True),
		patch.object(abha_record, "unlink_abha_from_patient"),
	):
		abha_record.ABHARecord.on_trash(_record())

	assert get_doc.return_value.insert.call_count == 1  # audit row written ...
	assert db.commit.call_count == 0  # ... but never committed by on_trash
