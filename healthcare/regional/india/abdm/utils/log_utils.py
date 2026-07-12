"""
M1-T6: PII/PHI log scrubber.
Ensures Aadhaar numbers, OTPs, mobile numbers, and ABDM tokens
never appear in any log output.
"""
import re
import frappe

# Patterns that must never appear in logs
_SCRUB_PATTERNS = [
	(re.compile(r"\b\d{12}\b"), "[AADHAAR_REDACTED]"),           # 12-digit Aadhaar
	(re.compile(r"\b\d{14}\b"), "[ABHA_NUM_REDACTED]"),          # 14-digit ABHA number
	(re.compile(r"\b\d{6}\b"), "[OTP_REDACTED]"),                # 6-digit OTPs
	(re.compile(r"\b[789]\d{9}\b"), "[MOBILE_REDACTED]"),        # Indian mobile numbers
	(re.compile(r'"x_token"\s*:\s*"[^"]{10,}"'), '"x_token":"[REDACTED]"'),
	(re.compile(r'"t_token"\s*:\s*"[^"]{10,}"'), '"t_token":"[REDACTED]"'),
	(re.compile(r'"linking_token"\s*:\s*"[^"]{10,}"'), '"linking_token":"[REDACTED]"'),
	(re.compile(r'"gateway_access_token"\s*:\s*"[^"]{10,}"'), '"gateway_access_token":"[REDACTED]"'),
	(re.compile(r'"accessToken"\s*:\s*"[^"]{10,}"'), '"accessToken":"[REDACTED]"'),
	(re.compile(r'"Authorization"\s*:\s*"Bearer [^"]{10,}"'), '"Authorization":"Bearer [REDACTED]"'),
]


def scrub_pii(message: str) -> str:
	"""
	Remove all PII/PHI from a log message string.
	Call this before any frappe.logger().* or frappe.log_error() for ABDM-related messages.

	Usage:
	    frappe.logger("abdm").info(scrub_pii(f"Response: {response_body}"))
	"""
	if not isinstance(message, str):
		message = str(message)
	for pattern, replacement in _SCRUB_PATTERNS:
		message = pattern.sub(replacement, message)
	return message


def abdm_log(level: str, message: str, title: str = "ABDM"):
	"""
	Safe ABDM logger — always scrubs PII before writing.
	level: 'debug' | 'info' | 'warning' | 'error'

	Frappe logger defaults to WARNING, so INFO entries are silently dropped.
	Force the logger to DEBUG level so all abdm_log() calls are written.
	"""
	import logging
	clean = scrub_pii(message)
	logger = frappe.logger("abdm", with_more_info=False)
	logger.setLevel(logging.DEBUG)
	getattr(logger, level, logger.info)(clean)
