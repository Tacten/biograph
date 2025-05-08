import frappe

def execute():
    meta = frappe.get_meta("Patient Encounter")
    if meta.has_field("custom_doctor_advice"):
        frappe.db.sql(""" 
                Update `tabPatient Encounter`
                Set doctor_advice = custom_doctor_advice
                Where 1=1
        """, as_dict = 1)
        
    
    field =  frappe.db.get_value("Custom Field", {"fieldname" : "custom_doctor_advice", "dt" : "Patient Encounter"}, "name")
    print(field)
    frappe.db.delete("Custom Field", field)

# from healthcare.patches.v15_0.custom_field_to_standard_field import execute
    