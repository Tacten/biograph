frappe.views.calendar["Patient Appointment"] = {
	field_map: {
		"start": "start",
		"end": "end",
		"id": "name",
		"title": "patient",
		"allDay": "allDay",
		"eventColor": "color"
	},
	order_by: "appointment_date",
	gantt: true,
	get_events_method: "healthcare.healthcare.doctype.patient_appointment.patient_appointment.get_events",
	
	// Replace onload with the render_event_sidebar event
	get_events_method_args: function() {
		// This method runs during calendar initialization
		console.log("Calendar initialization - setting up button");
		
		// Use setTimeout to add button after calendar renders
		setTimeout(function() {
			try {
				let cal = cur_page.page.calendar;
				if (!cal || !cal.page) {
					console.error("Calendar or page not initialized");
					return;
				}
				
				// Add Mark Unavailable button
				cal.page.add_inner_button(__("Mark Unavailable"), function() {
					if (typeof window.show_unavailability_dialog === 'function') {
						window.show_unavailability_dialog();
					} else {
						// Fallback in case script is not loaded
						frappe.require("/assets/healthcare/js/mark_unavailable.js", function() {
							window.show_unavailability_dialog();
						});
					}
				}, null, "secondary").css({
					"margin-right": "10px",
					"font-weight": "normal"
				});
				console.log("Mark Unavailable button added successfully");
			} catch (e) {
				console.error("Error adding calendar button:", e);
			}
		}, 1500); // Increased delay to ensure calendar is fully rendered
		
		return {};
	},
	
	// Use patient_name as title for Unavailable type appointments
	format_event_args: function(event) {
		if (event.appointment_type === "Unavailable") {
			event.title = event.patient_name || "Unavailable";
		}
		return event;
	}
};