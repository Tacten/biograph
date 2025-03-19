# -*- coding: utf-8 -*-
# Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class PatientDuplicateCheckRuleConfiguration(Document):
    def validate(self):
        # Ensure all fields have field_label set
        for field in self.duplicate_fields:
            field_labels = {
                'first_name': 'First Name',
                'last_name': 'Last Name',
                'sex': 'Gender',
                'dob': 'Date of Birth',
                'mobile': 'Mobile',
                'email': 'Email'
            }
            field.field_label = field_labels.get(field.field_name, field.field_name) 