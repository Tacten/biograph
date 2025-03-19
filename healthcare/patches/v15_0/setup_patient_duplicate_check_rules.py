from __future__ import unicode_literals
import frappe
from frappe import _
from healthcare.healthcare.setup.patient_duplicate_check import setup_patient_duplicate_check_rules

def execute():
    """
    Execute the patient duplicate check rules setup patch.
    This patch creates the patient duplicate check rule configurations
    based on the 25 scenarios defined in PATIENT-DUPLICATE.md
    """
    try:
        setup_patient_duplicate_check_rules()
        frappe.logger().info(_("Patient duplicate check rules have been set up successfully"))
    except Exception as e:
        frappe.logger().error(_("Error setting up patient duplicate check rules: {0}").format(str(e)))
        frappe.log_error(frappe.get_traceback(), _("Patient Duplicate Check Rules Setup Failed")) 