console.log("patient_appointment_calendar.js loaded!");

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
	
	// Custom event rendering to highlight unavailability appointments
	filters: [["status", "!=", "Cancelled"]],
	
	onload: function(cal) {
		// Add "Mark Unavailable" button to the toolbar
		console.log("Adding Mark Unavailable button to calendar view");
		
		// Primary method to add button
		cal.page.add_inner_button(__("Mark Unavailable"), function() {
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
		cal.page.add_inner_button(__("Cancel Unavailability"), function() {
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
		
		// Backup method to add button to the FullCalendar header
		setTimeout(function() {
			if (cal.cal) {
				let $calendarHeader = $(cal.cal.el).find('.fc-header-toolbar .fc-toolbar-chunk:last');
				if ($calendarHeader.length && $calendarHeader.find('.mark-unavailable-btn').length === 0) {
					$calendarHeader.append(`
						<button class="btn btn-danger mark-unavailable-btn" 
							style="margin-left: 10px; font-weight: bold;">
							${__("Mark Unavailable")}
						</button>
					`);
					
					$calendarHeader.append(`
						<button class="btn btn-warning cancel-unavailable-btn" 
							style="margin-left: 10px;">
							${__("Cancel Unavailability")}
						</button>
					`);
					
					$calendarHeader.find('.mark-unavailable-btn').on('click', function() {
						if (typeof window.show_unavailability_dialog === 'function') {
							window.show_unavailability_dialog();
						} else {
							frappe.require("/assets/healthcare/js/mark_unavailable.js", function() {
								window.show_unavailability_dialog();
							});
						}
					});
					
					$calendarHeader.find('.cancel-unavailable-btn').on('click', function() {
						if (typeof healthcare !== 'undefined' && healthcare.appointment && healthcare.appointment.cancel_unavailability) {
							healthcare.appointment.cancel_unavailability();
						} else {
							frappe.require("/assets/healthcare/js/mark_unavailable.js", function() {
								healthcare.appointment.cancel_unavailability();
							});
						}
					});
				}
			}
		}, 1000); // Wait for FullCalendar to initialize
	},
	
	// Custom event rendering for unavailability appointments
	get_css_class: function(data) {
		if (data.appointment_type === "Unavailable" && data.patient === "UNAVAILABLE-BLOCK") {
			return "unavailable-appointment";
		} else if (data.status === "Needs Rescheduling") {
			return "needs-rescheduling";
		}
		return "";
	},
	
	// Custom event content for unavailability appointments
	eventContent: function(eventInfo) {
		const event = eventInfo.event;
		const eventData = event.extendedProps;
		
		if (eventData.appointment_type === "Unavailable" && eventData.patient === "UNAVAILABLE-BLOCK") {
			let timeText = eventInfo.timeText || "";
			let title = __("Unavailable");
			
			if (eventData.practitioner_name) {
				title += ": " + eventData.practitioner_name;
			} else if (eventData.service_unit) {
				title += ": " + eventData.service_unit;
			}
			
			let reason = eventData.notes || "";
			
			return { 
				html: `
					<div class="fc-event-time">${timeText}</div>
					<div class="fc-event-title">${title}</div>
					${reason ? `<div class="fc-event-reason">${reason}</div>` : ''}
				`
			};
		}
		
		return false; // Use default rendering for other events
	}
};

// CSS for unavailability appointments
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
`);
