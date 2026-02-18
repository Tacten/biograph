// Debug: Check if file is loaded
console.log("mark_unavailable.js loaded!");

frappe.provide("healthcare.appointment");

// Global function to expose for direct access from calendar view
window.show_unavailability_dialog = function() {
    healthcare.appointment.show_unavailability_dialog();
};

// Function to show the unavailability dialog
healthcare.appointment.show_unavailability_dialog = function() {
    // Create the unavailability dialog
    let d = new frappe.ui.Dialog({
        title: __("Mark Time as Unavailable"),
        fields: [
            {
                fieldname: "unavailability_for",
                label: __("Unavailability For"),
                fieldtype: "Select",
                options: ["Practitioner"],  // Removed Service Unit option
                default: "Practitioner",
                hidden: 1  // Hide this field since we only have one option
            },
            {
                fieldname: "practitioner",
                label: __("Healthcare Practitioner"),
                fieldtype: "Link",
                options: "Healthcare Practitioner",
                reqd: 1,
                onchange: function() {
                    if (this.value) {
                        frappe.call({
                            method: "frappe.client.get",
                            args: {
                                doctype: "Healthcare Practitioner",
                                name: this.value
                            },
                            callback: function(r) {
                                if (r.message && r.message.practitioner_schedules) {
                                    let service_units = [];
                                    r.message.practitioner_schedules.forEach(function(schedule) {
                                        if (schedule.service_unit) {
                                            service_units.push(schedule.service_unit);
                                        }
                                    });
                                    
                                    if (service_units.length > 0) {
                                        d.set_df_property("service_unit_info", "hidden", 0);
                                        d.set_value("service_unit_info", 
                                            __("Note: This practitioner is associated with the following service units: ") +
                                            service_units.join(", ")
                                        );
                                    } else {
                                        d.set_df_property("service_unit_info", "hidden", 1);
                                    }
                                }
                            }
                        });
                    }
                }
            },
            {
                fieldname: "service_unit_info",
                fieldtype: "HTML",
                hidden: 1
            },
            {
                fieldname: "date",
                label: __("Date"),
                fieldtype: "Date",
                reqd: 1,
                default: frappe.datetime.get_today()
            },
            {
                fieldname: "from_time",
                label: __("From Time"),
                fieldtype: "Time",
                reqd: 1,
                default: "09:00:00"
            },
            {
                fieldname: "to_time",
                label: __("To Time"),
                fieldtype: "Time",
                reqd: 1,
                default: "17:00:00"
            },
            {
                fieldname: "reason",
                label: __("Reason for Unavailability"),
                fieldtype: "Small Text"
            }
        ],
        primary_action_label: __("Check Conflicts"),
        primary_action: function() {
            let values = d.get_values();
            
            if (!values) return;
            
            if (values.from_time >= values.to_time) {
                frappe.throw(__("From Time must be before To Time"));
                return;
            }
            
            // Rest of your existing primary_action code...
            // ... existing code continues ...
        }
    });
} 