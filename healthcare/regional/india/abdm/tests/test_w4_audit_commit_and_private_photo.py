"""
w4: audit_log commit parameter, private ABHA KYC photo, ABHA Record on_trash.

These are module-level pytest functions that mock the Frappe layer (see
conftest.py), like the sibling abdm/tests modules. They are NOT collected by
`bench run-tests`; run them with pytest, from the worktree/app root:

    ../../../../env/bin/python -m pytest \
        healthcare/regional/india/abdm/tests/test_w4_audit_commit_and_private_photo.py -v
"""

import types
from unittest.mock import MagicMock, patch

import frappe

from healthcare.healthcare.doctype.abha_record import abha_record
from healthcare.regional.india.abdm.api import profile
from healthcare.regional.india.abdm.utils import audit

# Captured at import: test_e2e_flows overwrites audit.audit_log on the module at run time.
_REAL_AUDIT_LOG = audit.audit_log


def _run_audit_log(**kwargs):
	db = MagicMock()
	db.table_exists.return_value = True
	with (
		patch.object(audit.frappe, "db", db),
		patch.object(audit.frappe, "session", types.SimpleNamespace(user="test@example.com")),
		patch.object(audit.frappe, "get_doc") as get_doc,
		patch.object(audit, "_get_client_ip", return_value="127.0.0.1"),
		patch.object(audit.frappe.utils, "now_datetime"),
	):
		_REAL_AUDIT_LOG("ABHA_DELETE", patient="P1", **kwargs)
	return db.commit, get_doc.return_value


def test_audit_log_commits_by_default():
	commit, doc = _run_audit_log()
	assert doc.insert.call_count == 1
	assert commit.call_count == 1


def test_audit_log_commit_false_skips_commit():
	commit, doc = _run_audit_log(commit=False)
	assert doc.insert.call_count == 1
	assert commit.call_count == 0


def test_abha_kyc_photo_saved_as_private_file():
	save_file = MagicMock(return_value=types.SimpleNamespace(file_url="/private/files/P1-abha-photo.jpg"))
	db = MagicMock()
	db.get_value.return_value = None
	with (
		patch.object(profile.frappe, "db", db),
		# Patching the source module attribute works because profile.py imports
		# save_file inside the function (at call time), not at module import.
		patch("frappe.utils.file_manager.save_file", save_file),
	):
		url = profile.sync_profile_photo_to_patient("P1", "aGVsbG8=")
	assert save_file.call_args.kwargs["is_private"] == 1
	assert url == "/private/files/P1-abha-photo.jpg"
	db.set_value.assert_called_once_with("Patient", "P1", "image", url)


def test_abha_record_on_trash_audits_without_commit():
	record = types.SimpleNamespace(
		status="DELETED",
		patient="P1",
		name="ABHA-1",
		flags={},
		_validate_patient_permission=MagicMock(),
	)
	with (
		patch.object(abha_record.frappe, "get_all", return_value=[]),
		patch.object(abha_record, "unlink_abha_from_patient"),
		patch("healthcare.regional.india.abdm.utils.audit.audit_log") as audit_log,
	):
		abha_record.ABHARecord.on_trash(record)
	audit_log.assert_called_once_with("ABHA_DELETE", patient="P1", result="SUCCESS", commit=False)


def test_abha_record_on_trash_does_not_commit_audit_row_before_link_check():
	"""
	Acceptance: deleting an ABHA Record that then fails Frappe's link check must
	leave no committed audit row. Frappe runs the link check AFTER on_trash, so
	on_trash must insert the audit row but never commit; a later rollback then
	discards it.

	Runs the REAL audit_log (captured at import) against a fake frappe.db, so the
	assertion covers the actual audit_log -> commit path, not just the kwarg.
	NOTE: a true end-to-end test (delete_doc raising LinkExistsError and the
	tabABDM Audit Log row being absent afterwards) needs a live site/DB and is
	not feasible in this stubbed unit-test setup; this is the closest check.
	"""
	record = types.SimpleNamespace(
		status="DELETED",
		patient="P1",
		name="ABHA-1",
		flags={},
		_validate_patient_permission=MagicMock(),
	)
	db = MagicMock()
	db.table_exists.return_value = True
	with (
		patch.object(audit.frappe, "db", db),
		patch.object(audit.frappe, "session", types.SimpleNamespace(user="test@example.com")),
		patch.object(audit.frappe, "get_doc") as get_doc,
		patch.object(audit, "_get_client_ip", return_value="127.0.0.1"),
		patch.object(audit.frappe.utils, "now_datetime"),
		patch.object(audit, "audit_log", _REAL_AUDIT_LOG),
		patch.object(abha_record.frappe, "get_all", return_value=[]),
		patch.object(abha_record, "unlink_abha_from_patient"),
	):
		abha_record.ABHARecord.on_trash(record)

	assert get_doc.return_value.insert.call_count == 1  # audit row written ...
	assert db.commit.call_count == 0  # ... but not committed before the link check
