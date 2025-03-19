# -*- coding: utf-8 -*-
# Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class PatientDuplicateCheckField(Document):
    def validate(self):
        field_labels = {
            'first_name': 'First Name',
            'last_name': 'Last Name',
            'sex': 'Gender',
            'dob': 'Date of Birth',
            'mobile': 'Mobile',
            'email': 'Email'
        }
        self.field_label = field_labels.get(self.field_name, self.field_name) 