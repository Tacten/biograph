"""
Milestone patch — ABHA Address Detail doctype (M1-T85) ships as part of the
regional/india/abdm module's own doctype fixtures (schema sync handles
creation). This patch exists only to log the milestone in migrate output.
"""
import frappe


def execute():
	frappe.logger("abdm").info("ABHA Address Detail doctype available (M1-T85)")
