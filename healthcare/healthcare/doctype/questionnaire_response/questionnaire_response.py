# -*- coding: utf-8 -*-
# Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
import json
from frappe.model.document import Document
from frappe.utils import now_datetime

class QuestionnaireResponse(Document):
    def validate(self):
        self.validate_required_answers()
        
        if not self.authored_on:
            self.authored_on = now_datetime()
            
        if not self.author:
            self.author = frappe.session.user
    
    def on_submit(self):
        if self.status == "in-progress":
            self.status = "completed"
    
    def validate_required_answers(self):
        """Check if all required questions have been answered"""
        # Get all required questions from template - use direct SQL to avoid permission issues
        required_questions = frappe.db.sql("""
            SELECT name, linkId, text 
            FROM `tabQuestionnaire Item` 
            WHERE parent = %s AND required = 1
        """, (self.questionnaire,), as_dict=1)
        
        # Check if all required questions have answers
        answered_questions = [item.question for item in self.items if self.has_answer(item)]
        
        for q in required_questions:
            if q.name not in answered_questions:
                frappe.throw(f"Required question not answered: {q.text}")
    
    def has_answer(self, item):
        """Check if the item has any answer based on its type"""
        if item.type == 'boolean' and item.answer_boolean is not None:
            return True
        if item.type == 'decimal' and item.answer_decimal is not None:
            return True
        if item.type == 'integer' and item.answer_integer is not None:
            return True
        if item.type == 'date' and item.answer_date:
            return True
        if item.type == 'dateTime' and item.answer_datetime:
            return True
        if item.type == 'string' and item.answer_string:
            return True
        if item.type == 'text' and item.answer_text:
            return True
        if item.type == 'url' and item.answer_url:
            return True
        if item.type in ['choice', 'open-choice'] and item.answer_choice:
            return True
        if item.type == 'attachment' and item.answer_attachment:
            return True
        return False
    
    def to_fhir(self):
        """Convert to FHIR QuestionnaireResponse format"""
        fhir_response = {
            "resourceType": "QuestionnaireResponse",
            "questionnaire": f"Questionnaire/{self.questionnaire}",
            "status": self.status,
            "subject": {
                "reference": f"Patient/{self.patient}"
            },
            "authored": self.authored_on,
            "author": {
                "reference": f"User/{self.author}"
            },
            "item": []
        }
        
        # Add encounter reference if present
        if self.encounter:
            fhir_response["encounter"] = {
                "reference": f"Encounter/{self.encounter}"
            }
        
        # Convert items to FHIR format
        for item in self.items:
            fhir_item = {
                "linkId": item.linkId,
                "text": item.text,
                "answer": []
            }
            
            # Add answer based on type
            if item.type == 'boolean' and item.answer_boolean is not None:
                fhir_item["answer"].append({"valueBoolean": item.answer_boolean})
            elif item.type == 'decimal' and item.answer_decimal is not None:
                fhir_item["answer"].append({"valueDecimal": item.answer_decimal})
            elif item.type == 'integer' and item.answer_integer is not None:
                fhir_item["answer"].append({"valueInteger": item.answer_integer})
            elif item.type == 'date' and item.answer_date:
                fhir_item["answer"].append({"valueDate": str(item.answer_date)})
            elif item.type == 'dateTime' and item.answer_datetime:
                fhir_item["answer"].append({"valueDateTime": str(item.answer_datetime)})
            elif item.type == 'string' and item.answer_string:
                fhir_item["answer"].append({"valueString": item.answer_string})
            elif item.type == 'text' and item.answer_text:
                fhir_item["answer"].append({"valueString": item.answer_text})
            elif item.type == 'url' and item.answer_url:
                fhir_item["answer"].append({"valueUri": item.answer_url})
            elif item.type in ['choice', 'open-choice'] and item.answer_choice:
                # Check if the answer is a coding (code: display) or just a string
                if ":" in item.answer_choice:
                    code, display = item.answer_choice.split(":", 1)
                    fhir_item["answer"].append({
                        "valueCoding": {
                            "code": code.strip(),
                            "display": display.strip()
                        }
                    })
                else:
                    fhir_item["answer"].append({"valueString": item.answer_choice})
            elif item.type == 'attachment' and item.answer_attachment:
                fhir_item["answer"].append({
                    "valueAttachment": {
                        "url": item.answer_attachment
                    }
                })
            
            if fhir_item["answer"]:  # Only add items with answers
                fhir_response["item"].append(fhir_item)
        
        return fhir_response


@frappe.whitelist()
def get_questionnaire_items(questionnaire):
    """Get all items from a questionnaire template"""
    # Use direct SQL to avoid permission issues
    return frappe.db.sql("""
        SELECT name, linkId, text, type, required, repeats, 
               fieldtype, field_options, has_condition, 
               condition_question, condition_operator, condition_value
        FROM `tabQuestionnaire Item`
        WHERE parent = %s
    """, (questionnaire,), as_dict=1)


@frappe.whitelist()
def create_from_encounter(encounter, questionnaire):
    """Create a new questionnaire response from a patient encounter"""
    # Run this with ignore_permissions to avoid permission issues
    with frappe.flags.ignore_permissions(True):
        encounter_doc = frappe.get_doc("Patient Encounter", encounter)
        
        response = frappe.new_doc("Questionnaire Response")
        response.questionnaire = questionnaire
        response.patient = encounter_doc.patient
        response.encounter = encounter
        response.company = encounter_doc.company
        response.author = frappe.session.user
        response.authored_on = now_datetime()
        response.status = "in-progress"
        
        # Populate items from questionnaire template
        items = get_questionnaire_items(questionnaire)
        for item in items:
            response_item = frappe.new_doc("Questionnaire Response Item")
            response_item.question = item.name
            response_item.linkId = item.linkId
            response_item.text = item.text
            response_item.type = item.type
            response.append("items", response_item)
        
        return response 