"""
Milestone patch — FHIR foundation doctypes (M1-T81-84: FHIR Bundle,
FHIR Patient Cache, Care Context, Consent Request) ship as part of the
regional/india/abdm module's own doctype fixtures (schema sync handles
creation). This patch exists only to log the milestone in migrate output.
"""
import frappe


def execute():
	frappe.logger("abdm").info(
		"FHIR foundation doctypes available: FHIR Bundle, FHIR Patient Cache, "
		"Care Context, Consent Request (M1-T81-84)"
	)
