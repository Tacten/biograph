console.log("patient_appointment_calendar.js loaded!");

frappe.views.calendar["Patient Appointment"] = {
	field_map: {
		"start": "start",
		"end": "end",
		"id": "name",
		"title": "patient_name",
		"allDay": "allDay",
		"color": "color"
	},
	order_by: "appointment_date",
	gantt: true,
	get_events_method: "healthcare.healthcare.doctype.patient_appointment.patient_appointment.get_events",
	
	filters: [["status", "!=", "Cancelled"]],
	
	onload: function(cal) {
		// Add "Mark Unavailable" button to the toolbar
		console.log("Adding Mark Unavailable button to calendar view");
		
		// Ensure the calendar is loaded before adding buttons
		if (!cal || !cal.page) {
			console.error("Calendar or page not initialized");
			return;
		}
		
		try {
			// Primary method to add button
			cal.page.add_inner_button(__("Mark Unavailable"), function() {
				if (typeof window.show_unavailability_dialog === 'function') {
					window.show_unavailability_dialog();
				} else {
					// Fallback in case script is not loaded
					frappe.require("/assets/healthcare/js/mark_unavailable.js", function() {
						window.show_unavailability_dialog();
					});
				}
			}).addClass("btn-danger mark-unavailable-btn").css({
				"margin-right": "10px",
				"font-weight": "bold",
				"color": "#fff"
			});
			
			// Add "Cancel Unavailability" button
			cal.page.add_inner_button(__("Cancel Unavailability"), function() {
				if (typeof healthcare !== 'undefined' && healthcare.appointment && healthcare.appointment.cancel_unavailability) {
					healthcare.appointment.cancel_unavailability();
				} else {
					frappe.require("/assets/healthcare/js/mark_unavailable.js", function() {
						healthcare.appointment.cancel_unavailability();
					});
				}
			}).addClass("btn-warning cancel-unavailable-btn").css({
				"margin-right": "10px",
				"color": "#fff"
			});
		} catch (e) {
			console.error("Error adding calendar buttons:", e);
		}
	},
	
	get_css_class: function(data) {
		if (data.appointment_type === "Unavailable" && data.patient === "UNAVAILABLE-BLOCK") {
			return "unavailable-appointment";
		} else if (data.status === "Needs Rescheduling") {
			return "needs-rescheduling";
		}
		return "";
	},
	
	eventRender: function(event, element, view) {
		if (event.color) {
			element.css('background-color', event.color);
			element.css('border-color', event.color);
		}
		
		if (event.appointment_type === "Unavailable") {
			element.css({
				'background-color': '#ff5858',
				'border-color': '#ff5858'
			});
		}
	}
};

// CSS for special appointment types only
frappe.dom.set_style(`
.unavailable-appointment {
	background-color: #ff5858 !important;
	border-color: #ff5858 !important;
}
.unavailable-appointment .fc-event-title,
.unavailable-appointment .fc-event-time {
	color: white !important;
}
.needs-rescheduling {
	background-color: #ffa00a !important;
	border-color: #ffa00a !important;
}
.needs-rescheduling .fc-event-title,
.needs-rescheduling .fc-event-time {
	color: white !important;
}

/* Ensure buttons are visible */
.mark-unavailable-btn {
	background-color: #ff5858 !important;
	border-color: #ff5858 !important;
	color: white !important;
}
.cancel-unavailable-btn {
	background-color: #ffa00a !important;
	border-color: #ffa00a !important;
	color: white !important;
}
`);
