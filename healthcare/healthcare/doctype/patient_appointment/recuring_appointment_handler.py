import frappe
import json
from frappe.utils import getdate, add_days, add_months, add_years, date_diff
from datetime import timedelta
from healthcare.healthcare.doctype.patient_appointment.patient_appointment import (
    check_employee_wise_availability,
    validate_practitioner_schedules,
    check_sales_invoice_exists,
    cancel_sales_invoice

)
from datetime import datetime, timedelta
from happiest_frappe.happiest_frappe.api.api import get_available_slots
from frappe.email.doctype.notification.notification import Notification, get_context


@frappe.whitelist()
def create_recurring_appointments(data):
    data = frappe._dict(json.loads(data))

    repeat_on = data.repeat_on
    repeat_interval = data.repeat_interval or 1
    repeat_till = getdate(data.repeat_till)
    base_date = getdate(data.from_date)
    max_occurrences = data.max_occurrences
    created = []
    schedule_details = get_recurring_appointment_dates(data)

    if not schedule_details.get("dates"):
        frappe.throw("Slots are not available")
    for row in schedule_details.get("dates"):
        if not row.get("booking_flage"):
            doc = frappe.get_doc({
                "doctype" : "Patient Appointment",
                "appointment_date" : row.get("date"),
                "patient" : data.patient,
                "practitioner" : data.practitioner,
                "appointment_time" : row.get("from_time"),
                "end_time" : row.get("to_time"),
                "service_unit" : data.service_unit,
                "recurring_appointments" : 1,
                "appointment_type" : data.appointment_type,
                "therapy_plan" : data.therapy_plan if data.appointment_type == 'Therapy Session' else ''
            })

            if data.appointment_type == 'Therapy Session' and data.therapy_plan:
                therapy = frappe.get_doc("Therapy Plan", data.therapy_plan)
                for d in therapy.therapy_plan_details:
                    doc.append("therapy_types", {
                        "therapy_type" : d.therapy_type,
                        "no_of_sessions" : d.no_of_sessions
                    })
            doc.insert(ignore_permissions=True)

    return True

    
def prepare_payload_for_email(self, doc, context):
    """Prepare and render the WhatsApp message payload."""
    payload_template = self.message
    rendered_payload = frappe.render_template(payload_template, context)
    payload = rendered_payload
    return payload

@frappe.whitelist()
def book_appointments(data):
    frappe.enqueue(
					create_recurring_appointments,
                    data=data,
					queue="long",
					is_async=True,
					enqueue_after_commit=True
				)
    return True

@frappe.whitelist()
def get_recurring_appointment_dates(data):
    try:
        data = frappe._dict(json.loads(data))
    except Exception:
        data = data

    time_obj = datetime.strptime(data.get("from_time"), "%H:%M:%S").time()
    from_time = timedelta(hours=time_obj.hour, minutes=time_obj.minute, seconds=time_obj.second)
    time_obj = datetime.strptime(data.get("to_time"), "%H:%M:%S").time()
    to_time = timedelta(hours=time_obj.hour, minutes=time_obj.minute, seconds=time_obj.second)

    repeat_on = data.repeat_on  # Daily, Weekly, Monthly, Yearly
    repeat_interval = data.repeat_interval or 1
    repeat_till = getdate(data.repeat_till) if data.repeat_till else None
    base_date = getdate(data.from_date) 
    max_occurrences = data.max_occurrences
    practitioner_doc = frappe.get_doc("Healthcare Practitioner", data.practitioner)
    
    practitioner_schedule_list = []
    for row in practitioner_doc.practitioner_schedules:
        if row.service_unit == data.service_unit:
            practitioner_schedule = frappe.get_doc("Practitioner Schedule", row.schedule)
            for log in practitioner_schedule.time_slots:
                practitioner_schedule_list.append(log)

    week_checks = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday" ]
    week_day = {
        "monday": "Monday", "tuesday": "Tuesday", "wednesday": "Wednesday", "thursday": "Thursday",
        "friday": "Friday", "saturday": "Saturday", "sunday": "Sunday"
    }

    # Collect weekly repeat days
    repeat_week_days = []
    if repeat_on == "Weekly":
        for row in week_checks:
            if data.get(row):
                repeat_week_days.append(week_day.get(row))

    scheduled_dates = []
    next_date = base_date

    # For Weekly repeat, track occurrences per weekday; otherwise use single counter
    if repeat_on == "Weekly":
        occurrences = {day: 0 for day in repeat_week_days}
    else:
        occurrences = 0
    
    total_day_of_booking = len(repeat_week_days)
    available_any = False

    max_iterations = 365  
    iteration_count = 0
    
    while True:
        iteration_count += 1
        if iteration_count > max_iterations:
            break  
            
        if next_date == getdate() and from_time:
            datetime_str = f"{next_date} {from_time}"
            dt = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S")
            if dt < frappe.utils.get_datetime():
                next_date += timedelta(days=1)
                continue
        # Check if the practitioner's schedule allows this time on this day
        available = False
        for row in practitioner_schedule_list:
            if row.day == next_date.strftime("%A"):
                # Check if the requested time slot fits inside the available time slot
                if row.from_time <= from_time < row.to_time:
                    available = True
                    available_any = True
                if row.from_time < to_time <= row.to_time:
                    available = True
                    available_any = True
                if (row.from_time >= from_time < row.to_time and 
                    row.from_time < to_time > row.to_time):
                    available = True
                    available_any = True
                if (row.from_time >= from_time < row.to_time and 
                    row.from_time < to_time <= row.to_time):
                    available = True
                    available_any = True

        if not available:
            next_date += timedelta(days=1)
            if repeat_till and getdate(next_date) >= getdate(repeat_till):
                print(repeat_till, "repeat_till")
                break
            
            weekday_name = next_date.strftime("%A")
            if repeat_on == "Weekly" and max_occurrences and occurrences.get(weekday_name, 0) >= max_occurrences:
                # If all weekdays reached max_occurrences, break
                if all(occ >= max_occurrences for occ in occurrences.values()):
                    break
                next_date += timedelta(days=1)
                continue

            if repeat_on != "Weekly" and max_occurrences and occurrences >= max_occurrences:
                break
            continue

        # Check if the date is a holiday
        holiday_list = frappe.db.sql(f"""
                    Select hdl.name
                    From `tabHoliday List` as hdl
                    Left Join `tabHoliday` as hl ON hl.parent = hdl.name
                    Where 
                        hdl.from_date <= '{str(next_date)}' 
                        and hdl.to_date >= '{str(next_date)}' 
                        and hl.holiday_date = '{str(next_date)}'
        """, as_dict=1)

        if holiday_list:
            next_date += timedelta(days=1)
            continue

        if repeat_on == "Weekly":
            weekday_name = next_date.strftime("%A")
            if weekday_name not in repeat_week_days:
                next_date += timedelta(days=1)
                continue

            # Check if max occurrences for this weekday reached
            if max_occurrences and occurrences.get(weekday_name, 0) >= max_occurrences:
                # If all weekdays reached max_occurrences, break
                if all(occ >= max_occurrences for occ in occurrences.values()):
                    break
                next_date += timedelta(days=1)
                continue

            # Add date if within repeat_till or if no repeat_till
            if repeat_till and next_date <= repeat_till:
                scheduled_dates.append(str(next_date))
                if total_day_of_booking == len(repeat_week_days):
                    first_week_date = next_date
                total_day_of_booking -= 1
                occurrences[weekday_name] += 1
            elif not repeat_till and max_occurrences:
                scheduled_dates.append(str(next_date))
                if total_day_of_booking == len(repeat_week_days):
                    first_week_date = next_date
                total_day_of_booking -= 1
                occurrences[weekday_name] += 1

            if repeat_till and next_date >= repeat_till:
                break

            # Break if all weekdays have reached max_occurrences
            if max_occurrences and all(occ >= max_occurrences for occ in occurrences.values()):
                break
            if total_day_of_booking == 0 and repeat_interval != 1:
                next_date = first_week_date + timedelta(days=7 * repeat_interval)
                total_day_of_booking = len(repeat_week_days)
            else:
                next_date += timedelta(days=1)

        else:
            # Non-weekly repeats use a single counter
            if repeat_till and next_date <= repeat_till:
                scheduled_dates.append(str(next_date))
                occurrences += 1
            elif not repeat_till and max_occurrences:
                scheduled_dates.append(str(next_date))
                occurrences += 1

            if repeat_till and getdate(next_date) >= getdate(repeat_till):
                break

            if max_occurrences and occurrences >= max_occurrences:
                break

            # Calculate next date
            if repeat_on == "Daily":
                next_date += timedelta(days=repeat_interval)
            elif repeat_on == "Monthly":
                next_date = add_months(next_date, repeat_interval)
            elif repeat_on == "Yearly":
                next_date = add_years(next_date, repeat_interval)

    scheduled_details = [
        {"date" : row, "from_time" : data.from_time[:-3], "to_time" : data.to_time[:-3]} for row in scheduled_dates
        ]

    service_unit = data.service_unit
    scheduled_details = get_availability(scheduled_details, data.practitioner, service_unit=service_unit)

    for row in scheduled_details:
        row.update({'days': getdate(row.get('date')).strftime("%A") })
    if not scheduled_details:
        available_any = False
    return {
        "total": len(scheduled_details),
        "dates": scheduled_details,
        "available" : available_any
    }

def get_availability(scheduled_details, practitioner, service_unit=None):
    """
    Check each scheduled slot against existing appointments.

    Overlap logic:
    - Fetch overlap_appointments and service_unit_capacity from the
      Healthcare Service Unit.
    - If overlap is allowed and the count of overlapping appointments is
      less than the capacity, the slot is still available (booking_flage=False).
    - Otherwise the slot is marked as booked (booking_flage=True).
    """
    for schedule in scheduled_details:
        date = getdate(schedule.get("date"))
        practitioner_doc = frappe.get_doc("Healthcare Practitioner", practitioner)

        check_employee_wise_availability(date, practitioner_doc)

        slot_details = []
        if practitioner_doc.practitioner_schedules:
            slot_details = get_available_slots(practitioner_doc, date, service_unit=None)

        # Collect overlap settings for the requested service unit
        allow_overlap = 0
        service_unit_capacity = 0
        all_appointments = []

        for slot in slot_details:
            print(slot,"slot details")
            all_appointments.extend(slot.get("appointments") or [])
            if service_unit and slot.get("service_unit") == service_unit:
                allow_overlap = slot.get("allow_overlap", 0)
                service_unit_capacity = slot.get("service_unit_capacity", 0)

        # Parse requested window
        time_obj = datetime.strptime(schedule.get("from_time"), "%H:%M").time()
        from_time = timedelta(hours=time_obj.hour, minutes=time_obj.minute, seconds=time_obj.second)
        time_obj = datetime.strptime(schedule.get("to_time"), "%H:%M").time()
        to_time = timedelta(hours=time_obj.hour, minutes=time_obj.minute, seconds=time_obj.second)

        # Only count appointments in the same service unit (when specified)
        relevant = [
            a for a in all_appointments
            if not service_unit or a.get("service_unit") == service_unit
        ]

        # Standard interval overlap: A overlaps B when A.start < B.end AND B.start < A.end
        overlap_count = sum(
            1 for a in relevant
            if a.get("appointment_time") is not None
            and a.get("end_time") is not None
            and from_time < a["end_time"]
            and a["appointment_time"] < to_time
        )

        if overlap_count == 0:
            schedule.update({"booking_flage": False})
        elif allow_overlap and service_unit_capacity and overlap_count < int(service_unit_capacity):
            # Capacity not yet exhausted — slot is still bookable
            schedule.update({"booking_flage": False})
        else:
            schedule.update({"booking_flage": True})

    return scheduled_details

@frappe.whitelist()
def get_service_unit_values(selected_practitioner):
    query=frappe.db.sql(
        "Select service_unit from `tabPractitioner Service Unit Schedule` where parent='{0}'".format(selected_practitioner),as_dict=1
    )

    return list(set([item.service_unit for item in query if item.service_unit]))
