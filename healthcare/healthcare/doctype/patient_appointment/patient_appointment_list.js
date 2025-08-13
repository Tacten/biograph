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
		listview.page.add_inner_button(__("Repeat Appointments"), function() {
			window.show_recurring_dialog()
		})
		listview.page.add_inner_button(__("Mark Unavailable"), function() {
			if (typeof window.show_unavailability_dialog === 'function') {
				window.show_unavailability_dialog();
			} else {
				// Try to load the script
				frappe.require("/assets/healthcare/js/mark_unavailable.js", function() {
					window.show_unavailability_dialog();
				});
			}
		}, null, "secondary").css({
			"margin-right": "10px",
			"font-weight": "normal"
		});
	},
	
	// Custom formatter to display unavailability appointments
	formatters: {
		name: function(value, df, doc) {
			if (doc.appointment_type === "Unavailable") {
				return doc.patient_name || value;
			}
			return value;
		},
		patient: function(value, df, doc) {
			if (doc.appointment_type === "Unavailable") {
				return `<span class="indicator-pill red">
					${doc.patient_name || __('Unavailable')}
				</span>`;
			}
			return value;
		}
	}
};
