// Copyright (c) 2026, earthians Health Informatics Pvt. Ltd. and contributors
// For license information, please see license.txt

// Shows the triage acuity colour of a patient's active Emergency Record as a
// dashboard headline on any clinical doctype, to speed-track ED activity.

frappe.provide("healthcare.emergency");

healthcare.emergency.TRIAGE_DOCTYPES = [
	"Patient Encounter",
	"Service Request",
	"Medication Request",
	"Observation",
	"Patient Appointment",
	"Therapy Session",
	"Therapy Plan",
	"Lab Test",
	"Inpatient Record",
	"Emergency Record",
	"Patient",
];

healthcare.emergency.show_triage = function (frm) {
	if (frm.is_new() || !frm.doc.patient) {
		frm.dashboard.set_headline("");
		return;
	}
	frappe
		.xcall(
			"healthcare.healthcare.doctype.emergency_record.emergency_record.get_active_triage",
			{
				patient: frm.doc.patient,
			},
		)
		.then(triage => {
			if (!triage) {
				frm.dashboard.set_headline("");
				return;
			}
			const color = triage.color || "#a6b1b9";
			frm.dashboard.set_headline(
				`<span style="display:inline-flex;align-items:center;gap:8px">
					<span style="width:12px;height:12px;border-radius:50%;background:${color}"></span>
					<b>${__("Triage")}: ${frappe.utils.escape_html(triage.triage_level)}</b>
					<a href="/app/emergency-record/${encodeURIComponent(triage.emergency_record)}">
						${frappe.utils.escape_html(triage.emergency_record)}
					</a>
				</span>`,
			);
		})
		.catch(() => frm.dashboard.set_headline(""));
};

healthcare.emergency.TRIAGE_DOCTYPES.forEach(doctype => {
	frappe.ui.form.on(doctype, {
		refresh: frm => healthcare.emergency.show_triage(frm),
		patient: frm => healthcare.emergency.show_triage(frm),
	});
});
