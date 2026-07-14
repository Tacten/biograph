frappe.provide("healthcare.appointment");


window.show_recurring_dialog = function(doc=null) {
    healthcare.appointment.show_recurring_dialog(doc);
};

healthcare.appointment.show_recurring_dialog = function(doc) {
    open_repeat_dialog(doc)
}



function open_repeat_dialog(doc) {
    let repeat_on = ""
    let selected_practitioner = '';
    let selected_slots = [];   // tracks user-selected {date, from_time, to_time}
    let d = new frappe.ui.Dialog({
        title: "Repeat Appointment",
        size: "large",
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
                default : "Consultation"
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
            { fieldtype: 'Column Break', fieldname: 'day_break21' },
            {
                label: "Repeat Interval",
                fieldname: "repeat_interval",
                fieldtype: "Int",
                reqd: 0,
                default: 1
            },
            { fieldtype: 'Column Break', fieldname: 'day_break211' },
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
            validate_data(data)
            if (!(data.max_occurrences || data.repeat_till)){
                frappe.throw("<b>Max Occurrences</b> or <b>Repeat Till</b> one of the value should be updated")
            }
            
            frappe.call({
                method : "healthcare.healthcare.doctype.patient_appointment.recuring_appointment_handler.get_recurring_appointment_dates",
                args: {
                    data : data
                },
                callback:(r)=>{

                    if (!r.message){
                        frappe.dom.unfreeze();
                        return;
                    }
                    const result = r.message.dates;  // Assuming it's a list
                    
                    let html = `<div>`;
                    
                    if(!r.message.available){
                        d.get_primary_btn().hide()
                        html += `<div style="padding: 16px; border: 1px solid #f0ad4e; background-color: #fff3cd; border-radius: 8px; font-family: Arial, sans-serif; color: #856404;">
                                    <p style="margin: 0; font-size: 16px;">
                                        <strong>Practitioner ${frappe.utils.escape_html(data.practitioner)}</strong> is unavailable during the selected time slot.
                                        <br><br>
                                        Please check their schedule and choose a different time.
                                    </p>
                                </div>
                                `
                        frappe.dom.unfreeze();
                    }
                    // Reset selection on fresh check-availability
                    selected_slots = [];
                    let any_not_availability = true;

                    // grouped[date] = [ {date, from_time, to_time, booking_flage, days}, ... ]
                    // Slots where the practitioner is marked unavailable (leave/holiday/no schedule)
                    // are filtered out entirely — they should not appear on the UI at all.
                    const grouped = {};
                    result.forEach(slot => {
                        if (slot.is_practitioner_unavailable) return;
                        if (!grouped[slot.date]) grouped[slot.date] = [];
                        grouped[slot.date].push(slot);
                        if (!slot.booking_flage) any_not_availability = false;  // at least one available
                    });

                    // Auto-select the first available slot for each date by default
                    Object.entries(grouped).forEach(([date, slots]) => {
                        const availableSlots = slots.filter(s => !s.booking_flage);
                        if (availableSlots.length > 0) {
                            const first = availableSlots[0];
                            selected_slots.push({ date: first.date, from_time: first.from_time, to_time: first.to_time });
                        }
                    });

                    function slotKey(s) { return s.date + '|' + s.from_time + '|' + s.to_time; }

                    function isDateSelected(date) {
                        return selected_slots.some(s => s.date === date);
                    }

                    function selectedCountForDate(date) {
                        return selected_slots.filter(s => s.date === date).length;
                    }

                    function renderDateCard(date, slots) {
                        // Summarise availability for the date
                        const availableSlots = slots.filter(s => !s.booking_flage);
                        const allBooked = availableSlots.length === 0;
                        const bg = allBooked ? '#dc3545' : (isDateSelected(date) ? '#28a745' : '#007bff');
                        const selected = isDateSelected(date);
                        const borderStyle = selected ? 'border:3px solid #fff;' : 'border:3px solid transparent;';

                        let card = '<div'
                            + ' class="recurring-date-card"'
                            + ' data-date="' + date + '"'
                            + ' style="'
                            + 'background-color:' + bg + ';color:white;'
                            + 'padding:10px;border-radius:8px;'
                            + 'font-family:Arial,sans-serif;'
                            + 'box-shadow:0 2px 4px rgba(0,0,0,0.1);'
                            + 'text-align:center;'
                            + 'width:110px;min-width:110px;'
                            + (allBooked ? 'opacity:0.75;cursor:not-allowed;' : 'cursor:pointer;user-select:none;')
                            + borderStyle
                            + 'transition:border-color 0.15s;">';
                        card += '<strong style="font-size:14px;">' + frappe.datetime.str_to_user(date) + '</strong>';
                        card += '<hr style="border-top:1px solid rgba(255,255,255,0.3);margin:1px 0;">';
                        if (slots.length > 1) {
                            const selCount = selectedCountForDate(date);
                            const selectedSlotsForDate = selected_slots.filter(s => s.date === date);
                            if (selCount === 1) {
                                // Show the single selected slot's time
                                const selSlot = selectedSlotsForDate[0];
                                const fullSlot = availableSlots.find(s => s.from_time === selSlot.from_time && s.to_time === selSlot.to_time) || selSlot;
                                card += '<div style="font-size:12px;margin-bottom:2px;">' + selSlot.from_time + ' - ' + selSlot.to_time + '</div>';
                                card += '<div style="font-size:11px;"><b>' + (fullSlot.days || '') + '</b></div>';
                                card += '';
                            } else if (selCount > 1) {
                                // Show count of selected appointments only
                                card += '<div style="font-size:11px;font-weight:bold;margin:5px 0;">' + selCount +" Slots Selected</div>";
                                // card += '<div style="font-size:11px;">Appointments</div>';
                            } else {
                                // Nothing selected — show first available slot + total slot count
                                const displaySlot = availableSlots[0] || slots[0];
                                card += '<div style="font-size:12px;margin-bottom:2px;">' + displaySlot.from_time + ' - ' + displaySlot.to_time + '</div>';
                                card += '<div style="font-size:11px;"><b>' + displaySlot.days + '</b></div>';
                                card += '<div style="font-size:10px;margin-top:3px;opacity:0.9;">' + slots.length + ' slots</div>';
                            }
                        } else {
                            // Single slot for this date — always show its time
                            const displaySlot = availableSlots[0] || slots[0];
                            card += '<div style="font-size:12px;margin-bottom:2px;">' + displaySlot.from_time + ' - ' + displaySlot.to_time + '</div>';
                            card += '<div style="font-size:11px;"><b>' + displaySlot.days + '</b></div>';
                        }
                        card += '</div>';
                        return card;
                    }

                    // Build the flat flex-wrap grid of date cards (one per date)
                    html += '<div style="display:flex;flex-wrap:wrap;gap:10px;">';
                    Object.entries(grouped).forEach(([date, slots]) => {
                        html += renderDateCard(date, slots);
                    });
                    html += '</div>';

                    d.fields_dict.available_slots.$wrapper.html(html);

                    function updateBookBtn() {
                        const n = selected_slots.length;
                        if (n > 0) {
                            d.get_primary_btn().show().text(__('Book') + ' ' + n + ' ' + __(n === 1 ? 'Appointment' : 'Appointments'));
                        } else {
                            d.get_primary_btn().hide();
                        }
                    }

                    function refreshDateCard(date) {
                        const $old = d.fields_dict.available_slots.$wrapper.find('.recurring-date-card[data-date="' + date + '"]');
                        $old.replaceWith(renderDateCard(date, grouped[date]));
                        // No direct re-bind needed — delegation on the wrapper covers new elements
                    }

                    function dateCardClickHandler() {
                        const date = $(this).data('date');
                        const slots = grouped[date];
                        if (!slots) return;

                        const availableSlots = slots.filter(s => !s.booking_flage);
                        if (availableSlots.length === 0) return;  // all booked, ignore click

                        // If only one slot — toggle select/deselect directly without popup
                        if (availableSlots.length === 1) {
                            const s = availableSlots[0];
                            const key = slotKey(s);
                            const idx = selected_slots.findIndex(x => slotKey(x) === key);
                            if (idx === -1) {
                                selected_slots.push({ date: s.date, from_time: s.from_time, to_time: s.to_time });
                            } else {
                                selected_slots.splice(idx, 1);
                            }
                            refreshDateCard(date);
                            updateBookBtn();
                            return;
                        }

                        // Multiple slots — open a popup to let user pick (multi-select)
                        // Build a working copy of selections for this date so user can toggle freely
                        let pendingKeys = new Set(
                            selected_slots.filter(x => x.date === date).map(x => slotKey(x))
                        );

                        // Pre-select the first available slot if nothing is currently selected for this date
                        if (pendingKeys.size === 0 && availableSlots.length > 0) {
                            pendingKeys.add(slotKey(availableSlots[0]));
                        }

                        function buildPopupHtml() {
                            let popup_html = '<div style="display:flex;flex-wrap:wrap;gap:10px;padding:8px;">';
                            availableSlots.forEach(s => {
                                const key = slotKey(s);
                                const isSelected = pendingKeys.has(key);
                                const slotBg = isSelected ? '#28a745' : '#007bff';
                                const borderStyle = isSelected ? 'border:3px solid #fff;' : 'border:3px solid transparent;';
                                popup_html += '<div'
                                    + ' class="slot-popup-item"'
                                    + ' data-key="' + key + '"'
                                    + ' data-date="' + s.date + '"'
                                    + ' data-from="' + s.from_time + '"'
                                    + ' data-to="' + s.to_time + '"'
                                    + ' style="'
                                    + 'background-color:' + slotBg + ';color:white;'
                                    + 'padding:10px;border-radius:8px;'
                                    + 'font-family:Arial,sans-serif;'
                                    + 'box-shadow:0 2px 4px rgba(0,0,0,0.1);'
                                    + 'text-align:center;'
                                    + 'width:110px;min-width:110px;'
                                    + 'cursor:pointer;user-select:none;'
                                    + borderStyle
                                    + 'transition:border-color 0.15s;">';
                                popup_html += '<strong style="font-size:14px;">' + frappe.datetime.str_to_user(s.date) + '</strong>';
                                popup_html += '<hr style="border-top:1px solid rgba(255,255,255,0.3);margin:1px 0;">';
                                popup_html += '<div style="font-size:12px;margin-bottom:2px;">' + s.from_time + ' - ' + s.to_time + '</div>';
                                popup_html += '<div style="font-size:11px;"><b>' + s.days + '</b></div>';
                                popup_html += '</div>';
                            });
                            popup_html += '</div>';
                            return popup_html;
                        }

                        const slot_popup = new frappe.ui.Dialog({
                            title: __('Select Slots') + ' — ' + frappe.datetime.str_to_user(date),
                            fields: [{ fieldtype: 'HTML', fieldname: 'slot_list', options: buildPopupHtml() }],
                            primary_action_label: __('Confirm'),
                            primary_action: function() {
                                // Sync pendingKeys back to selected_slots for this date
                                // Remove all existing selections for this date
                                selected_slots = selected_slots.filter(x => x.date !== date);
                                // Add all pending selections
                                availableSlots.forEach(s => {
                                    if (pendingKeys.has(slotKey(s))) {
                                        selected_slots.push({ date: s.date, from_time: s.from_time, to_time: s.to_time });
                                    }
                                });
                                refreshDateCard(date);
                                updateBookBtn();
                                slot_popup.hide();
                            }
                        });

                        // Toggle selection on popup card click (re-render in place)
                        slot_popup.$wrapper.on('click', '.slot-popup-item', function() {
                            const key = $(this).data('key');
                            if (pendingKeys.has(key)) {
                                pendingKeys.delete(key);
                            } else {
                                pendingKeys.add(key);
                            }
                            // Re-render the HTML field content
                            slot_popup.fields_dict.slot_list.$wrapper.html(buildPopupHtml());
                        });

                        slot_popup.show();
                    }

                    // Bind click handler — remove any previous binding first to prevent
                    // handler accumulation when Check Availability is clicked multiple times
                    d.fields_dict.available_slots.$wrapper
                        .off('click', '.recurring-date-card')
                        .on('click', '.recurring-date-card', dateCardClickHandler);

                    updateBookBtn();
                    if (!any_not_availability) {
                        d.get_primary_btn().hide();
                    }
                },
                freeze: true,
                freeze_message: __('Loading Slots...'),
            })
            d.get_primary_btn().show()
        },
        primary_action_label: "Book Appointments",
        primary_action: function () {
            if (!selected_slots || selected_slots.length === 0) {
                frappe.throw("Please select at least one slot before booking.");
                return;
            }
            const data = d.get_values();
            validate_data(data);
            if (!data) return;

            setTimeout(() => {
                frappe.dom.freeze("Creating Appointments...");

                frappe.call({
                    method: "healthcare.healthcare.doctype.patient_appointment.recuring_appointment_handler.create_selected_appointments",
                    args: {
                        data: data,
                        selected_slots: selected_slots
                    },
                    callback: function (r) {
                        frappe.dom.unfreeze();
                        if (r.message) {
                            frappe.msgprint(r.message.created + " appointment(s) created successfully.");
                            selected_slots = [];
                            d.hide();
                        }
                    }
                });
            }, 10);
        }

    });
    d.fields_dict.repeat_till.datepicker?.update({
        minDate : frappe.datetime.str_to_obj(frappe.datetime.get_today())
    })
    d.fields_dict.from_date.datepicker?.update({
        minDate : frappe.datetime.str_to_obj(frappe.datetime.get_today())
    })
    d.fields_dict['repeat_till'].df.onchange =()=>{
        html=`<div></div>`
        d.fields_dict.available_slots.$wrapper.html(html);
        d.get_primary_btn().hide()
    }
    let week_list = [
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday"

    ]
    week_list.forEach(r=>{
        d.fields_dict[r].df.onchange =()=>{
        html=`<div></div>`
        d.fields_dict.available_slots.$wrapper.html(html);
        d.get_primary_btn().hide()
    }
    })
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
        if((d.get_value('from_time') > d.get_value('to_time')) || (d.get_value('from_time') == d.get_value('to_time'))) {
            d.set_value("to_time", null)
            frappe.throw("<b>From Time must be before To Time and it should not be same.</b>")
        }
        html=`<div></div>`
        d.fields_dict.available_slots.$wrapper.html(html);
        d.get_primary_btn().hide()

    }
   
    d.fields_dict['practitioner'].df.onchange = async () => {
			if (d.get_value('practitioner')) {
				selected_practitioner = d.get_value('practitioner');
				let r = await frappe.call({
					method: "healthcare.healthcare.doctype.patient_appointment.recuring_appointment_handler.get_service_unit_values",
					args: {
						selected_practitioner
					},
                    callback:(r)=>{
                        service_unit_values = r.message

                        if (r.message.length == 1){
                            d.set_value("service_unit", r.message[0])    
                            d.set_df_property("service_unit", "read_only", 1)                
                        }
                        else{
                            d.set_value("service_unit", '')   
                            d.set_df_property("service_unit", "read_only", 0)                
                        }
                    }
				});
				
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
    d.fields_dict['patient'].df.onchange = () => {
        selected_slots = [];
        d.fields_dict.available_slots.$wrapper.html('<div></div>');
        d.fields_dict.available_slots.$wrapper.off('click', '.recurring-date-card');
        d.get_primary_btn().hide();
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
    d.fields_dict.repeat_till.datepicker.update("position", "top left")
    d.fields_dict.therapy_plan.get_query = function() {
			return {
				filters: {
					'status': ["!=", "Completed"],
                    'patient': d.get_value('patient')
				}
			};
		};
    d.get_primary_btn().hide()

    if(doc){
        d.set_value("patient", doc.patient)
        d.set_value("practitioner", doc.practitioner)
        d.set_value("medical_department", doc.medical_department)
        d.set_value("therapy_plan", doc.name)
        d.set_value("from_date", doc.start_date)
    }
    d.show();
}

function validate_data(data){
    if(
        data.repeat_on == "Weekly" && (
            !(data.monday || 
            data.tuesday || 
            data.wednesday || 
            data.friday || 
            data.thursday || 
            data.sunday || 
            data.saturday
            )
        )){
        frappe.throw("💡 Please select at least one weekday to proceed.")
    }
    if((data.from_time > data.to_time) || (data.from_time == data.to_time)) {
        frappe.throw("<b>From Time must be before To Time and it should not be same.</b>")
    }

    const dateStr = data.from_date; // Format: YYYY-MM-DD
    const timeStr = data.from_time   // Format: HH:MM:SS

    // Combine date and time into a single string
    const dateTimeStr = `${dateStr}T${timeStr}`;

    // Create a Date object from the combined string
    const inputDateTime = new Date(dateTimeStr);

    // Get the current date and time
    const now = new Date();

    // Check if the input date-time is in the past
    if (inputDateTime < now) {
        frappe.throw(`Oops! The selected date and time <b>${data.from_date} ${data.from_time}</b> is in the past. Please pick a future slot.`)
    }
}