"""
Session hooks — called by Frappe on login/logout.
On logout: clear ABDM Token Registry for all sessions tied to the user.
"""
import frappe


def on_session_creation(login_manager):
	"""Regenerate session token on login to prevent session fixation (WASA A07)."""
	# Frappe handles session ID rotation natively; this hook is a placeholder
	# for any additional ABDM-specific session hardening needed.
	pass


def on_logout():
	"""
	M1-T14 / M1-T51: On Frappe logout, clear all ABDM tokens for the current user.
	This ensures:
	- Post-logout API calls immediately return 401 (no stale gateway tokens)
	- Token replay attacks are blocked (WASA A07)
	"""
	user = frappe.session.user
	if not user or user == "Guest":
		return

	# Find all Token Registry records for patients linked to this user
	# (via Patient record's linked user or direct session ownership)
	_clear_user_tokens(user)


def _clear_user_tokens(user: str):
	"""Clear gateway_access_token, x_token, linking_token for the given user's patients."""
	try:
		# Get all ABDM Token Registry records for patients this user has access to
		token_records = frappe.get_all(
			"ABDM Token Registry",
			filters={"owner": user},
			fields=["name"],
		)
		for record in token_records:
			frappe.db.set_value(
				"ABDM Token Registry",
				record["name"],
				{
					"gateway_access_token": None,
					"gateway_token_expiry": None,
					"x_token": None,
					"x_token_expiry": None,
					"linking_token": None,
					"linking_token_expiry": None,
					# t_token is enrolment-scoped, not session-scoped — leave it
				},
			)
		if token_records:
			frappe.db.commit()
	except Exception:
		# Never block logout due to token cleanup failures
		frappe.log_error("ABDM Token Registry cleanup failed on logout", "ABDM Auth")
