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
    if data and schedule_details:
        send_notification(data, schedule_details)

    return True

def send_notification(data, schedule_details):
    doc = { "data" : data, "schedule_details" : schedule_details }
    context = get_context(doc)
    context["frappe"] = frappe
    recipients = frappe.db.get_value("Patient", data.patient, "email")
    
    if not recipients:
        frappe.throw("Patient email id not found")
    
    notifications = frappe.db.get_list("Notification", {"is_recurring_appointment" : 1, "enabled": 1}, pluck="name")
    
    for row in notifications:
        notification_doc = frappe.get_doc("Notification", row)
        payload = prepare_payload_for_email(notification_doc, doc, context)
        frappe.sendmail(
            recipients=recipients,
            subject=notification_doc.subject,
            message=payload
        )

    
def prepare_payload_for_email(self, doc, context):
    """Prepare and render the WhatsApp message payload."""
    payload_template = self.message
    rendered_payload = frappe.render_template(payload_template, context)
    payload = rendered_payload
    return 

@frappe.whitelist()
def book_appointments(data):
    frappe.enqpayloadueue(
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
    except:
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
    while True:
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
  
    return {
        "total": len(scheduled_details),
        "dates": scheduled_details,
        "available" : available_any
    }



@frappe.whitelist()
def get_availability(scheduled_details, practitioner, service_unit=None):
    """
    requirement parameters : date, practitioner, appointment
    Get availability data of 'practitioner' on 'date'
    :param date: Date to check in schedule
    :param practitioner: Name of the practitioner
    :return: dict containing a list of available slots, list of appointments and time of appointments
    """
    for schedule in scheduled_details:
        date = getdate(schedule.get("date"))
        weekday = date.strftime("%A")

        practitioner_doc = frappe.get_doc("Healthcare Practitioner", practitioner)

        check_employee_wise_availability(date, practitioner_doc)

        if practitioner_doc.practitioner_schedules:
            service_unit = None
            slot_details = get_available_slots(practitioner_doc, date, service_unit=service_unit)
        
        appointments = []
        for row in slot_details:
            for d in row.get("appointments"):
                appointments.append(d)
        
        if appointments:
            booked = False
            for row in appointments:
                time_obj = datetime.strptime(schedule.get("from_time"), "%H:%M").time()
                from_time = timedelta(hours=time_obj.hour, minutes=time_obj.minute, seconds=time_obj.second)
                time_obj = datetime.strptime(schedule.get("to_time"), "%H:%M").time()
                to_time = timedelta(hours=time_obj.hour, minutes=time_obj.minute, seconds=time_obj.second)
                
                if (from_time <= row.get("appointment_time") < to_time):
                    booked=True
                if (from_time < row.get("end_time") <= to_time):
                    booked=True 
                if (from_time >= row.get("appointment_time") < to_time and 
                    from_time < row.get("end_time") > to_time):
                    booked=True
                if (from_time >= row.get("appointment_time") < to_time and 
                    from_time < row.get("end_time") <= to_time):
                    booked=True
                if booked:
                    schedule.update({"booking_flage" : True})
                    break
            if not booked:
                schedule.update({"booking_flage" : False})
        else:
            schedule.update({"booking_flage" : False})
    
    return scheduled_details

@frappe.whitelist()
def get_service_unit_values(selected_practitioner):
    query=frappe.db.sql(
        "Select service_unit from `tabPractitioner Service Unit Schedule` where parent='{0}'".format(selected_practitioner),as_dict=1
    )

    return list(set([item.service_unit for item in query if item.service_unit]))