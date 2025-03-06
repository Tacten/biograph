import frappe
import json
from frappe.utils import now_datetime

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
    
    if fhir_data.get("date"):
        questionnaire.approval_date = fhir_data.get("date")
    
    # Process items (questions)
    process_fhir_items(questionnaire, fhir_data.get("item", []))
    
    return questionnaire

def process_fhir_items(questionnaire, items, parent_linkId=None):
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
        
        # Process nested items
        if item.get("item"):
            process_fhir_items(questionnaire, item["item"], item.get("linkId"))

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

def export_fhir_questionnaire_response(questionnaire_response, include_unanswered=False):
    """
    Convert a QuestionnaireResponse to FHIR format
    
    Args:
        questionnaire_response: The QuestionnaireResponse document
        include_unanswered: Whether to include questions without answers
    
    Returns:
        dict: FHIR formatted QuestionnaireResponse
    """
    if isinstance(questionnaire_response, str):
        questionnaire_response = frappe.get_doc("Questionnaire Response", questionnaire_response)
    
    fhir_response = {
        "resourceType": "QuestionnaireResponse",
        "questionnaire": f"Questionnaire/{questionnaire_response.questionnaire}",
        "status": questionnaire_response.status,
        "subject": {
            "reference": f"Patient/{questionnaire_response.patient}"
        },
        "authored": questionnaire_response.authored_on,
        "author": {
            "reference": f"User/{questionnaire_response.author}"
        },
        "item": []
    }
    
    # Add encounter reference if present
    if questionnaire_response.encounter:
        fhir_response["encounter"] = {
            "reference": f"Encounter/{questionnaire_response.encounter}"
        }
    
    # Get questionnaire template to include proper question structure
    template = frappe.get_doc("Healthcare Questionnaire Template", questionnaire_response.questionnaire)
    
    # Build a map of responses by linkId for quick lookup
    responses_by_linkId = {}
    for item in questionnaire_response.items:
        responses_by_linkId[item.linkId] = item
    
    # Process template items maintaining structure
    fhir_response["item"] = process_response_items(template.items, responses_by_linkId, include_unanswered)
    
    return fhir_response

def process_response_items(template_items, responses_by_linkId, include_unanswered=False, parent_item=None):
    """Process questionnaire items recursively, maintaining structure"""
    result = []
    
    for template_item in template_items:
        # Find corresponding response
        response = responses_by_linkId.get(template_item.linkId)
        
        # If no response and we're not including unanswered, skip
        if not response and not include_unanswered and template_item.type != "group":
            continue
        
        # Create the item structure
        fhir_item = {
            "linkId": template_item.linkId,
            "text": template_item.text
        }
        
        # For groups, recursively process child items
        if template_item.type == "group":
            # Get child items from template
            child_template_items = [i for i in template_items if getattr(i, "parent_item", None) == template_item.linkId]
            child_items = process_response_items(child_template_items, responses_by_linkId, include_unanswered, template_item.linkId)
            
            if child_items:
                fhir_item["item"] = child_items
                result.append(fhir_item)
            
        # For regular items with responses
        elif response:
            fhir_item["answer"] = []
            
            # Add answer based on type
            if template_item.type == 'boolean' and response.answer_boolean is not None:
                fhir_item["answer"].append({"valueBoolean": response.answer_boolean})
            elif template_item.type == 'decimal' and response.answer_decimal is not None:
                fhir_item["answer"].append({"valueDecimal": response.answer_decimal})
            elif template_item.type == 'integer' and response.answer_integer is not None:
                fhir_item["answer"].append({"valueInteger": response.answer_integer})
            elif template_item.type == 'date' and response.answer_date:
                fhir_item["answer"].append({"valueDate": str(response.answer_date)})
            elif template_item.type == 'dateTime' and response.answer_datetime:
                fhir_item["answer"].append({"valueDateTime": str(response.answer_datetime)})
            elif template_item.type == 'string' and response.answer_string:
                fhir_item["answer"].append({"valueString": response.answer_string})
            elif template_item.type == 'text' and response.answer_text:
                fhir_item["answer"].append({"valueString": response.answer_text})
            elif template_item.type == 'url' and response.answer_url:
                fhir_item["answer"].append({"valueUri": response.answer_url})
            elif template_item.type in ['choice', 'open-choice'] and response.answer_choice:
                # Check if the answer is a coding (code: display) or just a string
                if ":" in response.answer_choice:
                    code, display = response.answer_choice.split(":", 1)
                    fhir_item["answer"].append({
                        "valueCoding": {
                            "code": code.strip(),
                            "display": display.strip()
                        }
                    })
                else:
                    fhir_item["answer"].append({"valueString": response.answer_choice})
            elif template_item.type == 'attachment' and response.answer_attachment:
                fhir_item["answer"].append({
                    "valueAttachment": {
                        "url": response.answer_attachment
                    }
                })
            
            # Only add to result if it has answers or we're including unanswered
            if fhir_item["answer"] or include_unanswered:
                result.append(fhir_item)
                
        # For items without responses but we're including unanswered
        elif include_unanswered:
            result.append(fhir_item)
    
    return result

@frappe.whitelist()
def import_fhir_json():
    """Web handler to import FHIR JSON"""
    if frappe.request.method != "POST":
        frappe.throw("Method not allowed")
    
    try:
        data = json.loads(frappe.request.data)
        if data.get("resourceType") == "Questionnaire":
            questionnaire = import_fhir_questionnaire(data)
            questionnaire.insert()
            frappe.db.commit()
            
            return {
                "status": "success",
                "message": f"Questionnaire '{questionnaire.title}' imported successfully",
                "name": questionnaire.name
            }
        else:
            frappe.throw("Invalid resource type. Expected 'Questionnaire'")
    except Exception as e:
        frappe.log_error(f"FHIR Import Error: {str(e)}")
        return {
            "status": "error",
            "message": str(e)
        } 