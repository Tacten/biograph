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
                options: ["Practitioner", "Service Unit"],
                reqd: 1,
                hidden: 1,
                default: "Practitioner",
                onchange: function() {
                    if (this.value === "Practitioner") {
                        d.set_df_property("practitioner", "hidden", 0);
                        d.set_df_property("practitioner", "reqd", 1);
                        d.set_df_property("service_unit", "hidden", 1);
                        d.set_df_property("service_unit", "reqd", 0);
                    } else {
                        d.set_df_property("practitioner", "hidden", 1);
                        d.set_df_property("practitioner", "reqd", 0);
                        d.set_df_property("service_unit", "hidden", 0);
                        d.set_df_property("service_unit", "reqd", 1);
                    }
                }
            },
            {
                fieldname: "practitioner",
                label: __("Healthcare Practitioner"),
                fieldtype: "Link",
                options: "Healthcare Practitioner",
                reqd: 0,
                hidden: 1,
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
                fieldname: "service_unit",
                label: __("Healthcare Service Unit"),
                fieldtype: "Link",
                options: "Healthcare Service Unit",
                reqd: 0,
                hidden: 1,
                get_query: function() {
                    return {
                        filters: {
                            "allow_appointments": 1
                        }
                    };
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
            
            if (values.from_time && typeof values.from_time === 'string') {
                if (!values.from_time.includes(':')) {
                    values.from_time = values.from_time + ":00";
                }
                if (values.from_time.split(':').length === 2) {
                    values.from_time = values.from_time + ":00";
                }
            }
            
            if (values.to_time && typeof values.to_time === 'string') {
                if (!values.to_time.includes(':')) {
                    values.to_time = values.to_time + ":00";
                }
                if (values.to_time.split(':').length === 2) {
                    values.to_time = values.to_time + ":00";
                }
            }
            
            try {
                let from_datetime = frappe.datetime.str_to_obj(values.date + " " + values.from_time);
                let to_datetime = frappe.datetime.str_to_obj(values.date + " " + values.to_time);
                let duration_minutes = (to_datetime - from_datetime) / (1000 * 60);
                values.duration = duration_minutes;
            } catch (e) {
                console.error("Error calculating duration:", e);
            }
            
            frappe.show_alert({
                message: __("Checking for conflicts..."),
                indicator: "blue"
            });
            
            let formValues = {...values};
            d.hide();
            
            frappe.call({
                method: "healthcare.healthcare.doctype.patient_appointment.patient_appointment.check_unavailability_conflicts",
                args: {
                    filters: formValues
                },
                callback: function(r) {
                    if (r.message && Array.isArray(r.message) && r.message.length > 0) {
                        healthcare.appointment.show_conflict_dialog(formValues, r.message);
                    } else {
                        frappe.confirm(
                            __("Are you sure you want to mark this time as unavailable?"),
                            function() {
                                healthcare.appointment.create_unavailability(formValues);
                            }
                        );
                    }
                }
            });
        }
    });
    
    // Add custom styling to match the design
    d.$wrapper.find('.modal-dialog').css({
        'max-width': '600px',
        'margin': '1.75rem auto'
    });
    
    d.$wrapper.find('.modal-content').css({
        'border-radius': '8px'
    });
    
    d.$wrapper.find('.modal-body').css({
        'padding': '20px'
    });
    
    d.$wrapper.find('.frappe-control').css({
        'margin-bottom': '15px'
    });
    
    d.$wrapper.find('input, select, textarea').css({
        'background-color': '#f8f9fa',
        'border': '1px solid #dee2e6',
        'border-radius': '4px',
        'padding': '8px 12px'
    });
    
    d.$wrapper.find('.btn-primary').css({
        'background-color': '#000',
        'border-color': '#000',
        'border-radius': '4px',
        'padding': '8px 20px'
    });
    
    d.show();
    
    // Set initial visibility of fields
    d.set_df_property("practitioner", "hidden", 0);
    d.set_df_property("practitioner", "reqd", 1);
    d.set_df_property("service_unit", "hidden", 1);
};

// Function to show the conflict resolution dialog
healthcare.appointment.show_conflict_dialog = function(values, conflicts) {
    // Ensure conflicts is an array and not empty
    if (!conflicts || !Array.isArray(conflicts) || conflicts.length === 0) {
        // If no conflicts exist, show confirmation and proceed
        frappe.confirm(
            __("Are you sure you want to mark this time as unavailable?"),
            function() {
                // Proceed with creating the unavailability with no conflicts
                healthcare.appointment.create_unavailability(values);
            }
        );
        return;
    }
    
    // If we have conflicts, show them and prevent proceeding
    let conflict_html = `<div class="conflicts-container">
        <div class="alert alert-danger">
            <strong>${__("Cannot mark as unavailable!")}</strong> ${__("The following appointments conflict with the selected time:")}
        </div>
        <div class="conflict-list" style="max-height: 300px; overflow-y: auto;">
            <table class="table table-bordered">
                <thead>
                    <tr>
                        <th>${__("Patient")}</th>
                        <th>${__("Time")}</th>
                        <th>${__("Type")}</th>
                        <th>${__("Status")}</th>
                    </tr>
                </thead>
                <tbody>`;
    
    // Add each conflict to the table
    conflicts.forEach(function(conflict) {
        conflict_html += `<tr>
            <td>${conflict.patient_name || conflict.patient}</td>
            <td>${conflict.appointment_time}</td>
            <td>${conflict.appointment_type || ""}</td>
            <td>${conflict.status}</td>
        </tr>`;
    });
    
    conflict_html += `</tbody>
            </table>
        </div>
        <div class="alert alert-info mt-3">
            ${__("Total conflicting appointments: ")} <strong>${conflicts.length}</strong>
        </div>
        <div class="alert alert-warning">
            <strong>${__("Important:")}</strong> ${__("You must cancel these appointments before marking this time as unavailable.")}
        </div>
    </div>`;
    
    let d = new frappe.ui.Dialog({
        title: __("Appointment Conflicts Detected"),
        fields: [
            {
                fieldtype: "HTML",
                fieldname: "conflicts_html",
                options: conflict_html
            }
        ],
        primary_action_label: __("Go Back"),
        primary_action: function() {
            d.hide();
            // Re-open the unavailability dialog
            healthcare.appointment.show_unavailability_dialog();
        }
    });
    
    d.show();
};

// Function to create an unavailability appointment
healthcare.appointment.create_unavailability = function(values) {
    console.log("Creating unavailability with values:", values);
    
    // Ensure times have proper format with seconds
    if (values.from_time && typeof values.from_time === 'string') {
        // Make sure from_time is in the HH:MM:SS format
        if (!values.from_time.includes(':')) {
            values.from_time = values.from_time + ":00";
        }
        if (values.from_time.split(':').length === 2) {
            values.from_time = values.from_time + ":00";
        }
        console.log("Formatted from_time:", values.from_time);
    }
    
    if (values.to_time && typeof values.to_time === 'string') {
        // Make sure to_time is in the HH:MM:SS format
        if (!values.to_time.includes(':')) {
            values.to_time = values.to_time + ":00";
        }
        if (values.to_time.split(':').length === 2) {
            values.to_time = values.to_time + ":00";
        }
        console.log("Formatted to_time:", values.to_time);
    }
    
    // Calculate duration to verify it's correct
    if (values.from_time && values.to_time && values.date) {
        try {
            let from_datetime = frappe.datetime.str_to_obj(values.date + " " + values.from_time);
            let to_datetime = frappe.datetime.str_to_obj(values.date + " " + values.to_time);
            let duration_minutes = (to_datetime - from_datetime) / (1000 * 60);
            console.log(`Duration calculated: ${duration_minutes} minutes`);
            
            // Set the duration explicitly
            values.duration = duration_minutes;
        } catch (e) {
            console.error("Error calculating duration:", e);
        }
    }
    
    // Log the final data being sent to the server
    console.log("Final data for unavailability creation:", {
        date: values.date,
        from_time: values.from_time,
        to_time: values.to_time,
        duration: values.duration
    });
    
    // Show freeze message to prevent user interaction during creation
    frappe.show_alert({
        message: __("Creating unavailability record..."),
        indicator: "blue"
    });
    
    // Create the unavailability appointment
    frappe.call({
        method: "healthcare.healthcare.doctype.patient_appointment.patient_appointment.create_unavailability_appointment",
        args: {
            data: values
        },
        freeze: true,
        freeze_message: __("Creating unavailability record..."),
        callback: function(r) {
            if (r.message) {
                console.log("Unavailability creation response:", r.message);
                
                frappe.show_alert({
                    message: __("Time marked as unavailable successfully"),
                    indicator: "green"
                }, 5);
                
                // Refresh the list view or calendar view if we're on one
                if (cur_list && cur_list.doctype === "Patient Appointment") {
                    cur_list.refresh();
                } else if (cur_calendar && cur_calendar.doctype === "Patient Appointment") {
                    cur_calendar.refresh();
                }
            } else {
                console.error("Failed to create unavailability:", r);
                frappe.msgprint({
                    title: __("Error"),
                    indicator: 'red',
                    message: __("Failed to mark time as unavailable. Please check the console and server logs.")
                });
            }
        },
        error: function(r) {
            console.error("API error when creating unavailability:", r);
            frappe.msgprint({
                title: __("Error"),
                indicator: 'red',
                message: __("Failed to communicate with the server. Please try again.")
            });
        }
    });
};

// Function to cancel an unavailability appointment
healthcare.appointment.cancel_unavailability = function(date) {
    // If no date provided, ask for one
    if (!date) {
        let d = new frappe.ui.Dialog({
            title: __("Cancel Unavailability"),
            fields: [
                {
                    fieldname: "date",
                    label: __("Date"),
                    fieldtype: "Date",
                    reqd: 1,
                    default: frappe.datetime.get_today()
                }
            ],
            primary_action_label: __("Get Unavailability"),
            primary_action: function() {
                let values = d.get_values();
                if (values.date) {
                    get_unavailability_for_date(values.date);
                    d.hide();
                }
            }
        });
        d.show();
    } else {
        get_unavailability_for_date(date);
    }
    
    function get_unavailability_for_date(selected_date) {
        frappe.call({
            method: "healthcare.healthcare.doctype.patient_appointment.patient_appointment.get_unavailability_appointments",
            args: {
                date: selected_date
            },
            callback: function(r) {
                if (r.message && r.message.length > 0) {
                    show_unavailability_list(r.message);
                } else {
                    frappe.msgprint(__("No unavailability records found for the selected date."));
                }
            }
        });
    }
    
    function show_unavailability_list(unavailability_list) {
        let options = [];
        unavailability_list.forEach(function(unavailability) {
            let label = "";
            if (unavailability.practitioner) {
                label += __("Practitioner") + ": " + unavailability.practitioner_name;
            } else if (unavailability.service_unit) {
                label += __("Service Unit") + ": " + unavailability.service_unit;
            }
            label += " | " + __("Time") + ": " + unavailability.appointment_time + " - " + unavailability.end_time;
            if (unavailability.reason) {
                label += " | " + __("Reason") + ": " + unavailability.reason;
            }
            
            options.push({
                label: label,
                value: unavailability.name
            });
        });
        
        let d = new frappe.ui.Dialog({
            title: __("Select Unavailability to Cancel"),
            fields: [
                {
                    fieldname: "unavailability",
                    label: __("Unavailability Record"),
                    fieldtype: "Select",
                    options: options.map(opt => opt.value),
                    get_label: function(value) {
                        let selected = options.find(opt => opt.value === value);
                        return selected ? selected.label : value;
                    }
                }
            ],
            primary_action_label: __("Cancel Selected Unavailability"),
            primary_action: function() {
                let values = d.get_values();
                if (values.unavailability) {
                    frappe.confirm(
                        __("Are you sure you want to cancel this unavailability record?"),
                        function() {
                            frappe.call({
                                method: "healthcare.healthcare.doctype.patient_appointment.patient_appointment.cancel_unavailability_appointment",
                                args: {
                                    appointment_name: values.unavailability
                                },
                                freeze: true,
                                freeze_message: __("Cancelling unavailability record..."),
                                callback: function(r) {
                                    if (r.message === true) {
                                        frappe.show_alert({
                                            message: __("Unavailability record cancelled successfully"),
                                            indicator: "green"
                                        }, 5);
                                        
                                        // Refresh the views
                                        if (cur_list && cur_list.doctype === "Patient Appointment") {
                                            cur_list.refresh();
                                        } else if (cur_calendar && cur_calendar.doctype === "Patient Appointment") {
                                            cur_calendar.refresh();
                                        }
                                        
                                        d.hide();
                                    }
                                }
                            });
                        }
                    );
                }
            }
        });
        
        d.show();
    }
}; 