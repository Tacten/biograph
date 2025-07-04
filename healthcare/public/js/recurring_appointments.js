frappe.provide("healthcare.appointment");


window.show_recurring_dialog = function() {
    healthcare.appointment.show_recurring_dialog();
};

healthcare.appointment.show_recurring_dialog = function() {
    open_repeat_dialog()
}



function open_repeat_dialog() {
    let repeat_on = ""
    let selected_practitioner = '';
    let d = new frappe.ui.Dialog({
        title: "Repeat Appointment",
        size: "extra-large",
        fields: [
            { fieldtype: 'Section Break', fieldname: "first_section_break" },
            {
                label: "Patient",
                fieldname: "patient",
                fieldtype: "Link",
                options: "Patient",
                reqd: 1
            },
            {
                label: "Appointment Type",
                fieldname: "appointment_type",
                fieldtype: "Link",
                options: "Appointment Type",
                reqd: 1,
                default : "Therapy Session"
            },
            { fieldtype: 'Column Break', fieldname: "first_column_break" },
            {
                label: "Healthcare Practitioner",
                fieldname: "practitioner",
                fieldtype: "Link",
                options: "Healthcare Practitioner",
                reqd: 1,
                onchange: function () {
                    let practitioner = d.get_value("practitioner");
                    if (practitioner) {
                        frappe.db.get_value("Healthcare Practitioner", practitioner, "department")
                            .then(r => {
                                console.log(r.message)
                                if (r.message && r.message.department) {
                                    
                                    d.set_value("medical_department", r.message.department);
                                    d.refresh()
                                } else {
                                    d.set_value("medical_department", null);
                                }
                            });
                    } else {
                        d.set_value("medical_department", null);
                    }
                }
            },
            {
                label: "Therapy Plan",
                fieldname: "therapy_plan",
                fieldtype: "Link",
                options: "Therapy Plan",
                hidden: 0,
                reqd: 0 
            },
            { fieldtype: 'Column Break', fieldname: "second_column_break" },
            {
                label: "Medical Department",
                fieldname: "medical_department",
                fieldtype: "Link",
                options: "Medical Department",
                reqd: 1
            },
            {
                label: "Service Unit",
                fieldname: "service_unit",
                fieldtype: "Link",
                options: "Healthcare Service Unit",
                reqd: 1
            },
            { fieldtype: 'Section Break', fieldname: "second_section_break" },
            {
                label: "Start Date",
                fieldname: "from_date",
                fieldtype: "Date",
                reqd: 1,
            },
            { fieldtype: 'Column Break', fieldname: "1a_column_break" },
            {
                label: "From Time",
                fieldname: "from_time",
                fieldtype: "Time",
                reqd: 1
            },
            { fieldtype: 'Column Break', fieldname: "1b_column_break" },
            {
                label: "To Time",
                fieldname: "to_time",
                fieldtype: "Time",
                reqd: 1
            },
            { fieldtype: 'Section Break', fieldname: "5_section_break" },
            {
                label: "Repeat On",
                fieldname: "repeat_on",
                fieldtype: "Select",
                options: "Daily\nWeekly\nMonthly\nYearly",
                reqd: 1,
                onchange: function () {
                    let selected = d.get_value("repeat_on");
                    if(selected == "Daily"){
                        d.set_value("repeat_interval",1)
                        d.set_df_property("repeat_interval", "hidden", 1)
                    }else{
                        d.set_value("repeat_interval",1)
                        d.set_df_property("repeat_interval", "hidden", 0)
                    }
                    // Show week day options only if "Weekly" is selected
                    const show_week_days = selected === "Weekly";
                    if(selected == "Weekly"){
                        d.set_df_property("week_days", "hidden", 0);
                    }else{
                        d.set_df_property("week_days", "hidden", 1);
                    }
                    html=`<div></div>`
                    d.fields_dict.available_slots.$wrapper.html(html);
                    d.get_primary_btn().hide()
                }
            },
            { fieldtype: 'Section Break', fieldname: 'week_days', hidden: 1, },
            {
                fieldtype: 'Check',
                fieldname: 'monday',
                label: 'Monday'
            },
            {
                fieldtype: 'Check',
                fieldname: 'tuesday',
                label: 'Tuesday'
            },
            { fieldtype: 'Column Break', fieldname: 'day_break2' },
            {
                fieldtype: 'Check',
                fieldname: 'wednesday',
                label: 'Wednesday'
            },
            {
                fieldtype: 'Check',
                fieldname: 'thursday',
                label: 'Thursday'
            },
            { fieldtype: 'Column Break', fieldname: 'day_break4' },
            {
                fieldtype: 'Check',
                fieldname: 'friday',
                label: 'Friday'
            },
            {
                fieldtype: 'Check',
                fieldname: 'saturday',
                label: 'Saturday'
            },
            { fieldtype: 'Column Break', fieldname: 'day_break6' },
            {
                fieldtype: 'Check',
                fieldname: 'sunday',
                label: 'Sunday'
            },
            { fieldtype: 'Section Break', fieldname: 'section_break_1', hidden: 0, },
            {
                label: "Repeat Till",
                fieldname: "repeat_till",
                fieldtype: "Date",
                reqd: 0
            },
            {
                label: "Repeat Interval",
                fieldname: "repeat_interval",
                fieldtype: "Int",
                reqd: 0,
                default: 1
            },
            {
                label: "Max Occurrences",
                fieldname: "max_occurrences",
                fieldtype: "Int",
                reqd: 0
            },
            { fieldtype: 'Section Break', fieldname: 'section_break_10', hidden: 0, },
            {
                label: "Available Slots",
                fieldname: "available_slots",
                fieldtype: "HTML",
                options: ""
            }
        ],
        secondary_action_label: "Check Availability",
        secondary_action:function() {
            var data = d.get_values();
            if (!(data.max_occurrences || data.repeat_till)){
                frappe.throw("<b>Max Occurrences</b> or <b>Repeat Till</b> one of the value should be updated")
            }

            frappe.call({
                method : "healthcare.healthcare.doctype.patient_appointment.recuring_appointment_handler.get_recurring_appointment_dates",
                args: {
                    data : data
                },
                callback:(r)=>{
                    if (!r.message) return;
                    const result = r.message.dates;  // Assuming it's a list
                    let html = `<div style="display: flex; flex-wrap: wrap; gap: 10px;">`;

                    result.forEach(slot => {
                        const color = slot.booking_flage  ? 'red' : 'green';
                        html += `
                            <div style="
                                background-color: ${color}; 
                                color: white;
                                padding: 5px 5px 5px 5px;
                                border-radius: 6px;
                                font-size: 12px;
                                text-align: center;
                            ">
                                <strong>${frappe.datetime.str_to_user(slot.date)}</strong><br/>
                                ${slot.from_time} - ${slot.to_time}
                            </div>
                        `;
                    });

                    html += `</div>`;
                    // Set HTML content into the dialog field
                    d.fields_dict.available_slots.$wrapper.html(html);
                }
            })
            d.get_primary_btn().show()
        },
        primary_action_label: "Book Appointments",
        primary_action: function () {
            const data = d.get_values();
            if (!data) return;

            if (!(data.max_occurrences || data.repeat_till)) {
                frappe.throw("<b>Max Occurrences</b> or <b>Repeat Till</b> one of the value should be updated");
            }

            // Slight delay to ensure dialog rendering finishes
            setTimeout(() => {
                frappe.dom.freeze("Creating Appointments...");
                
                frappe.call({
                    method: "healthcare.healthcare.doctype.patient_appointment.recuring_appointment_handler.create_recurring_appointments",
                    args: { data },
                    callback: function (r) {
                        frappe.dom.unfreeze();
                        if (r.message) {
                            frappe.msgprint("Appointments are being created in background", () => {
                                d.hide();
                            });
                        }
                    }
                });
            }, 10);
        }

    });
    d.fields_dict['from_date'].df.onchange =()=>{
        let today = frappe.datetime.get_today();
        if (d.get_value('from_date') < today) {
            d.set_value('from_date', '')
            frappe.msgprint(__('Booking only allow for today and future date'));
        }
        html=`<div></div>`
        d.fields_dict.available_slots.$wrapper.html(html);
        d.get_primary_btn().hide()
    }
    d.fields_dict['from_time'].df.onchange = () => {
        html=`<div></div>`
        d.fields_dict.available_slots.$wrapper.html(html);
        d.get_primary_btn().hide()
    }
    d.fields_dict['to_time'].df.onchange = () => {
        html=`<div></div>`
        d.fields_dict.available_slots.$wrapper.html(html);
        d.get_primary_btn().hide()
    }
    d.fields_dict['practitioner'].df.onchange = async () => {
			if (d.get_value('practitioner') && d.get_value('practitioner') != selected_practitioner) {
				selected_practitioner = d.get_value('practitioner');
				let r = await frappe.call({
					method: "healthcare.healthcare.doctype.patient_appointment.recuring_appointment_handler.get_service_unit_values",
					args: {
						selected_practitioner
					}
				});
				service_unit_values = r.message;
                if (service_unit_values.length == 1){
                    d.set_value("service_unit", service_unit_values[0])    
                    d.set_df_property("service_unit", "read_only", 1)                
                }
			}else{
                    d.set_value("service_unit", '')   
                    d.set_df_property("service_unit", "read_only", 0)                
            }
            if (d.get_value('practitioner')) {
            frappe.db.get_value("Healthcare Practitioner", d.get_value('practitioner'), "department")
                .then(r => {
                    if (r.message && r.message.department) {                
                        d.set_value("medical_department", r.message.department);
                        d.refresh()
                    } else {
                        d.set_value("medical_department", null);
                    }
                });
            } else {
                d.set_value("medical_department", null);
            }
            html=`<div></div>`
            d.fields_dict.available_slots.$wrapper.html(html);
            d.get_primary_btn().hide()
		};
    d.fields_dict['appointment_type'].df.onchange = () =>{
        if (d.get_value("appointment_type") == "Therapy Session"){
            d.set_df_property("therapy_plan", "hidden", 0)
            d.set_df_property("therapy_plan", "reqd", 1)
        }
        else{
            d.set_df_property("therapy_plan", "hidden", 1)
            d.set_df_property("therapy_plan", "reqd", 0)
            d.set_value("therapy_plan", '')
        }
    }
    if (d.get_value("appointment_type") == "Therapy Session"){
            d.set_df_property("therapy_plan", "hidden", 0)
            d.set_df_property("therapy_plan", "reqd", 1)
    }
    else{
        d.set_df_property("therapy_plan", "hidden", 1)
        d.set_df_property("therapy_plan", "reqd", 0)
        d.set_value("therapy_plan", '')
    }
    d.fields_dict.service_unit.get_query = function() {
			return {
				filters: {
					'name': ["in", service_unit_values]
				}
			};
		};
    d.fields_dict.therapy_plan.get_query = function() {
			return {
				filters: {
					'status': ["!=", "Completed"],
                    'patient': d.get_value('patient')
				}
			};
		};
    d.get_primary_btn().hide()
    d.show();
}
