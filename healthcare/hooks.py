app_name = "healthcare"
app_title = "Biograph"
app_publisher = "earthians Health Informatics Pvt. Ltd."
app_description = "Modern, Open Source HIS built on Frappe and ERPNext"
app_icon = "octicon octicon-file-directory"
app_color = "grey"
app_email = "info@earthianslive.com"
app_license = "GNU GPL V3"
required_apps = ["frappe/erpnext"]
app_home = "/desk/healthcare"

add_to_apps_screen = [
	{
		"name": app_name,
		"logo": "/assets/healthcare/images/healthcare.svg",
		"title": app_title,
		"route": app_home,
		"has_permission": "erpnext.check_app_permission",
	}
]

# Includes in <head>
# ------------------
# include js, css files in header of desk.html
# app_include_css = "/assets/healthcare/css/healthcare.css"
app_include_js = "healthcare.bundle.js"

# include js, css files in header of web template
# web_include_css = "/assets/healthcare/css/healthcare.css"
# web_include_js = "/assets/healthcare/js/healthcare.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "healthcare/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
	"Sales Invoice": "public/js/sales_invoice.js",
	"Healthcare Practitioner": "public/js/healthcare_practitioner.js",
	"Patient": "public/js/patient_abdm.js",
	# ABHA Record's own "Delete/Deactivate/Reactivate via ABDM" buttons (see
	# doctype/abha_record/abha_record.js) call healthcare.regional.india.abdm.
	# AbhaLifecycleDialog, defined in this same file — without it loaded here
	# too, that class doesn't exist on the ABHA Record form and the buttons
	# throw immediately on click.
	"ABHA Record": "public/js/patient_abdm.js",
}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Dynamic, per-role login redirect: reads `home_page` live from the Role
# doctype on every login, so admin changes in the Role UI take effect
# immediately without any code change.
on_login = "healthcare.healthcare.auth.set_role_based_home_page"

# ABDM Token Registry cleanup on login/logout
on_session_creation = "healthcare.regional.india.abdm.auth.on_session_creation"
on_logout = "healthcare.regional.india.abdm.auth.on_logout"

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
jinja = {
	"methods": [
		"healthcare.healthcare.doctype.diagnostic_report.diagnostic_report.diagnostic_report_print",
		"healthcare.healthcare.utils.generate_barcodes",
		"healthcare.healthcare.doctype.observation.observation.get_observations_for_medical_record",
	]
}

# Installation
# ------------

before_install = "healthcare.install.before_install"
after_install = "healthcare.setup.setup_healthcare"

# Uninstallation
# ------------

before_uninstall = "healthcare.uninstall.before_uninstall"
after_uninstall = "healthcare.uninstall.after_uninstall"
after_migrate = "healthcare.after_migrate.execute_migrate"

# ABDM: strip stack traces from ABDM error responses; secure response headers
# (HSTS, X-Frame-Options, CSP, X-Content-Type-Options) on every response
after_exception = ["healthcare.regional.india.abdm.utils.error_handler.handle_abdm_exception"]
after_request = ["healthcare.regional.india.abdm.utils.secure_headers.add_security_headers"]

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "healthcare.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }
# has_permission = {
# 	"*": "healthcare.permissions.check_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

override_doctype_class = {
	"Sales Invoice": "healthcare.healthcare.custom_doctype.sales_invoice.HealthcareSalesInvoice",
	# Frappe v16 bug: AuditTrail.get_amended_documents() queries 'amended_from' on every
	# doctype, but non-amendable doctypes (Patient, ABHA Record, etc.) have no such column —
	# causing MySQL OperationalError (1054) whenever the Audit Trail form runs compare_document
	# on those records. SafeAuditTrail short-circuits for non-amendable doctypes.
	"Audit Trail": "healthcare.regional.india.abdm.utils.frappe_patches.SafeAuditTrail",
}

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"*": {
		"on_submit": "healthcare.healthcare.doctype.patient_history_settings.patient_history_settings.create_medical_record",
		"on_cancel": "healthcare.healthcare.doctype.patient_history_settings.patient_history_settings.delete_medical_record",
		"on_update_after_submit": "healthcare.healthcare.doctype.patient_history_settings.patient_history_settings.update_medical_record",
	},
	"Sales Invoice": {
		"on_submit": "healthcare.healthcare.utils.manage_invoice_submit_cancel",
		"on_cancel": "healthcare.healthcare.utils.manage_invoice_submit_cancel",
		"validate": "healthcare.healthcare.utils.manage_invoice_validate",
	},
	"Company": {
		"after_insert": "healthcare.healthcare.utils.create_healthcare_service_unit_tree_root",
		"on_trash": "healthcare.healthcare.utils.company_on_trash",
	},
	"Patient": {
		"on_trash": "healthcare.regional.india.abdm.utils.patient_hooks.cleanup_abdm_data_before_patient_delete",
	},
	"Payment Entry": {
		"on_submit": [
			"healthcare.healthcare.custom_doctype.payment_entry.manage_payment_entry_submit_cancel",
			"healthcare.healthcare.custom_doctype.payment_entry.set_paid_amount_in_healthcare_docs",
		],
		"on_cancel": [
			"healthcare.healthcare.custom_doctype.payment_entry.manage_payment_entry_submit_cancel",
			"healthcare.healthcare.custom_doctype.payment_entry.set_paid_amount_in_healthcare_docs",
		],
		"validate": "healthcare.healthcare.doctype.insurance_claim.insurance_claim.validate_payment_entry_and_set_claim_fields",
	},
}

scheduler_events = {
	"all": [
		"healthcare.healthcare.doctype.patient_appointment.patient_appointment.send_appointment_reminder",
	],
	"hourly": [
		"healthcare.regional.india.abdm.tasks.notify_expiring_tokens",   # warn when X-token < 2 h left
	],
	"daily": [
		"healthcare.healthcare.doctype.patient_appointment.patient_appointment.update_appointment_status",
		"healthcare.healthcare.doctype.fee_validity.fee_validity.update_validity_status",
		"healthcare.healthcare.doctype.inpatient_record.inpatient_record.add_occupied_service_unit_in_ip_to_billables",
		"healthcare.healthcare.doctype.medication_request.medication_request.update_expired_medication_requests",
		"healthcare.regional.india.abdm.tasks.refresh_expiring_tokens",  # clear expired X-tokens
		"healthcare.regional.india.abdm.tasks.purge_gateway_token_cache", # force fresh gateway token daily
	],
}

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"healthcare.tasks.all"
# 	],
# 	"daily": [
# 		"healthcare.tasks.daily"
# 	],
# 	"hourly": [
# 		"healthcare.tasks.hourly"
# 	],
# 	"weekly": [
# 		"healthcare.tasks.weekly"
# 	],
# 	"monthly": [
# 		"healthcare.tasks.monthly"
# 	],
# }

# Testing
# -------

before_tests = "healthcare.healthcare.utils.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "healthcare.event.get_events"
# }
#
# Frappe v16 workaround: get_list_settings() called without `doctype` on some list
# navigations (Frappe bug — TypeError pollutes Error Log). Our shim returns None
# gracefully instead of raising, matching the no-settings path.
override_whitelisted_methods = {
	"frappe.desk.listview.get_list_settings": "healthcare.regional.india.abdm.utils.frappe_patches.safe_get_list_settings",
}
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "healthcare.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
auto_cancel_exempted_doctypes = [
	"Inpatient Medication Entry",
]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"healthcare.auth.validate"
# ]

global_search_doctypes = {
	"Healthcare": [
		{"doctype": "Patient", "index": 1},
		{"doctype": "Medical Department", "index": 2},
		{"doctype": "Vital Signs", "index": 3},
		{"doctype": "Healthcare Practitioner", "index": 4},
		{"doctype": "Patient Appointment", "index": 5},
		{"doctype": "Healthcare Service Unit", "index": 6},
		{"doctype": "Patient Encounter", "index": 7},
		{"doctype": "Antibiotic", "index": 8},
		{"doctype": "Diagnosis", "index": 9},
		{"doctype": "Lab Test", "index": 10},
		{"doctype": "Clinical Procedure", "index": 11},
		{"doctype": "Inpatient Record", "index": 12},
		{"doctype": "Sample Collection", "index": 13},
		{"doctype": "Patient Medical Record", "index": 14},
		{"doctype": "Appointment Type", "index": 15},
		{"doctype": "Fee Validity", "index": 16},
		{"doctype": "Practitioner Schedule", "index": 17},
		{"doctype": "Dosage Form", "index": 18},
		{"doctype": "Lab Test Sample", "index": 19},
		{"doctype": "Prescription Duration", "index": 20},
		{"doctype": "Prescription Dosage", "index": 21},
		{"doctype": "Sensitivity", "index": 22},
		{"doctype": "Complaint", "index": 23},
		{"doctype": "Medical Code", "index": 24},
	]
}

healthcare_service_order_doctypes = [
	"Medication",
	"Therapy Type",
	"Lab Test Template",
	"Clinical Procedure Template",
]

domains = {
	"Healthcare": "healthcare.setup",
}

# nosemgrep
standard_portal_menu_items = [
	{
		"title": "Patient Portal",
		"route": "/patient-portal",
		"reference_doctype": "Patient",
		"role": "Patient",
	},
]

has_website_permission = {
	"Lab Test": "healthcare.healthcare.web_form.lab_test.lab_test.has_website_permission",
	"Patient Encounter": "healthcare.healthcare.web_form.prescription.prescription.has_website_permission",
	"Patient Appointment": "healthcare.healthcare.web_form.patient_appointments.patient_appointments.has_website_permission",
	"Patient": "healthcare.healthcare.web_form.personal_details.personal_details.has_website_permission",
}

standard_queries = {
	"Healthcare Practitioner": "healthcare.healthcare.doctype.healthcare_practitioner.healthcare_practitioner.get_practitioner_list"
}

treeviews = [
	"Healthcare Service Unit",
]

company_data_to_be_ignored = [
	"Healthcare Service Unit",
]
