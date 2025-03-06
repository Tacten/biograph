# -*- coding: utf-8 -*-
# Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
import json
from frappe.model.document import Document

class HealthcareQuestionnaireTemplate(Document):
    def validate(self):
        self.validate_item_links()
    
    def validate_item_links(self):
        """Ensure all linkIds are unique within the questionnaire"""
        link_ids = {}
        for item in self.items:
            if item.linkId in link_ids:
                frappe.throw(f"Duplicate linkId '{item.linkId}' found. linkIds must be unique within a questionnaire.")
            link_ids[item.linkId] = 1
    
    def to_fhir(self):
        """Convert to FHIR Questionnaire format"""
        fhir_questionnaire = {
            "resourceType": "Questionnaire",
            "id": self.fhir_identifier or self.name,
            "url": f"Questionnaire/{self.name}",
            "title": self.title,
            "status": self.status,
            "date": self.approval_date,
            "publisher": self.publisher,
            "version": self.version,
            "description": self.description,
            "purpose": self.purpose,
            "item": []
        }
        
        # Convert items to FHIR format
        for item in self.items:
            fhir_item = {
                "linkId": item.linkId,
                "text": item.text,
                "type": item.type,
                "required": item.required,
                "repeats": item.repeats
            }
            
            # Add help text if provided
            if item.help_text:
                fhir_item["definition"] = item.help_text
            
            # Add options for choice questions
            if item.type in ["choice", "open-choice"] and item.field_options:
                fhir_item["answerOption"] = []
                options = item.field_options.split("\n")
                for option in options:
                    if ":" in option:
                        code, display = option.split(":", 1)
                        fhir_item["answerOption"].append({
                            "valueCoding": {
                                "code": code.strip(),
                                "display": display.strip()
                            }
                        })
                    else:
                        fhir_item["answerOption"].append({
                            "valueString": option.strip()
                        })
            
            # Add enableWhen conditions
            if item.has_condition and item.condition_question and item.condition_operator:
                fhir_item["enableWhen"] = [{
                    "question": item.condition_question,
                    "operator": item.condition_operator,
                    "answer": self.get_fhir_condition_answer(item)
                }]
            
            fhir_questionnaire["item"].append(fhir_item)
        
        return fhir_questionnaire
    
    def get_fhir_condition_answer(self, item):
        """Create appropriate FHIR answer format based on the condition value"""
        if not item.condition_value:
            return {"exists": True}
        
        # Try to determine value type based on operator and value
        if item.condition_operator in ["exists", "not-exists"]:
            return {"exists": item.condition_value.lower() == "true"}
        
        # Try to parse as boolean
        if item.condition_value.lower() in ["true", "false"]:
            return {"valueBoolean": item.condition_value.lower() == "true"}
        
        # Try to parse as number
        try:
            if "." in item.condition_value:
                return {"valueDecimal": float(item.condition_value)}
            else:
                return {"valueInteger": int(item.condition_value)}
        except ValueError:
            pass
        
        # Default to string
        return {"valueString": item.condition_value}


@frappe.whitelist()
def import_fhir_questionnaire(fhir_data):
    """Import a FHIR Questionnaire into ERPNext"""
    if isinstance(fhir_data, str):
        fhir_data = json.loads(fhir_data)
    
    if fhir_data.get("resourceType") != "Questionnaire":
        frappe.throw("Invalid FHIR resource type. Expected 'Questionnaire'")
    
    # Create questionnaire template
    questionnaire = frappe.new_doc("Healthcare Questionnaire Template")
    questionnaire.title = fhir_data.get("title", "Imported Questionnaire")
    questionnaire.status = fhir_data.get("status", "draft")
    questionnaire.description = fhir_data.get("description", "")
    questionnaire.purpose = fhir_data.get("purpose", "")
    questionnaire.fhir_identifier = fhir_data.get("id", "")
    questionnaire.version = fhir_data.get("version", "")
    questionnaire.publisher = fhir_data.get("publisher", "")
    
    # Process items (questions)
    process_fhir_items(questionnaire, fhir_data.get("item", []))
    
    return questionnaire

def process_fhir_items(questionnaire, items):
    """Process FHIR questionnaire items recursively"""
    for item in items:
        q_item = frappe.new_doc("Questionnaire Item")
        q_item.linkId = item.get("linkId", "")
        q_item.text = item.get("text", "")
        q_item.type = item.get("type", "string")
        q_item.required = item.get("required", False)
        q_item.repeats = item.get("repeats", False)
        q_item.help_text = item.get("definition", "")
        
        # Map FHIR type to Frappe fieldtype
        q_item.fieldtype = map_fhir_to_frappe_fieldtype(item.get("type"))
        
        # Handle options for choice questions
        if item.get("type") in ["choice", "open-choice"] and item.get("answerOption"):
            options = []
            for option in item.get("answerOption", []):
                if "valueCoding" in option:
                    options.append(f"{option['valueCoding'].get('code', '')}: {option['valueCoding'].get('display', '')}")
                elif "valueString" in option:
                    options.append(option["valueString"])
            q_item.field_options = "\n".join(options)
        
        # Handle enableWhen conditions
        if item.get("enableWhen"):
            condition = item["enableWhen"][0]  # Taking first condition for simplicity
            q_item.has_condition = True
            q_item.condition_question = condition.get("question", "")
            q_item.condition_operator = condition.get("operator", "equals")
            
            # Extract condition value based on type
            for key, value in condition.get("answer", {}).items():
                if key.startswith("value"):
                    q_item.condition_value = str(value)
                    break
        
        questionnaire.append("items", q_item)
        
        # Process nested items - for groups
        if item.get("item"):
            process_fhir_items(questionnaire, item["item"])

def map_fhir_to_frappe_fieldtype(fhir_type):
    """Map FHIR question types to Frappe field types"""
    mapping = {
        "boolean": "Check",
        "decimal": "Float",
        "integer": "Int",
        "date": "Date",
        "dateTime": "Datetime",
        "time": "Time",
        "string": "Data",
        "text": "Text",
        "url": "Data",
        "choice": "Select",
        "open-choice": "Data",
        "attachment": "Attach",
        "reference": "Link",
        "quantity": "Float",
        "group": "Section Break",
        "display": "HTML"
    }
    return mapping.get(fhir_type, "Data") 