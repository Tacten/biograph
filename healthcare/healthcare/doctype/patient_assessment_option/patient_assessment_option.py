# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document


class PatientAssessmentOption(Document):
	def autoname(self):
		"""Generate name from option text and parent parameter to ensure uniqueness"""
		if not self.name and self.parent_parameter and self.option_text:
			self.name = f"{self.parent_parameter}: {self.option_text}"[:140]
			
	def get_label(self):
		"""Return formatted label for multiselect display"""
		return self.option_text or self.name
		
	def get_value(self):
		"""Return value for multiselect"""
		return self.name
		
	def get_description(self):
		"""Return a description that includes the score"""
		score_text = f" (Score: {self.score})" if self.score else ""
		return f"{self.option_text}{score_text}"
		
	def on_update(self):
		"""Ensure this option is directly accessible by its parent parameter"""
		if self.parent_parameter:
			# Ensure the parent parameter exists
			parent_exists = frappe.db.exists("Patient Assessment Parameter", self.parent_parameter)
			if not parent_exists:
				frappe.throw(f"Parent parameter {self.parent_parameter} does not exist")
				
	def after_insert(self):
		"""Add any necessary post-creation actions"""
		frappe.db.commit()
		
	def load_in_grid(self):
		"""Additional formatting for grid views"""
		self.label = self.get_label()
		return self

	def get_options(self):
		"""Return options for multiselect"""
		return [
			{'label': self.get_label(), 'value': self.get_value()}
		] 