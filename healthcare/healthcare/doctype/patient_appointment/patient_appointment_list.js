/*
(c) ESS 2015-16
*/
console.log("patient_appointment_list.js loaded!");

frappe.listview_settings["Patient Appointment"] = {
	filters: [["status", "=", "Open"]],
	get_indicator: function(doc) {
		var colors = {
			"Open": "orange",
			"Scheduled": "yellow",
			"Closed": "green",
			"Cancelled": "red",
			"Expired": "grey",
			"Checked In": "blue",
			"Checked Out": "orange",
			"Confirmed": "green",
			"No Show": "red",
			"Needs Rescheduling": "orange",
			"Unavailable": "red"
		};
		return [__(doc.status), colors[doc.status], "status,=," + doc.status];
	},
	
	onload: function(listview) {
		// Add "Mark Unavailable" button to the toolbar
		console.log("Adding Mark Unavailable button to list view");
		listview.page.add_inner_button(__("Mark Unavailable"), function() {
			if (typeof window.show_unavailability_dialog === 'function') {
				window.show_unavailability_dialog();
			} else {
				// Fallback in case script is not loaded
				frappe.msgprint(__("Unable to load unavailability dialog. Please refresh the page."));
				
				// Try to load the script
				frappe.require("/assets/healthcare/js/mark_unavailable.js", function() {
					window.show_unavailability_dialog();
				});
			}
		}, null, "primary", "mark-unavailable").addClass("btn-danger").css({"margin-right": "10px", "font-weight": "bold"});
		
		// Add "Cancel Unavailability" button
		listview.page.add_inner_button(__("Cancel Unavailability"), function() {
			if (typeof healthcare !== 'undefined' && healthcare.appointment && healthcare.appointment.cancel_unavailability) {
				healthcare.appointment.cancel_unavailability();
			} else {
				// Fallback in case script is not loaded
				frappe.msgprint(__("Unable to load cancel unavailability dialog. Please refresh the page."));
				
				// Try to load the script
				frappe.require("/assets/healthcare/js/mark_unavailable.js", function() {
					healthcare.appointment.cancel_unavailability();
				});
			}
		}, null, "secondary", "cancel-unavailability").addClass("btn-warning").css({"margin-right": "10px"});
	},
	
	// Custom formatter to highlight unavailability appointments
	formatters: {
		patient: function(value, df, doc) {
			if (doc.appointment_type === "Unavailable" && doc.patient === "UNAVAILABLE-BLOCK") {
				return `<span class="indicator-pill red">
					${__('Unavailable')}${doc.practitioner_name ? ': ' + doc.practitioner_name : ''}
					${doc.service_unit ? ': ' + doc.service_unit : ''}
				</span>`;
			}
			return value;
		}
	}
};
