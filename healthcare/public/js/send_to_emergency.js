// Copyright (c) 2026, earthians Health Informatics Pvt. Ltd. and contributors
// For license information, please see license.txt

// Adds a "Send to Emergency" action on Patient Appointment and Patient Encounter
// that opens a new Emergency Record pre-filled from the source document.

frappe.provide("healthcare.emergency");

healthcare.emergency.SOURCE_DOCTYPES = ["Patient Appointment", "Patient Encounter"];

healthcare.emergency.send_to_emergency = function (frm) {
	frappe.route_options = {
		patient: frm.doc.patient,
		company: frm.doc.company,
		attending_practitioner: frm.doc.practitioner,
		medical_department: frm.doc.medical_department || frm.doc.department,
	};
	frappe.new_doc("Emergency Record");
};

healthcare.emergency.SOURCE_DOCTYPES.forEach(doctype => {
	frappe.ui.form.on(doctype, {
		refresh(frm) {
			if (frm.is_new() || !frm.doc.patient) {
				return;
			}
			frm.add_custom_button(
				__("Send to Emergency"),
				() => healthcare.emergency.send_to_emergency(frm),
				__("Create"),
			);
		},
	});
});
