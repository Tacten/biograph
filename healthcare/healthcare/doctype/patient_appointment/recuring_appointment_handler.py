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
def create_selected_appointments(data, selected_slots):
    """Create appointments only for the explicitly selected slots."""
    if isinstance(data, str):
        data = frappe._dict(json.loads(data))
    if isinstance(selected_slots, str):
        selected_slots = json.loads(selected_slots)

    if not selected_slots:
        frappe.throw("No slots selected.")

    created = 0
    therapy = None
    if data.appointment_type == "Therapy Session" and data.get("therapy_plan"):
        therapy = frappe.get_doc("Therapy Plan", data.therapy_plan)

    for slot in selected_slots:
        doc = frappe.get_doc({
            "doctype": "Patient Appointment",
            "appointment_date": slot.get("date"),
            "patient": data.patient,
            "practitioner": data.practitioner,
            "appointment_time": slot.get("from_time"),
            "end_time": slot.get("to_time"),
            "service_unit": data.service_unit,
            "recurring_appointments": 1,
            "appointment_type": data.appointment_type,
            "therapy_plan": data.therapy_plan if data.appointment_type == "Therapy Session" else "",
            "department": data.medical_department
        })
        if therapy:
            for t in therapy.therapy_plan_details:
                doc.append("therapy_types", {
                    "therapy_type": t.therapy_type,
                    "no_of_sessions": t.no_of_sessions
                })
        doc.insert(ignore_permissions=True)
        created += 1

    return {"created": created}


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
            practitioner_schedule = frappe.get_cached_doc("Practitioner Schedule", row.schedule)
            for log in practitioner_schedule.time_slots:
                practitioner_schedule_list.append(log)

    def _to_seconds(t):
        """Safely convert timedelta, datetime.time, or 'HH:MM:SS' string to total seconds."""
        if isinstance(t, timedelta):
            return int(t.total_seconds())
        if hasattr(t, "hour"):
            return t.hour * 3600 + t.minute * 60 + getattr(t, "second", 0)
        if isinstance(t, str):
            parts = t.split(":")
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + (int(parts[2]) if len(parts) > 2 else 0)
        return 0

    def _to_hhmm(t):
        """Safely convert timedelta, datetime.time, or 'HH:MM:SS' string to 'HH:MM'."""
        if isinstance(t, timedelta):
            s = int(t.total_seconds())
            return f"{s // 3600:02d}:{(s % 3600) // 60:02d}"
        if hasattr(t, "hour"):
            return f"{t.hour:02d}:{t.minute:02d}"
        if isinstance(t, str):
            return t[:5]
        return "00:00"

    from_time_secs = _to_seconds(from_time)
    to_time_secs = _to_seconds(to_time)

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

    # Pre-fetch all holidays for the full date range in ONE query instead of per-date SQL inside the loop
    _end_date = repeat_till if repeat_till else add_days(base_date, max_iterations)
    _holiday_rows = frappe.db.sql("""
        SELECT hl.holiday_date
        FROM `tabHoliday List` AS hdl
        INNER JOIN `tabHoliday` AS hl ON hl.parent = hdl.name
        WHERE hdl.from_date <= %s AND hdl.to_date >= %s
            AND hl.holiday_date BETWEEN %s AND %s
    """, (str(_end_date), str(base_date), str(base_date), str(_end_date)), as_dict=1)
    _holiday_set = {str(h.holiday_date) for h in _holiday_rows if h.holiday_date}

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
        # Check if the practitioner has any schedule slot that starts within the user's time range
        available = False
        for row in practitioner_schedule_list:
            if row.day == next_date.strftime("%A"):
                slot_start = _to_seconds(row.from_time)
                slot_end = _to_seconds(row.to_time)
                # Slot must start at or after user's from_time AND end at or before user's to_time
                if from_time_secs <= slot_start and slot_end <= to_time_secs:
                    available = True
                    available_any = True
                    break

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

        # Check if the date is a holiday (uses pre-fetched set — no per-iteration SQL)
        if str(next_date) in _holiday_set:
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

    scheduled_details = []
    for date_str in scheduled_dates:
        day_name = getdate(date_str).strftime("%A")
        # Collect ALL schedule slots for this day that fall within the user's time range
        matched = [
            {"date": date_str, "from_time": _to_hhmm(slot.from_time), "to_time": _to_hhmm(slot.to_time)}
            for slot in practitioner_schedule_list
            if slot.day == day_name
            and from_time_secs <= _to_seconds(slot.from_time)
            and _to_seconds(slot.to_time) <= to_time_secs
        ]
        if matched:
            scheduled_details.extend(matched)
        else:
            # Fallback: no schedule slot matched, use user-supplied times
            scheduled_details.append({"date": date_str, "from_time": data.from_time[:-3], "to_time": data.to_time[:-3]})

    service_unit = data.service_unit
    scheduled_details = get_availability(scheduled_details, data.practitioner, service_unit=service_unit, patient=data.patient)

    for row in scheduled_details:
        row.update({'days': getdate(row.get('date')).strftime("%A") })
    if not scheduled_details:
        available_any = False
    return {
        "total": len(scheduled_details),
        "dates": scheduled_details,
        "available" : available_any
    }

def get_availability(scheduled_details, practitioner, service_unit=None, patient=None):
    """
    Check each scheduled slot against existing appointments.

    Overlap logic:
    - If the same patient already has a non-cancelled appointment overlapping
      this slot on this date, the slot is blocked (booking_flage=True).
    - Fetch overlap_appointments and service_unit_capacity from the
      Healthcare Service Unit.
    - If overlap is allowed and the count of overlapping appointments is
      less than the capacity, the slot is still available (booking_flage=False).
    - Otherwise the slot is marked as booked (booking_flage=True).
    """

    def _slot_secs(t):
        """Convert timedelta, datetime.time, or 'HH:MM:SS' string to total seconds."""
        if isinstance(t, timedelta):
            return int(t.total_seconds())
        if hasattr(t, "hour"):
            return t.hour * 3600 + t.minute * 60 + getattr(t, "second", 0)
        if isinstance(t, str):
            parts = t.split(":")
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + (int(parts[2]) if len(parts) > 2 else 0)
        return 0

    if not scheduled_details:
        return scheduled_details

    # Fetch practitioner doc once for all slots — avoids redundant DB roundtrips
    practitioner_doc = frappe.get_cached_doc("Healthcare Practitioner", practitioner)

    # Pre-fetch the patient's own existing non-cancelled appointments for all
    # dates in scope in ONE query. This lets us block slots the same patient
    # has already booked (regardless of the service-unit overlap capacity).
    patient_existing = {}
    if patient:
        date_list = list({s.get("date") for s in scheduled_details})
        _patient_appts = frappe.get_all(
            "Patient Appointment",
            filters={
                "patient": patient,
                # "practitioner": practitioner,   # only same practitioner counts as a block
                "appointment_date": ["in", date_list],
                "status": ["not in", ["Cancelled", "Closed"]],
            },
            fields=["appointment_date", "appointment_time", "end_time"],
        )
        for appt in _patient_appts:
            d_str = str(appt.appointment_date)
            if d_str not in patient_existing:
                patient_existing[d_str] = []
            patient_existing[d_str].append(appt)

    # Pre-fetch all practitioner unavailability appointments (appointment_type="Unavailable")
    # for the full date range in ONE query.  Any slot that overlaps one of these blocks
    # is considered unavailable and must not be shown to the user.
    date_list_all = list({s.get("date") for s in scheduled_details})
    _unavail_appts = frappe.get_all(
        "Patient Appointment",
        filters={
            "practitioner": practitioner,
            "appointment_date": ["in", date_list_all],
            "appointment_type": "Unavailable",
            "status": ["not in", ["Cancelled"]],
        },
        fields=["appointment_date", "appointment_time", "end_time", "service_unit"],
    )
    practitioner_unavailable = {}
    for ua in _unavail_appts:
        d_str = str(ua.appointment_date)
        if d_str not in practitioner_unavailable:
            practitioner_unavailable[d_str] = []
        practitioner_unavailable[d_str].append(ua)

    # Cache get_available_slots and check_employee_wise_availability results by date.
    # Multiple slots can share the same date; without a cache each one would hit the DB separately.
    _slots_cache = {}
    _checked_dates = set()

    for schedule in scheduled_details:
        date = getdate(schedule.get("date"))
        date_str = str(date)

        if date_str not in _checked_dates:
            try:
                check_employee_wise_availability(date, practitioner_doc)
                _checked_dates.add(date_str)
            except frappe.ValidationError:
                # Practitioner is on leave or holiday on this date — block all slots for the day
                schedule.update({"booking_flage": True, "is_practitioner_unavailable": True})
                _slots_cache[date_str] = []
                _checked_dates.add(date_str)
                continue

        if date_str not in _slots_cache:
            slot_details = []
            if practitioner_doc.practitioner_schedules:
                slot_details = get_available_slots(practitioner_doc, date, service_unit=None)
            _slots_cache[date_str] = slot_details

        slot_details = _slots_cache[date_str]

        # Collect overlap settings for the requested service unit
        allow_overlap = 0
        service_unit_capacity = 0
        all_appointments = []

        for slot in slot_details:
            all_appointments.extend(slot.get("appointments") or [])
            if service_unit and slot.get("service_unit") == service_unit:
                allow_overlap = slot.get("allow_overlap", 0)
                service_unit_capacity = slot.get("service_unit_capacity", 0)

        # Parse requested window
        time_obj = datetime.strptime(schedule.get("from_time"), "%H:%M").time()
        from_time = timedelta(hours=time_obj.hour, minutes=time_obj.minute, seconds=time_obj.second)
        time_obj = datetime.strptime(schedule.get("to_time"), "%H:%M").time()
        to_time = timedelta(hours=time_obj.hour, minutes=time_obj.minute, seconds=time_obj.second)

        req_start = int(from_time.total_seconds())
        req_end = int(to_time.total_seconds())

        # Guard: practitioner must have a schedule slot on this date that covers
        # the requested time window for the service unit. If not (e.g. they have
        # a leave, the schedule was removed, or no slot matches the time range),
        # mark as booked so the UI does not offer this slot for booking.
        practitioner_covers_slot = any(
            (not service_unit or sd.get("service_unit") == service_unit)
            and any(
                _slot_secs(s.from_time) <= req_start and req_end <= _slot_secs(s.to_time)
                for s in (sd.get("all_slots") or [])
            )
            for sd in slot_details
        )
        if not practitioner_covers_slot:
            schedule.update({"booking_flage": True, "is_practitioner_unavailable": True})
            continue

        # Block the slot if the practitioner has explicitly marked this time as unavailable
        # (Patient Appointment with appointment_type="Unavailable").  A global block
        # (no service_unit on the unavailability record) applies to all service units.
        if practitioner_unavailable.get(date_str):
            is_marked_unavailable = any(
                ua.get("appointment_time") is not None
                and ua.get("end_time") is not None
                and (not ua.get("service_unit") or not service_unit or ua.get("service_unit") == service_unit)
                and from_time < ua["end_time"]
                and ua["appointment_time"] < to_time
                for ua in practitioner_unavailable[date_str]
            )
            if is_marked_unavailable:
                schedule.update({"booking_flage": True, "is_practitioner_unavailable": True})
                continue

        # Block the slot if the same patient already has an overlapping active appointment
        # on this date — regardless of overlap capacity settings.
        if patient and patient_existing.get(date_str):
            patient_overlap = any(
                appt.get("appointment_time") is not None
                and appt.get("end_time") is not None
                and from_time < appt["end_time"]
                and appt["appointment_time"] < to_time
                for appt in patient_existing[date_str]
            )
            if patient_overlap:
                schedule.update({"booking_flage": True})
                continue

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
        "Select service_unit from `tabPractitioner Service Unit Schedule` WHERE parent=%s", (selected_practitioner,), as_dict=1
    )

    return list(set([item.service_unit for item in query if item.service_unit]))
