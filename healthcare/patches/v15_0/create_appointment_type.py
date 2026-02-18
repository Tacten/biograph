
import frappe

# Create an Appintment Type at the time of setup
def execute():
    appointment_type = [
        "Consultation",
        "Therapy Session",
        "Unavailable",
        "Block Booking",
    ]

    color = [
        "#39E4A5",
        "#ECAD4B",
        "#f5001d",
        "#002df5"
    ]

    for i, row in enumerate(appointment_type):
        if not frappe.db.exists("Appointment Type", row):
            doc = frappe.get_doc({
                "doctype" : "Appointment Type",
                "appointment_type" : row,
                "default_duration" : 20,
                "color" : color[i]
            }).save()
