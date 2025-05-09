# -*- coding: utf-8 -*-
# Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _

def setup_patient_duplicate_check_rules():
    """
    Setup default patient duplicate check rules based on requirements from PATIENT-DUPLICATE.md.
    
    This function should be called during app installation or as a patch.
    """
    frappe.logger().info("Starting patient duplicate check rules setup")
    
    healthcare_settings = frappe.get_doc("Healthcare Settings")
    
    # Only proceed if there are no existing rules
    if healthcare_settings.get("patient_duplicate_check_rules"):
        frappe.logger().info("Patient duplicate check rules already exist, skipping setup")
        return
    
    # Enable patient duplicate check
    healthcare_settings.enable_patient_duplicate_check = 1
    
    # Define field options and labels
    field_options = {
        "first_name": {"label": "First Name", "is_required": 1},
        "last_name": {"label": "Last Name", "is_required": 0},
        "sex": {"label": "Gender", "is_required": 0},
        "dob": {"label": "Date of Birth", "is_required": 0},
        "mobile": {"label": "Mobile", "is_required": 0}
    }
    
    # Define rules based on the 25 scenarios in PATIENT-DUPLICATE.md
    rules = [
        # Scenario 2: All fields match exactly - Disallow
        {
            "rule_name": "All Fields Exact Match",
            "fields": ["first_name", "last_name", "sex", "dob", "mobile"],
            "action": "Disallow",
            "message": "Exact duplicate patient record found. Please use the existing patient record.",
            "priority": 1
        },
        # Scenario 3: First Name, Last Name, Gender, DOB match - Disallow
        {
            "rule_name": "Name Gender DOB Match",
            "fields": ["first_name", "last_name", "sex", "dob"],
            "action": "Disallow",
            "message": "Duplicate patient found with matching name, gender, and date of birth.",
            "priority": 2
        },
        # Scenario 4: First Name, Last Name, Gender, Mobile match - Disallow
        {
            "rule_name": "Name Gender Mobile Match",
            "fields": ["first_name", "last_name", "sex", "mobile"],
            "action": "Disallow",
            "message": "Duplicate patient found with matching name, gender, and mobile number.",
            "priority": 3
        },
        # Scenario 5: First Name, Last Name, Gender, DOB match - Disallow
        {
            "rule_name": "Name DOB Mobile Match",
            "fields": ["first_name", "last_name", "dob", "mobile"],
            "action": "Disallow",
            "message": "Duplicate patient found with matching name, date of birth, and mobile number.",
            "priority": 4
        },
        # Scenario 6: First Name, Gender, DOB, Mobile match - Disallow
        {
            "rule_name": "First Name Gender DOB Mobile Match",
            "fields": ["first_name", "sex", "dob", "mobile"],
            "action": "Disallow",
            "message": "Duplicate patient found with matching first name, gender, date of birth, and mobile number.",
            "priority": 5
        },
        # Scenario 7: Last Name, Gender, DOB, Mobile match - Disallow
        {
            "rule_name": "Last Name Gender DOB Mobile Match",
            "fields": ["last_name", "sex", "dob", "mobile"],
            "action": "Disallow",
            "message": "Duplicate patient found with matching last name, gender, date of birth, and mobile number.",
            "priority": 6
        },
        # Scenario 8: First Name, Last Name match (others don't) - Warn
        {
            "rule_name": "First and Last Name Match",
            "fields": ["first_name", "last_name"],
            "action": "Warn",
            "message": "Potential duplicate patient found with matching first and last name.",
            "priority": 7
        },
        # Scenario 9: First Name, Gender match (others don't) - Warn
        {
            "rule_name": "First Name and Gender Match",
            "fields": ["first_name", "sex"],
            "action": "Warn",
            "message": "Potential duplicate patient found with matching first name and gender.",
            "priority": 8
        },
        # Scenario 10: First Name, DOB match (others don't) - Warn
        {
            "rule_name": "First Name and DOB Match",
            "fields": ["first_name", "dob"],
            "action": "Warn",
            "message": "Potential duplicate patient found with matching first name and date of birth.",
            "priority": 9
        },
        # Scenario 11: First Name, Mobile match (others don't) - Warn
        {
            "rule_name": "First Name and Mobile Match",
            "fields": ["first_name", "mobile"],
            "action": "Warn",
            "message": "Potential duplicate patient found with matching first name and mobile number.",
            "priority": 10
        },
        # Scenario 12: Last Name, Gender match (others don't) - Warn
        {
            "rule_name": "Last Name and Gender Match",
            "fields": ["last_name", "sex"],
            "action": "Warn",
            "message": "Potential duplicate patient found with matching last name and gender.",
            "priority": 11
        },
        # Scenario 13: Last Name, DOB match (others don't) - Warn
        {
            "rule_name": "Last Name and DOB Match",
            "fields": ["last_name", "dob"],
            "action": "Warn",
            "message": "Potential duplicate patient found with matching last name and date of birth.",
            "priority": 12
        },
        # Scenario 14: Last Name, Mobile match (others don't) - Warn
        {
            "rule_name": "Last Name and Mobile Match",
            "fields": ["last_name", "mobile"],
            "action": "Warn",
            "message": "Potential duplicate patient found with matching last name and mobile number.",
            "priority": 13
        },
        # Scenario 15: Gender, DOB match (others don't) - Warn
        {
            "rule_name": "Gender and DOB Match",
            "fields": ["sex", "dob"],
            "action": "Warn",
            "message": "Potential duplicate patient found with matching gender and date of birth.",
            "priority": 14
        },
        # Scenario 16: Gender, Mobile match (others don't) - Warn
        {
            "rule_name": "Gender and Mobile Match",
            "fields": ["sex", "mobile"],
            "action": "Warn",
            "message": "Potential duplicate patient found with matching gender and mobile number.",
            "priority": 15
        },
        # Scenario 17: DOB, Mobile match (others don't) - Warn
        {
            "rule_name": "DOB and Mobile Match",
            "fields": ["dob", "mobile"],
            "action": "Warn",
            "message": "Potential duplicate patient found with matching date of birth and mobile number.",
            "priority": 16
        },
        # Scenario 18: First Name, Last Name, Mobile match (others don't) - Warn
        {
            "rule_name": "First Last Name and Mobile Match",
            "fields": ["first_name", "last_name", "mobile"],
            "action": "Warn",
            "message": "Potential duplicate patient found with matching name and mobile number.",
            "priority": 17
        },
        # Scenario 19: First Name, Last Name, DOB match (others don't) - Warn
        {
            "rule_name": "First Last Name and DOB Match",
            "fields": ["first_name", "last_name", "dob"],
            "action": "Warn",
            "message": "Potential duplicate patient found with matching name and date of birth.",
            "priority": 18
        },
        # Scenario 20: First Name, Gender, DOB match (others don't) - Warn
        {
            "rule_name": "First Name Gender and DOB Match",
            "fields": ["first_name", "sex", "dob"],
            "action": "Warn",
            "message": "Potential duplicate patient found with matching first name, gender, and date of birth.",
            "priority": 19
        },
        # Scenario 21: First Name, Gender, Mobile match (others don't) - Warn
        {
            "rule_name": "First Name Gender and Mobile Match",
            "fields": ["first_name", "sex", "mobile"],
            "action": "Warn",
            "message": "Potential duplicate patient found with matching first name, gender, and mobile number.",
            "priority": 20
        },
        # Scenario 22: Last Name, Gender, DOB match (others don't) - Warn
        {
            "rule_name": "Last Name Gender and DOB Match",
            "fields": ["last_name", "sex", "dob"],
            "action": "Warn",
            "message": "Potential duplicate patient found with matching last name, gender, and date of birth.",
            "priority": 21
        },
        # Scenario 23: Last Name, Gender, Mobile match (others don't) - Warn
        {
            "rule_name": "Last Name Gender and Mobile Match",
            "fields": ["last_name", "sex", "mobile"],
            "action": "Warn",
            "message": "Potential duplicate patient found with matching last name, gender, and mobile number.",
            "priority": 22
        },
        # Scenario 24: Gender, DOB, Mobile match (others don't) - Warn
        {
            "rule_name": "Gender DOB and Mobile Match",
            "fields": ["sex", "dob", "mobile"],
            "action": "Warn",
            "message": "Potential duplicate patient found with matching gender, date of birth, and mobile number.",
            "priority": 23
        }
        # Scenarios 1 and 25 are "Allow" cases which are the default behavior if no rules match
    ]
    
    frappe.logger().info(f"Creating {len(rules)} patient duplicate check rules")
    
    # Create rule configurations
    for i, rule in enumerate(rules, 1):
        # Check if rule already exists
        existing_rule = frappe.db.exists("Patient Duplicate Check Rule Configuration", rule["rule_name"])
        if existing_rule:
            rule_doc = frappe.get_doc("Patient Duplicate Check Rule Configuration", existing_rule)
            frappe.logger("web").debug(f"Rule {i}/{len(rules)}: '{rule['rule_name']}' already exists, using existing")
        else:
            # Create new rule configuration
            rule_doc = frappe.new_doc("Patient Duplicate Check Rule Configuration")
            rule_doc.rule_name = rule["rule_name"]
            rule_doc.action = rule["action"]
            rule_doc.message = rule["message"]
            rule_doc.priority = rule["priority"]
            
            # Add fields to the rule
            for field_name in rule["fields"]:
                if field_name in field_options:
                    rule_doc.append("duplicate_fields", {
                        "field_name": field_name,
                        "field_label": field_options[field_name]["label"],
                        "is_required": field_options[field_name]["is_required"]
                    })
            
            rule_doc.save()
            frappe.logger("web").debug(f"Rule {i}/{len(rules)}: '{rule['rule_name']}' created successfully")
        
        # Link rule configuration to healthcare settings
        healthcare_settings.append("patient_duplicate_check_rules", {
            "rule_configuration": rule_doc.name
        })
    
    healthcare_settings.save()
    frappe.db.commit()
    
    frappe.logger().info("Patient duplicate check rules setup completed successfully")
    frappe.msgprint(_("Patient duplicate check rules have been set up successfully."))

def execute():
    """
    Execute this function as a patch or during installation
    """
    setup_patient_duplicate_check_rules() 