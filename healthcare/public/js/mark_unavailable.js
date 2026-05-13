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
            { fieldtype: 'Section Break' },
            {
                fieldname: "practitioner",
                label: __("Healthcare Practitioner"),
                fieldtype: "Link",
                options: "Healthcare Practitioner",
                reqd: 0,
                onchange: function() 
                {
                    d.set_value("service_unit", "");
                    let su_field = d.fields_dict["service_unit"];
                    if (su_field) {
                        su_field.refresh && su_field.refresh();
                        if (su_field.$input) su_field.$input.val("");
                    }

                    if (this.value) {
                        frappe.call({
                            method: "frappe.client.get",
                            args: {
                                doctype: "Healthcare Practitioner",
                                name: this.value
                            },
                            callback: function(r) {
                                if (r.message && r.message.practitioner_schedules) {
                                    let child_units = [];
                                    r.message.practitioner_schedules.forEach(function(schedule) {
                                        if (schedule.service_unit && !child_units.includes(schedule.service_unit)) {
                                            child_units.push(schedule.service_unit);
                                        }
                                    });

                                    if (child_units.length > 0) {
                                        all_service_units = child_units.slice().sort();
                                        refresh_service_unit_options();
                                    } else {
                                        all_service_units = [];
                                        d.set_df_property("service_unit", "options", "");
                                        d.fields_dict["service_unit"].set_data([]);
                                        frappe.show_alert({
                                            message: __("No service units linked to this practitioner."),
                                            indicator: "orange"
                                        }, 4);
                                    }
                                }
                            }
                        });
                    } else {
                        load_all_service_units();
                    }
                }
            },
            { fieldtype: 'Column Break' },
            {
                fieldname: "service_unit",
                label: __("Healthcare Service Unit"),
                fieldtype: "MultiSelect",
                options: "",
                reqd: 0,
                onchange: function() {
                    let raw = d.get_value("service_unit") || "";
                    let parts = raw.split(",").map(s => s.trim()).filter(Boolean);
                    let unique = [...new Set(parts)];
                    let normalised = unique.length ? unique.join(",") + "," : " ";
                    if (normalised !== raw) {
                        d.set_value("service_unit", normalised);
                    }
                    // Remove already-selected units from dropdown options
                    setTimeout(function() {
                        refresh_service_unit_options();
                        // Re-trigger input to auto-open the dropdown
                        let su_field = d.fields_dict["service_unit"];
                        if (su_field && su_field.$input) {
                            su_field.$input.trigger("input");
                        }
                    }, 150);
                }
            },

            // ── Row 2: Start Date + From Time | To Time ──────────────────────
            { fieldtype: 'Section Break' },
            {
                fieldname: "from_date",
                label: __("Start Date"),
                fieldtype: "Date",
                reqd: 1,
                onchange: function() {
                    if (this.value) {
                        let _p = this.value.split("-");
                        let _sel = new Date(parseInt(_p[0]), parseInt(_p[1]) - 1, parseInt(_p[2]));
                        if (_sel.getDay() === 0) {  // Sunday — weekoff
                            _sel.setDate(_sel.getDate() + 1);  // advance to Monday
                            let _monday = _sel.getFullYear() + "-"
                                + String(_sel.getMonth() + 1).padStart(2, "0") + "-"
                                + String(_sel.getDate()).padStart(2, "0");
                            frappe.show_alert({
                                message: __("Sunday is weekoff. Start Date moved to Monday."),
                                indicator: "orange"
                            }, 4);
                            d.set_value("from_date", _monday);
                            return;
                        }
                        if (this.value < frappe.datetime.get_today()) {
                            frappe.show_alert({
                                message: __("Start Date cannot be a past date."),
                                indicator: "red"
                            }, 4);
                            d.set_value("from_date", frappe.datetime.get_today());
                        }
                    }
                }
            },
            {
                fieldname: "to_time",
                label: __("To Time"),
                fieldtype: "Time",
                reqd: 1,
                default: "20:00:00"
            },
            { fieldtype: 'Column Break' },
            {
                fieldname: "from_time",
                label: __("From Time"),
                fieldtype: "Time",
                reqd: 1,
                default: "07:00:00"
            },
            { fieldtype: 'Section Break' },
            {
                fieldname: "repeat_on",
                label: __("Repeat On"),
                fieldtype: "Select",
                options: "Daily\nWeekly\nMonthly\nYearly",
                reqd: 1,
                onchange: function () {
                    let selected = d.get_value("repeat_on");
                    if (selected === "Daily") {
                        d.set_value("repeat_interval", 1);
                        d.set_df_property("repeat_interval", "hidden", 1);
                    } else {
                        d.set_value("repeat_interval", 1);
                        d.set_df_property("repeat_interval", "hidden", 0);
                    }
                    d.set_df_property("week_days", "hidden", selected !== "Weekly");
                }
            },
            {
                fieldname: "repeat_interval",
                label: __("Repeat Every (days)"),
                fieldtype: "Int",
                default: 1,
                hidden: 1,
                reqd: 0,
            },
            { fieldtype: 'Column Break' },
            {
                fieldname: "repeat_till",
                label: __("Repeat Till"),
                fieldtype: "Date",
                reqd: 0,
                onchange: function() {
                    let from = d.get_value("from_date") || frappe.datetime.get_today();
                    if (this.value && this.value < from) {
                        frappe.show_alert({
                            message: __("Repeat Till cannot be before the Start Date."),
                            indicator: "red"
                        }, 4);
                        d.set_value("repeat_till", from);
                    }
                }
            },
            { fieldtype: 'Section Break', fieldname: 'week_days', hidden: 1, label: __("Select Days") },
            { fieldtype: 'Check', fieldname: 'monday',    label: __('Monday') },
            { fieldtype: 'Check', fieldname: 'tuesday',   label: __('Tuesday') },
            { fieldtype: 'Column Break', fieldname: 'day_break2' },
            { fieldtype: 'Check', fieldname: 'wednesday', label: __('Wednesday') },
            { fieldtype: 'Check', fieldname: 'thursday',  label: __('Thursday') },
            { fieldtype: 'Column Break', fieldname: 'day_break4' },
            { fieldtype: 'Check', fieldname: 'friday',    label: __('Friday') },
            { fieldtype: 'Check', fieldname: 'saturday',  label: __('Saturday') },
            { fieldtype: 'Column Break', fieldname: 'day_break6' },
            { fieldtype: 'Check', fieldname: 'sunday',    label: __('Sunday'), hidden: 1 },  // permanent holiday
            { fieldtype: 'Section Break' },
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

            // For Weekly repeat, at least one day must be selected
            if (values.repeat_on === "Weekly") {
                let day_fields = ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"];
                let selected_days = day_fields.filter(day => values[day]);
                if (!selected_days.length) {
                    frappe.throw(__("Please select at least one day for Weekly recurrence."));
                    return;
                }
                values.week_days = selected_days;
            }

            // Normalise times to HH:MM:SS
            ["from_time", "to_time"].forEach(function(key) {
                if (values[key] && typeof values[key] === "string") {
                    if (!values[key].includes(":")) {
                        values[key] += ":00:00";
                    } else if (values[key].split(":").length === 2) {
                        values[key] += ":00";
                    }
                }
            });

            // Backend expects 'date' (start) and 'to_date' (end of recurrence range)
            values.date    = values.from_date;
            values.to_date = values.repeat_till || values.from_date;

            // Duration per occurrence (minutes)
            try {
                let fd = frappe.datetime.str_to_obj(values.from_date + " " + values.from_time);
                let td = frappe.datetime.str_to_obj(values.from_date + " " + values.to_time);
                values.duration = (td - fd) / (1000 * 60);
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
                        healthcare.appointment.show_dates_confirmation_dialog(formValues);
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

    d.$wrapper.find('input, textarea').css({
        'background-color': '#f8f9fa',
        'border': '1px solid #dee2e6',
        'border-radius': '4px',
        'padding': '8px 12px'
    });
    d.$wrapper.find('select').css({
        'background-color': '#f8f9fa',
        'border': '1px solid #dee2e6',
        'border-radius': '4px'
    });

    d.$wrapper.find('.btn-primary').css({
        'background-color': '#000',
        'border-color': '#000',
        'border-radius': '4px',
        'padding': '8px 20px'
    });

    d.show();

    // Block past dates and Sundays (weekoff) on the datepicker widgets
    let today_obj = frappe.datetime.str_to_obj(frappe.datetime.get_today());
    let _dp_opts = {
        minDate: today_obj,
        onRenderCell({ date, cellType }) {
            if (cellType === "day" && date.getDay() === 0) {
                return { disabled: true, classes: "sunday-weekoff" };
            }
        }
    };
    let from_date_field = d.fields_dict["from_date"];
    if (from_date_field && from_date_field.datepicker) {
        from_date_field.datepicker.update(_dp_opts);
    }
    let repeat_till_field = d.fields_dict["repeat_till"];
    if (repeat_till_field && repeat_till_field.datepicker) {
        repeat_till_field.datepicker.update(_dp_opts);
    }

    // Tracks the full list of available service units for the current context
    let all_service_units = [];

    // Helper: refresh MultiSelect options excluding already-selected units
    function refresh_service_unit_options() {
        let raw = d.get_value("service_unit") || "";
        let selected = raw.split(",").map(s => s.trim()).filter(Boolean);
        let remaining = all_service_units.filter(u => !selected.includes(u));
        let opts = remaining.join("\n");
        d.set_df_property("service_unit", "options", opts);
        d.fields_dict["service_unit"].set_data(opts);
    }

    // Load all service units as initial MultiSelect options
    load_all_service_units();

    function load_all_service_units() {
        frappe.call({
            method: "healthcare.healthcare.doctype.patient_appointment.patient_appointment.get_all_service_units",
            callback: function(r) {
                console.log("Healthcare Service Units fetched:", r.message);
                if (r.message && r.message.length > 0) {
                    all_service_units = r.message.map(function(su) { return su.name; });
                } else {
                    all_service_units = [];
                }
                refresh_service_unit_options();
            },
            error: function(err) {
                console.error("Failed to fetch Healthcare Service Units:", err);
            }
        });
    }
};

// Function to show the conflict resolution dialog
healthcare.appointment.show_conflict_dialog = function(values, conflicts) {
    // Ensure conflicts is an array and not empty
    if (!conflicts || !Array.isArray(conflicts) || conflicts.length === 0) {
        // If no conflicts exist, show date confirmation and proceed
        healthcare.appointment.show_dates_confirmation_dialog(values);
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

// Function to preview all recurrence dates and confirm before creating unavailability
healthcare.appointment.show_dates_confirmation_dialog = function(values) {
    // Parse a YYYY-MM-DD string into a local Date without timezone shift
    function parse_date(s) {
        let p = s.split("-");
        return new Date(parseInt(p[0]), parseInt(p[1]) - 1, parseInt(p[2]));
    }

    let from_date = parse_date(values.from_date || values.date);
    let to_date   = parse_date(values.repeat_till || values.to_date || values.from_date || values.date);
    let repeat_on = values.repeat_on || "Daily";
    let interval  = Math.max(parseInt(values.repeat_interval) || 1, 1);
    let week_days = values.week_days || [];

    const day_map  = { monday:1, tuesday:2, wednesday:3, thursday:4, friday:5, saturday:6, sunday:0 };
    const day_abbr = ["Sun","Mon","Tue","Wed","Thu","Fri","Sat"];
    const mon_abbr = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];

    // Compute all matching dates client-side (mirrors backend _get_recurrence_dates)
    let dates = [];
    let current = new Date(from_date);

    if (repeat_on === "Weekly") {
        let selected = new Set(week_days.map(d => day_map[d.toLowerCase()]));
        while (current <= to_date) {
            if (selected.has(current.getDay())) dates.push(new Date(current));
            current.setDate(current.getDate() + 1);
        }
    } else if (repeat_on === "Monthly") {
        let target_day = from_date.getDate();
        while (current <= to_date) {
            dates.push(new Date(current));
            let m = current.getMonth() + interval;
            let y = current.getFullYear() + Math.floor(m / 12);
            m = m % 12;
            let max_d = new Date(y, m + 1, 0).getDate();
            current = new Date(y, m, Math.min(target_day, max_d));
        }
    } else if (repeat_on === "Yearly") {
        while (current <= to_date) {
            dates.push(new Date(current));
            current = new Date(current.getFullYear() + interval, current.getMonth(), current.getDate());
        }
    } else {
        // Daily (default)
        while (current <= to_date) {
            dates.push(new Date(current));
            current.setDate(current.getDate() + interval);
        }
    }

    // Remove Sundays — permanent holiday
    dates = dates.filter(dt => dt.getDay() !== 0);

    // Build summary info lines
    let practitioner_line = values.practitioner
        ? `<tr><td><strong>${__("Practitioner")}</strong></td><td>${values.practitioner}</td></tr>` : "";
    let su_raw = values.service_unit || "";
    let sus = su_raw.split(",").map(s => s.trim()).filter(Boolean);
    let su_line = sus.length
        ? `<tr><td><strong>${__("Service Unit(s)")}</strong></td><td>${sus.join(", ")}</td></tr>` : "";
    let time_line = `<tr><td><strong>${__("Time")}</strong></td><td>${values.from_time || ""} – ${values.to_time || ""}</td></tr>`;
    let repeat_desc = repeat_on;
    if (repeat_on === "Weekly" && week_days.length) {
        repeat_desc += ` (${week_days.map(d => d.charAt(0).toUpperCase() + d.slice(1)).join(", ")})`;
    } else if (interval > 1) {
        repeat_desc += ` (every ${interval})`;
    }
    let repeat_line = `<tr><td><strong>${__("Recurrence")}</strong></td><td>${repeat_desc}</td></tr>`;

    // Render date badges
    function render_date_badges(dates) {
        return dates.map(function(dt) {
            return `<span style="display:inline-block;margin:2px 3px;padding:3px 8px;border-radius:4px;
                                background:#f0f0f0;border:1px solid #ccc;color:#333;
                                font-size:12px;font-weight:500;">
                        ${day_abbr[dt.getDay()]}, ${dt.getDate()} ${mon_abbr[dt.getMonth()]} ${dt.getFullYear()}
                    </span>`;
        }).join("");
    }

    let date_badges = render_date_badges(dates);
    let html = `
        <table class="table table-borderless" style="margin-bottom:10px;font-size:13px;">
            <tbody>${practitioner_line}${su_line}${time_line}${repeat_line}</tbody>
        </table>
        <div style="margin-bottom:8px;font-size:13px;">
            <strong>${dates.length} ${dates.length === 1 ? __("date") : __("dates")} ${__("in selected range")}:</strong>
        </div>
        <div style="max-height:180px;overflow-y:auto;padding:8px;background:#f8f9fa;
                    border:1px solid #dee2e6;border-radius:4px;">
            ${date_badges || `<em>${__("No dates calculated")}</em>`}
        </div>`;

    let confirm_dialog = new frappe.ui.Dialog({
        title: __("Confirm: Mark as Unavailable"),
        fields: [{ fieldtype: "HTML", fieldname: "preview_html", options: html }],
        primary_action_label: __("Confirm & Proceed"),
        secondary_action_label: __("Go Back"),
        primary_action: function() {
            confirm_dialog.hide();
            healthcare.appointment.create_unavailability(values);
        },
        secondary_action: function() {
            confirm_dialog.hide();
            healthcare.appointment.show_unavailability_dialog();
        }
    });
    confirm_dialog.show();
};

// Function to create an unavailability appointment
healthcare.appointment.create_unavailability = function(values) {
    // Ensure times have proper format HH:MM:SS
    ["from_time", "to_time"].forEach(function(key) {
        if (values[key] && typeof values[key] === "string") {
            if (!values[key].includes(":")) {
                values[key] += ":00:00";
            } else if (values[key].split(":").length === 2) {
                values[key] += ":00";
            }
        }
    });

    // Ensure date and to_date are set
    values.date    = values.date    || values.from_date;
    values.to_date = values.to_date || values.repeat_till || values.from_date;

    // Recalculate duration (per occurrence, in minutes)
    try {
        let fd = frappe.datetime.str_to_obj(values.date + " " + values.from_time);
        let td = frappe.datetime.str_to_obj(values.date + " " + values.to_time);
        values.duration = (td - fd) / (1000 * 60);
    } catch (e) {
        console.error("Error calculating duration:", e);
    }

    frappe.show_alert({ message: __("Submitting unavailability request..."), indicator: "blue" });

    frappe.call({
        method: "healthcare.healthcare.doctype.patient_appointment.patient_appointment.schedule_unavailability_creation",
        args: { data: values },
        callback: function(r) {
            if (!r.message) {
                frappe.msgprint({
                    title: __("Error"),
                    indicator: "red",
                    message: __("Failed to mark time as unavailable. Please check the server logs.")
                });
                return;
            }

            if (r.message.queued) {
                // Large range — job is running in background; notify when done
                frappe.show_alert({
                    message: __(
                        "Creating {0} unavailability record(s) in the background. You will be notified when done.",
                        [r.message.count]
                    ),
                    indicator: "blue"
                }, 8);

                frappe.realtime.on("unavailability_creation_done", function(data) {
                    frappe.realtime.off("unavailability_creation_done");
                    if (data.success) {
                        frappe.show_alert({
                            message: __(
                                "{0} unavailability record(s) created successfully.",
                                [data.count]
                            ),
                            indicator: "green"
                        }, 5);
                    } else {
                        frappe.show_alert({
                            message: __("Some records could not be created. Please check the Error Log."),
                            indicator: "red"
                        }, 8);
                    }
                    if (cur_list && cur_list.doctype === "Patient Appointment") {
                        cur_list.refresh();
                    } else if (cur_calendar && cur_calendar.doctype === "Patient Appointment") {
                        cur_calendar.refresh();
                    }
                });

            } else {
                // Small range — completed synchronously
                frappe.show_alert({
                    message: __(
                        r.message.count === 1
                            ? "Time marked as unavailable successfully"
                            : "{0} unavailability records created successfully",
                        [r.message.count]
                    ),
                    indicator: "green"
                }, 5);
                if (cur_list && cur_list.doctype === "Patient Appointment") {
                    cur_list.refresh();
                } else if (cur_calendar && cur_calendar.doctype === "Patient Appointment") {
                    cur_calendar.refresh();
                }
            }
        },
        error: function(r) {
            console.error("API error when creating unavailability:", r);
            frappe.msgprint({
                title: __("Error"),
                indicator: "red",
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