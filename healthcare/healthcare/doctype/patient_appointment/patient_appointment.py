# -*- coding: utf-8 -*-
# Copyright (c) 2015, ESS LLP and contributors
# For license information, please see license.txt


import json
from datetime import datetime, timedelta

import frappe
from frappe import _
from frappe.core.doctype.sms_settings.sms_settings import send_sms
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc
from frappe.utils import add_to_date, flt, format_date, get_link_to_form, get_time, getdate, today

from erpnext.setup.doctype.employee.employee import is_holiday

from healthcare.healthcare.doctype.fee_validity.fee_validity import (
	check_fee_validity,
	get_fee_validity,
	manage_fee_validity,
)
from healthcare.healthcare.doctype.healthcare_settings.healthcare_settings import (
	get_income_account,
	get_receivable_account,
)
from healthcare.healthcare.utils import get_appointment_billing_item_and_rate


class MaximumCapacityError(frappe.ValidationError):
	pass


class OverlapError(frappe.ValidationError):
	pass


class PatientAppointment(Document):
	def validate(self):
		# Skip certain validations for unavailability appointments
		self.is_unavailability = self.appointment_type == "Unavailable"
		
		# Always ensure duration is set first
		self.ensure_duration_is_set()
		
		# Set appointment datetime and end time
		self.set_appointment_datetime()
		
		# Validate overlaps for all appointments
		self.validate_overlaps()
		
		# Skip all patient-related validations for unavailability appointments
		if not self.is_unavailability:
			self.validate_based_on_appointments_for()
			self.validate_customer_created()
		else:
			# For unavailability appointments, make sure the status remains "Unavailable"
			if self.status != "Cancelled" and self.status != "Unavailable":
				self.status = "Unavailable"
		
		# Service unit validation applies to all appointments
		self.validate_service_unit()
		
		# Set status and title
		self.set_status()
		self.set_title()
		self.update_event()
		self.set_postition_in_queue()


	def before_save(self):
		# Always ensure duration is set
		self.ensure_duration_is_set()
		
		# Calculate appointment end time
		self.set_appointment_datetime()

	def on_update(self):
		# Skip fee validity updates for unavailability appointments
		if self.is_unavailability:
			return
			
		if (
			not frappe.db.get_single_value("Healthcare Settings", "show_payment_popup")
			or not self.practitioner
		):
			update_fee_validity(self)

	def after_insert(self):
		# Create calendar events for all appointments, including unavailability
		if self.appointment_type == "Unavailable":
			# Special case for unavailability events
			self.insert_unavailability_calendar_event()
		else:
			# Normal appointments
			self.insert_calendar_event()
			# Send confirmation only for normal appointments
			send_confirmation_msg(self)
		
		self.update_prescription_details()
		self.set_payment_details()
		
	def insert_unavailability_calendar_event(self):
		"""Special method to create calendar events for unavailability"""
		try:
			if not self.practitioner and not self.service_unit:
				return

			# Get start time as datetime
			starts_on = datetime.combine(
				getdate(self.appointment_date), get_time(self.appointment_time)
			)
			
			# For debugging
			print(f"DEBUG - Appointment start time: {self.appointment_time}")
			
			# IMPORTANT FIX: Always use appointment_end_time if available, regardless of duration
			# This prevents the default 60 min duration from the appointment type from overriding
			if self.appointment_end_time:
				# If we already have an end time, use it directly
				end_time = get_time(self.appointment_end_time)
				ends_on = datetime.combine(getdate(self.appointment_date), end_time)
				print(f"DEBUG - Using appointment_end_time: {self.appointment_end_time} for event end time")
			else:
				# Otherwise calculate from duration
				ends_on = starts_on + timedelta(minutes=flt(self.duration))
				print(f"DEBUG - Calculated end time from duration {self.duration}: {ends_on.time()}")

			# Ensure duration is correct based on start and end times
			duration_minutes = (ends_on - starts_on).total_seconds() / 60
			
			# Force the duration to match the time difference regardless of the appointment type's default
			if abs(duration_minutes - flt(self.duration)) > 1:  # Allow 1 minute tolerance for rounding
				print(f"DEBUG - Duration mismatch! Stored: {self.duration}, Calculated: {duration_minutes}")
				# Update the duration to match the actual time difference
				self.db_set("duration", duration_minutes)
			
			# Debug output
			print(f"DEBUG - Creating event from {starts_on} to {ends_on}. Duration: {duration_minutes} minutes")
			
			# Use the default calendar
			google_calendar = None
			if self.practitioner:
				google_calendar = frappe.db.get_value(
					"Healthcare Practitioner", self.practitioner, "google_calendar"
				)
			if not google_calendar:
				google_calendar = frappe.db.get_single_value("Healthcare Settings", "default_google_calendar")

			# Set color to red for unavailability
			color = "#ff5858"

			# Create event title with time range for better visibility
			start_time_str = starts_on.strftime("%H:%M")
			end_time_str = ends_on.strftime("%H:%M")
			time_range = f"{start_time_str} - {end_time_str}"
			
			if self.practitioner:
				subject = f"UNAVAILABLE: {self.practitioner_name} ({time_range})"
			elif self.service_unit:
				subject = f"UNAVAILABLE: {self.service_unit} ({time_range})"
			else:
				subject = f"UNAVAILABLE: {time_range}"

			# Create a descriptive message
			description = f"Time marked as unavailable: {time_range}"
			if self.notes:
				description += f"\nReason: {self.notes}"

			# IMPORTANT: Store the calculated end time before creating the event
			# This ensures we have it even if event creation somehow overrides it
			calculated_end_time = ends_on
			
			event = frappe.get_doc(
				{
					"doctype": "Event",
					"subject": subject,
					"event_type": "Private",
					"color": color,
					"send_reminder": 0,
					"starts_on": starts_on,
					"ends_on": ends_on,
					"status": "Open",
					"all_day": 0,
					"sync_with_google_calendar": 0,  # Don't sync unavailability
					"add_video_conferencing": 0,
					"description": description,
					"pulled_from_google_calendar": 0,
				}
			)
			
			# Add participants
			participants = []
			if self.practitioner:
				participants.append(
					{"reference_doctype": "Healthcare Practitioner", "reference_docname": self.practitioner}
				)

			if participants:
				event.update({"event_participants": participants})

			# Force bypass any validation issues
			event.flags.ignore_validate = True
			event.flags.ignore_mandatory = True
			event.insert(ignore_permissions=True)
			
			# CRITICAL FIX: After event is created, force-set the correct end time in the database
			# This bypasses any automatic duration calculations from appointment type
			frappe.db.set_value("Event", event.name, "ends_on", calculated_end_time)
			
			# Ensure the event document was created properly by reloading it
			event.reload()
			print(f"DEBUG - Event created with starts_on: {event.starts_on} and ends_on: {event.ends_on}")
			
			# Double-check the event duration to make sure it's correct
			event_duration = (event.ends_on - event.starts_on).total_seconds() / 60
			print(f"DEBUG - Event duration: {event_duration} minutes")
			
			# If the event duration still doesn't match our expected duration, fix it again
			if abs(event_duration - duration_minutes) > 1:  # Allow 1 minute tolerance for rounding
				print(f"DEBUG - Event duration mismatch! Expected: {duration_minutes}, Got: {event_duration}")
				# Try one more direct update to the event end time in the database
				frappe.db.set_value("Event", event.name, "ends_on", calculated_end_time)
				print(f"DEBUG - Fixed event end time again to {calculated_end_time}")
				
				# Verify the fix worked
				event.reload()
				final_duration = (event.ends_on - event.starts_on).total_seconds() / 60
				print(f"DEBUG - Final event duration after fix: {final_duration} minutes")
			
			# Link the event to the appointment and ensure we store the end time
			update_values = {"event": event.name}
			
			if not self.appointment_end_time:
				end_time_str = ends_on.time().strftime("%H:%M:%S")
				update_values.update({
					"appointment_end_time": end_time_str,
					"appointment_end_datetime": ends_on.strftime("%Y-%m-%d %H:%M:%S")
				})
				print(f"DEBUG - Updated appointment with end_time: {end_time_str}")
			
			self.db_set(update_values)
			self.notify_update()
			
		except Exception as e:
			error_msg = f"Error creating calendar event: {str(e)}\n{frappe.get_traceback()}"
			print(f"ERROR - {error_msg}")
			frappe.log_error(error_msg, "Unavailability Calendar Event Error")

	def insert_calendar_event(self):
		if not self.practitioner:
			return

		starts_on = datetime.combine(
			getdate(self.appointment_date), get_time(self.appointment_time)
		)
		
		# Use end_time if available, otherwise calculate based on duration
		if self.end_time:
			ends_on = datetime.combine(getdate(self.appointment_date), get_time(self.end_time))
		else:
			ends_on = starts_on + timedelta(minutes=flt(self.duration))
			
		google_calendar = frappe.db.get_value(
			"Healthcare Practitioner", self.practitioner, "google_calendar"
		)
		if not google_calendar:
			google_calendar = frappe.db.get_single_value("Healthcare Settings", "default_google_calendar")

		if self.appointment_type:
			color = frappe.db.get_value("Appointment Type", self.appointment_type, "color")
		else:
			color = ""

		event = frappe.get_doc(
			{
				"doctype": "Event",
				"subject": f"{self.title} - {self.company}",
				"event_type": "Private",
				"color": color,
				"send_reminder": 1,
				"starts_on": starts_on,
				"ends_on": ends_on,
				"status": "Open",
				"all_day": 0,
				"sync_with_google_calendar": 1 if self.add_video_conferencing and google_calendar else 0,
				"add_video_conferencing": 1 if self.add_video_conferencing and google_calendar else 0,
				"google_calendar": google_calendar,
				"description": f"{self.title} - {self.company}",
				"pulled_from_google_calendar": 0,
			}
		)
		participants = []

		participants.append(
			{"reference_doctype": "Healthcare Practitioner", "reference_docname": self.practitioner}
		)
		
		if self.patient:
			participants.append({"reference_doctype": "Patient", "reference_docname": self.patient})

		event.update({"event_participants": participants})

		event.insert(ignore_permissions=True)
		
		# Link the event to the appointment
		self.db_set("event", event.name)

		event.reload()
		if self.add_video_conferencing and not event.google_meet_link:
			frappe.msgprint(
				_("Could not add conferencing to this Appointment, please contact System Manager"),
				indicator="error",
				alert=True,
			)
		
		self.db_set("google_meet_link", event.google_meet_link)
		self.notify_update()

	def set_title(self):
		if self.is_unavailability:
			# For unavailability appointments, use patient_name as title
			self.title = self.patient_name or "UNAVAILABLE"
		elif self.practitioner:
			self.title = _("{0} with {1}").format(
				self.patient_name or self.patient, self.practitioner_name or self.practitioner
			)
		else:
			self.title = _("{0} at {1}").format(
				self.patient_name or self.patient, self.get(frappe.scrub(self.appointment_for))
			)

	def set_status(self):
		today = getdate()
		appointment_date = getdate(self.appointment_date)

		# If this is an unavailability appointment, always keep it as "Unavailable"
		if self.appointment_type == "Unavailable":
			if self.status != "Cancelled" and self.status != "Unavailable":
				self.status = "Unavailable"
			return
		
		# For new appointments, set default status based on date
		if self.is_new():
			if appointment_date == today:
				self.status = "Confirmed"
			elif appointment_date > today:
				self.status = "Scheduled"
			else:
				self.status = "No Show"
			return
			
		# If appointment is already marked as "Needs Rescheduling", we should check if it has been rescheduled
		if self.status == "Needs Rescheduling" and self.status != "Cancelled":
			# If this has been modified and saved, it means the appointment was rescheduled
			if self.modified != self.creation:
				if appointment_date > today:
					self.status = "Scheduled"
				elif appointment_date == today:
					self.status = "Confirmed"
				return
			return

		# If appointment is created for today set status as Open else Scheduled
		if appointment_date == today:
			if self.status not in ["Checked In", "Checked Out", "Open", "Confirmed", "Cancelled"]:
				self.status = "Open"

		elif appointment_date > today and self.status not in ["Scheduled", "Confirmed", "Cancelled"]:
			self.status = "Scheduled"

		elif appointment_date < today and self.status not in ["No Show", "Cancelled"]:
			self.status = "No Show"

	def validate_overlaps(self):
		if self.appointment_based_on_check_in:
			if frappe.db.exists(
				{
					"doctype": "Patient Appointment",
					"patient": self.patient,
					"appointment_date": self.appointment_date,
					"appointment_time": self.appointment_time,
					"appointment_based_on_check_in": True,
					"name": ["!=", self.name],
				}
			):
				frappe.throw(_("Patient already has an appointment booked for the same day!"), OverlapError)
			return

		if not self.practitioner:
			return

		# Calculate end time based on duration or directly from end_time field
		if self.end_time:
			# Use the end_time directly if it's set
			end_time = datetime.combine(
				getdate(self.appointment_date), get_time(self.end_time)
			)
		else:
			# Otherwise calculate from duration
			end_time = datetime.combine(
				getdate(self.appointment_date), get_time(self.appointment_time)
			) + timedelta(minutes=flt(self.duration))

		# Check for overlaps with unavailable time slots (block appointments marked as Unavailable)
		unavailable_appointments = frappe.get_all(
			"Patient Appointment",
			filters={
				"appointment_date": self.appointment_date,
				"name": ["!=", self.name],
				"status": "Unavailable",
				"appointment_type": "Unavailable",
				"practitioner": self.practitioner,
			},
			fields=["name", "appointment_time", "duration", "end_time"]
		)
		
		for existing in unavailable_appointments:
			if not self.status == "Unavailable":  # Only regular appointments need to avoid unavailable slots
				# Get existing appointment time boundaries
				existing_start_time = get_time(existing.appointment_time)
				
				# Calculate or get end time
				if existing.end_time:
					existing_end_time = get_time(existing.end_time)
				else:
					existing_start_dt = datetime.combine(getdate(self.appointment_date), existing_start_time)
					existing_end_dt = existing_start_dt + timedelta(minutes=flt(existing.duration or 0))
					existing_end_time = existing_end_dt.time()
				
				# Get current appointment time boundaries
				current_start_time = get_time(self.appointment_time)
				current_end_time = end_time.time()
				
				# Check for overlap conditions
				overlap = False
				
				# Condition 1: Current appointment starts during existing appointment
				if (existing_start_time <= current_start_time < existing_end_time):
					overlap = True
				
				# Condition 2: Current appointment ends during existing appointment
				elif (existing_start_time < current_end_time <= existing_end_time):
					overlap = True
				
				# Condition 3: Current appointment contains existing appointment
				elif (current_start_time <= existing_start_time and current_end_time >= existing_end_time):
					overlap = True
				
				# Condition 4: Start times are exactly the same
				elif (current_start_time == existing_start_time):
					overlap = True
				
				if overlap:
					frappe.throw(
						_("The practitioner {0} is already marked as unavailable during this time (see appointment {1})").format(
							frappe.bold(self.practitioner),
							frappe.bold(existing.name)
						),
						OverlapError,
					)

		# Modified SQL query to include end_time check for better overlap detection
		# This will check for overlaps using a range comparison that handles block appointments properly
		overlapping_appointments = frappe.db.sql(
			"""
			SELECT
				name, practitioner, patient, appointment_time, duration, service_unit, status, appointment_type,
				end_time
			FROM
				`tabPatient Appointment`
			WHERE
				appointment_date=%(appointment_date)s AND name!=%(name)s AND status NOT IN ("Closed", "Cancelled") AND
				(
					/* Regular overlap check for patient and practitioner with end_time support */
					(
						(practitioner=%(practitioner)s OR patient=%(patient)s) AND
						(
							/* Case 1: Using explicitly set end_time if available */
							(
								end_time IS NOT NULL AND (
									/* Our start is during their time block */
									(%(appointment_time)s >= appointment_time AND %(appointment_time)s < end_time) OR
									/* Their start is during our time block */
									(appointment_time >= %(appointment_time)s AND appointment_time < %(end_time)s) OR
									/* Exactly matching start times */
									(appointment_time = %(appointment_time)s)
								)
							)
							OR
							/* Case 2: Using duration-based calculation when end_time not available */
							(
								end_time IS NULL AND (
									(appointment_time<%(appointment_time)s AND appointment_time + INTERVAL duration MINUTE>%(appointment_time)s) OR
									(appointment_time>%(appointment_time)s AND appointment_time<%(end_time)s) OR
									(appointment_time=%(appointment_time)s)
								)
							)
						)
					)
					OR
					/* Special check for unavailable slots for this practitioner with end_time support */
					(
						practitioner=%(practitioner)s AND status="Unavailable" AND appointment_type="Unavailable" AND
						(
							/* Case 1: Using explicitly set end_time if available */
							(
								end_time IS NOT NULL AND (
									/* Our start is during their time block */
									(%(appointment_time)s >= appointment_time AND %(appointment_time)s < end_time) OR
									/* Their start is during our time block */
									(appointment_time >= %(appointment_time)s AND appointment_time < %(end_time)s) OR
									/* Exactly matching start times */
									(appointment_time = %(appointment_time)s)
								)
							)
							OR
							/* Case 2: Using duration-based calculation when end_time not available */
							(
								end_time IS NULL AND (
									(appointment_time<%(appointment_time)s AND appointment_time + INTERVAL duration MINUTE>%(appointment_time)s) OR
									(appointment_time>%(appointment_time)s AND appointment_time<%(end_time)s) OR
									(appointment_time=%(appointment_time)s)
								)
							)
						)
					)
				)
			""",
			{
				"appointment_date": self.appointment_date,
				"name": self.name,
				"practitioner": self.practitioner,
				"patient": self.patient,
				"appointment_time": self.appointment_time,
				"end_time": end_time.time().strftime("%H:%M:%S")
			},
			as_dict=True,
		)

		if not overlapping_appointments:
			return  # No overlaps, nothing to validate!

		# Check for unavailable appointments specifically
		unavailable_appointments = [appt for appt in overlapping_appointments 
									if appt.status == "Unavailable" and appt.appointment_type == "Unavailable"
									and appt.practitioner == self.practitioner]
		
		if unavailable_appointments and self.appointment_type != "Unavailable":
			# This is a regular appointment overlapping with an unavailability period
			frappe.throw(
				_("The practitioner {0} is not available during this time due to an unavailability record {1}").format(
					frappe.bold(self.practitioner), 
					frappe.bold(", ".join([appointment["name"] for appointment in unavailable_appointments]))
				),
				OverlapError,
			)

		if self.service_unit:  # validate service unit capacity if overlap enabled
			allow_overlap, service_unit_capacity = frappe.get_value(
				"Healthcare Service Unit", self.service_unit, ["overlap_appointments", "service_unit_capacity"]
			)
			if allow_overlap:
				service_unit_appointments = list(
					filter(
						lambda appointment: appointment["service_unit"] == self.service_unit
						and appointment["patient"] != self.patient,
						overlapping_appointments,
					)
				)
				if len(service_unit_appointments) >= (service_unit_capacity or 1):
					frappe.throw(
						_("Not allowed, {} cannot exceed maximum capacity {}").format(
							frappe.bold(self.service_unit), frappe.bold(service_unit_capacity or 1)
						),
						MaximumCapacityError,
					)
				else:  # service_unit_appointments within capacity, remove from overlapping_appointments
					overlapping_appointments = [
						appointment
						for appointment in overlapping_appointments
						if appointment not in service_unit_appointments
					]

		if overlapping_appointments:
			frappe.throw(
				_("Not allowed, cannot overlap appointment {}").format(
					frappe.bold(", ".join([appointment["name"] for appointment in overlapping_appointments]))
				),
				OverlapError,
			)

	def validate_based_on_appointments_for(self):
		if self.appointment_for:
			# fieldname: practitioner / department / service_unit
			appointment_for_field = frappe.scrub(self.appointment_for)

			# validate if respective field is set
			if not self.get(appointment_for_field):
				frappe.throw(
					_("Please enter {}").format(frappe.bold(self.appointment_for)),
					frappe.MandatoryError,
				)

			if self.appointment_for == "Practitioner":
				# appointments for practitioner are validated separately,
				# based on practitioner schedule
				return

			# validate if patient already has an appointment for the day
			booked_appointment = frappe.db.exists(
				"Patient Appointment",
				{
					"patient": self.patient,
					"status": ["!=", "Cancelled"],
					appointment_for_field: self.get(appointment_for_field),
					"appointment_date": self.appointment_date,
					"name": ["!=", self.name],
				},
			)

			if booked_appointment:
				frappe.throw(
					_("Patient already has an appointment {} booked for {} on {}").format(
						get_link_to_form("Patient Appointment", booked_appointment),
						frappe.bold(self.get(appointment_for_field)),
						frappe.bold(format_date(self.appointment_date)),
					),
					frappe.DuplicateEntryError,
				)

	def validate_service_unit(self):
		if self.inpatient_record and self.service_unit:
			from healthcare.healthcare.doctype.inpatient_medication_entry.inpatient_medication_entry import (
				get_current_healthcare_service_unit,
			)

			is_inpatient_occupancy_unit = frappe.db.get_value(
				"Healthcare Service Unit", self.service_unit, "inpatient_occupancy"
			)
			service_unit = get_current_healthcare_service_unit(self.inpatient_record)
			if is_inpatient_occupancy_unit and service_unit != self.service_unit:
				msg = (
					_("Patient {0} is not admitted in the service unit {1}").format(
						frappe.bold(self.patient), frappe.bold(self.service_unit)
					)
					+ "<br>"
				)
				msg += _(
					"Appointment for service units with Inpatient Occupancy can only be created against the unit where patient has been admitted."
				)
				frappe.throw(msg, title=_("Invalid Healthcare Service Unit"))

	def set_appointment_datetime(self):
		"""Set appointment_datetime field based on appointment date and time."""
		self.appointment_datetime = "%s %s" % (self.appointment_date, self.appointment_time or "00:00:00")
		
		# Set the end time based on duration or use existing end_time
		if self.end_time:
			# If end_time is already set, use it and ensure other fields are consistent
			end_time_str = self.end_time
			if isinstance(self.end_time, datetime):
				end_time_str = self.end_time.strftime("%H:%M:%S")
			
			# Make sure appointment_end_time is also set
			self.appointment_end_time = end_time_str
			
			# Set appointment_end_datetime
			self.appointment_end_datetime = "%s %s" % (self.appointment_date, end_time_str)
			
			# Calculate and update duration based on end_time for consistency
			if self.appointment_time:
				start_time = get_time(self.appointment_time)
				end_time = get_time(end_time_str)
				
				if end_time > start_time:
					start_dt = datetime.combine(getdate(), start_time)
					end_dt = datetime.combine(getdate(), end_time)
					self.duration = (end_dt - start_dt).total_seconds() / 60
		elif self.appointment_time:
			# If no end_time but we have duration and appointment_time, calculate end_time
			start_time = get_time(self.appointment_time)
			end_time = add_to_date(datetime.combine(getdate(), start_time), minutes=self.duration)
			end_time_str = end_time.time().strftime("%H:%M:%S")
			
			# Set both appointment_end_time and end_time
			self.appointment_end_time = end_time_str
			self.end_time = end_time_str
			
			self.appointment_end_datetime = "%s %s" % (self.appointment_date, end_time_str)

	def set_payment_details(self):
		if frappe.db.get_single_value("Healthcare Settings", "show_payment_popup"):
			details = get_appointment_billing_item_and_rate(self)
			self.db_set("billing_item", details.get("service_item"))
			if not self.paid_amount:
				self.db_set("paid_amount", details.get("practitioner_charge"))

	def validate_customer_created(self):
		if frappe.db.get_single_value("Healthcare Settings", "show_payment_popup"):
			if not frappe.db.get_value("Patient", self.patient, "customer"):
				msg = _("Please set a Customer linked to the Patient")
				msg += " <b><a href='/app/Form/Patient/{0}'>{0}</a></b>".format(self.patient)
				frappe.throw(msg, title=_("Customer Not Found"))

	def update_prescription_details(self):
		if self.procedure_prescription:
			frappe.db.set_value(
				"Procedure Prescription", self.procedure_prescription, "appointment_booked", 1
			)
			if self.procedure_template:
				comments = frappe.db.get_value(
					"Procedure Prescription", self.procedure_prescription, "comments"
				)
				if comments:
					frappe.db.set_value("Patient Appointment", self.name, "notes", comments)

	def update_event(self):
		if self.event:
			event_doc = frappe.get_doc("Event", self.event)
			starts_on = datetime.combine(
				getdate(self.appointment_date), get_time(self.appointment_time)
			)
			ends_on = starts_on + timedelta(minutes=flt(self.duration))
			if (
				starts_on != event_doc.starts_on
				or self.add_video_conferencing != event_doc.add_video_conferencing
			):
				event_doc.starts_on = starts_on
				event_doc.ends_on = ends_on
				event_doc.add_video_conferencing = self.add_video_conferencing
				event_doc.save(ignore_permissions=True)
				event_doc.reload()
				self.google_meet_link = event_doc.google_meet_link

	def set_postition_in_queue(self):
		from frappe.query_builder.functions import Max

		if self.status == "Checked In" and not self.position_in_queue:
			appointment = frappe.qb.DocType("Patient Appointment")
			position = (
				frappe.qb.from_(appointment)
				.select(
					Max(appointment.position_in_queue).as_("max_position"),
				)
				.where(
					(appointment.status == "Checked In")
					& (appointment.practitioner == self.practitioner)
					& (appointment.service_unit == self.service_unit)
					& (appointment.appointment_time == self.appointment_time)
				)
			).run(as_dict=True)[0]
			position_in_queue = 1
			if position and position.get("max_position"):
				position_in_queue = position.get("max_position") + 1

			self.position_in_queue = position_in_queue

	def ensure_duration_is_set(self):
		"""Ensure that appointment duration is properly set based on appointment type or slot"""
		
		# First check if we have both appointment_time and end_time set - this takes highest priority
		if self.appointment_time and self.end_time:
			start_time = get_time(self.appointment_time)
			end_time = get_time(self.end_time)
			
			# Ensure end time is after start time
			if end_time > start_time:
				start_dt = datetime.combine(getdate(), start_time)
				end_dt = datetime.combine(getdate(), end_time)
				duration_minutes = (end_dt - start_dt).total_seconds() / 60
				
				# Set the duration based on the time difference
				self.duration = duration_minutes
				print(f"Set duration to {duration_minutes} minutes based on end_time")
				return
			
		# If a duration is already set, respect it
		if self.duration:
			print(f"Using existing duration: {self.duration} minutes")
			return
			
		# Next try to get duration from schedule slot if it's available
		if self.practitioner and self.appointment_date and self.appointment_time:
			# Get the practitioner's schedule
			practitioner_doc = frappe.get_doc("Healthcare Practitioner", self.practitioner)
			if practitioner_doc.practitioner_schedules:
				appointment_date = getdate(self.appointment_date)
				weekday = appointment_date.strftime("%A")
				appointment_time = get_time(self.appointment_time)
				
				# Look through all schedules and find the matching slot
				for schedule_entry in practitioner_doc.practitioner_schedules:
					if schedule_entry.schedule:
						try:
							schedule_doc = frappe.get_doc("Practitioner Schedule", schedule_entry.schedule)
							
							for time_slot in schedule_doc.time_slots:
								if time_slot.day == weekday:
									slot_start = get_time(time_slot.from_time)
									slot_end = get_time(time_slot.to_time)
									
									# Check if appointment time matches this slot
									if slot_start <= appointment_time < slot_end:
										# Calculate slot duration in minutes
										slot_start_dt = datetime.combine(appointment_date, slot_start)
										slot_end_dt = datetime.combine(appointment_date, slot_end)
										slot_duration = (slot_end_dt - slot_start_dt).total_seconds() / 60
										
										# Use this slot's duration
										self.duration = slot_duration
										print(f"Set duration to {slot_duration} minutes based on practitioner schedule slot")
										return
						except Exception as e:
							print(f"Error getting schedule: {str(e)}")
							continue
		
		# If no schedule slot found, get duration from appointment type
		if self.appointment_type:
			default_duration = frappe.db.get_value("Appointment Type", self.appointment_type, "default_duration")
			if default_duration:
				self.duration = default_duration
				print(f"Set duration to {default_duration} minutes based on appointment type {self.appointment_type}")
				return
		
		# If all else fails, set a default duration
		self.duration = 15
		print(f"Set default duration to 15 minutes as no other duration source was found")

	@frappe.whitelist()
	def get_therapy_types(self):
		if not self.therapy_plan:
			return []

		therapy_types = []
		therapy_plan_doc = frappe.get_doc("Therapy Plan", self.therapy_plan)
		if(therapy_plan_doc.status == "Completed"):
			return "Completed"
		for entry in therapy_plan_doc.therapy_plan_details:
			therapy_type_name = entry.therapy_type
			therapy_type_doc = frappe.get_doc("Therapy Type", therapy_type_name)
			
			# Check if this therapy type is already in the appointment's therapy_types table
			already_added = False
			if self.therapy_types:
				for t in self.therapy_types:
					if t.therapy_type == therapy_type_name:
						already_added = True
						break
						
			# If not already added, add it to the return list
			if not already_added:
				therapy_types.append({
					"therapy_type": therapy_type_name,
					"therapy_name": therapy_type_doc.therapy_type,  # The display name
					"duration": therapy_type_doc.default_duration or 45,
					"no_of_sessions" : entry.no_of_sessions
				})
		
		return therapy_types


@frappe.whitelist()
def check_payment_reqd(patient):
	"""
	return True if patient need to be invoiced when show_payment_popup enabled or have no fee validity
	return False show_payment_popup is disabled
	"""
	show_payment_popup = frappe.db.get_single_value("Healthcare Settings", "show_payment_popup")
	free_follow_ups = frappe.db.get_single_value("Healthcare Settings", "enable_free_follow_ups")
	if show_payment_popup:
		if free_follow_ups:
			fee_validity = frappe.db.exists("Fee Validity", {"patient": patient, "status": "Active"})
			if fee_validity:
				return {"fee_validity": fee_validity}
		return True
	return False


@frappe.whitelist()
def invoice_appointment(appointment_name, discount_percentage=0, discount_amount=0):
	appointment_doc = frappe.get_doc("Patient Appointment", appointment_name)
	settings = frappe.get_single("Healthcare Settings")

	if settings.enable_free_follow_ups:
		fee_validity = check_fee_validity(appointment_doc)

		if fee_validity and fee_validity.status != "Active":
			fee_validity = None
		elif not fee_validity:
			if get_fee_validity(appointment_doc.name, appointment_doc.appointment_date):
				return
	else:
		fee_validity = None

	if settings.show_payment_popup and not appointment_doc.invoiced and not fee_validity:
		create_sales_invoice(appointment_doc, discount_percentage, discount_amount)
	update_fee_validity(appointment_doc)


def create_sales_invoice(appointment_doc, discount_percentage=0, discount_amount=0):
	sales_invoice = frappe.new_doc("Sales Invoice")
	sales_invoice.patient = appointment_doc.patient
	sales_invoice.customer = frappe.get_value("Patient", appointment_doc.patient, "customer")
	sales_invoice.appointment = appointment_doc.name
	sales_invoice.due_date = getdate()
	sales_invoice.company = appointment_doc.company
	sales_invoice.debit_to = get_receivable_account(appointment_doc.company)

	item = sales_invoice.append("items", {})
	item = get_appointment_item(appointment_doc, item)

	paid_amount = flt(appointment_doc.paid_amount)
	# Set discount amount and percentage if entered in payment popup
	if flt(discount_percentage):
		sales_invoice.additional_discount_percentage = flt(discount_percentage)
		paid_amount = flt(appointment_doc.paid_amount) - (
			flt(appointment_doc.paid_amount) * (flt(discount_percentage) / 100)
		)
	if flt(discount_amount):
		sales_invoice.discount_amount = flt(discount_amount)
		paid_amount = flt(appointment_doc.paid_amount) - flt(discount_amount)
	# Add payments if payment details are supplied else proceed to create invoice as Unpaid
	if appointment_doc.mode_of_payment and appointment_doc.paid_amount:
		sales_invoice.is_pos = 1
		payment = sales_invoice.append("payments", {})
		payment.mode_of_payment = appointment_doc.mode_of_payment
		payment.amount = paid_amount

	sales_invoice.set_missing_values(for_validate=True)
	sales_invoice.flags.ignore_mandatory = True
	sales_invoice.save(ignore_permissions=True)
	sales_invoice.submit()
	frappe.msgprint(_("Sales Invoice {0} created").format(sales_invoice.name), alert=True)
	frappe.db.set_value(
		"Patient Appointment",
		appointment_doc.name,
		{
			"invoiced": 1,
			"ref_sales_invoice": sales_invoice.name,
			"paid_amount": paid_amount,
		},
	)
	appointment_doc.notify_update()


@frappe.whitelist()
def update_fee_validity(appointment):
	if isinstance(appointment, str):
		appointment = json.loads(appointment)
		appointment = frappe.get_doc(appointment)

	if (
		not frappe.db.get_single_value("Healthcare Settings", "enable_free_follow_ups")
		or not appointment.practitioner
	):
		return

	fee_validity = manage_fee_validity(appointment)
	if fee_validity:
		frappe.msgprint(
			_("{0} has fee validity till {1}").format(
				frappe.bold(appointment.patient_name), format_date(fee_validity.valid_till)
			),
			alert=True,
		)


def check_is_new_patient(patient, name=None):
	filters = {"patient": patient, "status": ("!=", "Cancelled")}
	if name:
		filters["name"] = ("!=", name)

	has_previous_appointment = frappe.db.exists("Patient Appointment", filters)
	return not has_previous_appointment


def get_appointment_item(appointment_doc, item):
	details = get_appointment_billing_item_and_rate(appointment_doc)
	charge = appointment_doc.paid_amount or details.get("practitioner_charge")
	item.item_code = details.get("service_item")
	item.description = _("Consulting Charges: {0}").format(appointment_doc.practitioner)
	item.income_account = get_income_account(appointment_doc.practitioner, appointment_doc.company)
	item.cost_center = frappe.get_cached_value("Company", appointment_doc.company, "cost_center")
	item.rate = charge
	item.amount = charge
	item.qty = 1
	item.reference_dt = "Patient Appointment"
	item.reference_dn = appointment_doc.name
	return item


def cancel_appointment(appointment_id):
	appointment = frappe.get_doc("Patient Appointment", appointment_id)
	if appointment.invoiced:
		sales_invoice = check_sales_invoice_exists(appointment)
		if sales_invoice and cancel_sales_invoice(sales_invoice):
			msg = _("Appointment {0} and Sales Invoice {1} cancelled").format(
				appointment.name, sales_invoice.name
			)
		else:
			msg = _("Appointment Cancelled. Please review and cancel the invoice {0}").format(
				sales_invoice.name
			)
		if frappe.db.get_single_value("Healthcare Settings", "enable_free_follow_ups"):
			fee_validity = frappe.db.get_value("Fee Validity", {"patient_appointment": appointment.name})
			if fee_validity:
				frappe.db.set_value("Fee Validity", fee_validity, "status", "Cancelled")

	else:
		fee_validity = manage_fee_validity(appointment)
		msg = _("Appointment Cancelled.")
		if fee_validity:
			msg += _("Fee Validity {0} updated.").format(fee_validity.name)

	if appointment.event:
		event_doc = frappe.get_doc("Event", appointment.event)
		event_doc.status = "Cancelled"
		event_doc.save(ignore_permissions=True)
	frappe.msgprint(msg)


def cancel_sales_invoice(sales_invoice):
	if frappe.db.get_single_value("Healthcare Settings", "show_payment_popup"):
		if len(sales_invoice.items) == 1:
			if sales_invoice.docstatus.is_submitted():
				sales_invoice.cancel()
			return True
	return False


def check_sales_invoice_exists(appointment):
	sales_invoice = frappe.db.get_value(
		"Sales Invoice Item",
		{"reference_dt": "Patient Appointment", "reference_dn": appointment.name},
		"parent",
	)

	if sales_invoice:
		sales_invoice = frappe.get_doc("Sales Invoice", sales_invoice)
		return sales_invoice
	return False


@frappe.whitelist()
def get_availability_data(date, practitioner, appointment):
	"""
	Get availability data of 'practitioner' on 'date'
	:param date: Date to check in schedule
	:param practitioner: Name of the practitioner
	:return: dict containing a list of available slots, list of appointments and time of appointments
	"""

	date = getdate(date)
	weekday = date.strftime("%A")

	practitioner_doc = frappe.get_doc("Healthcare Practitioner", practitioner)

	check_employee_wise_availability(date, practitioner_doc)

	if practitioner_doc.practitioner_schedules:
		slot_details = get_available_slots(practitioner_doc, date)
	else:
		frappe.throw(
			_(
				"{0} does not have a Healthcare Practitioner Schedule. Add it in Healthcare Practitioner master"
			).format(practitioner),
			title=_("Practitioner Schedule Not Found"),
		)

	if not slot_details:
		# TODO: return available slots in nearby dates
		frappe.throw(
			_("Healthcare Practitioner not available on {0}").format(weekday), title=_("Not Available")
		)

	if isinstance(appointment, str):
		appointment = json.loads(appointment)
		appointment = frappe.get_doc(appointment)

	fee_validity = "Disabled"
	if frappe.db.get_single_value("Healthcare Settings", "enable_free_follow_ups"):
		fee_validity = check_fee_validity(appointment, date, practitioner)
		if not fee_validity and not appointment.get("__islocal"):
			fee_validity = get_fee_validity(appointment.get("name"), date) or None

	if appointment.invoiced:
		fee_validity = "Disabled"

	return {"slot_details": slot_details, "fee_validity": fee_validity}


def check_employee_wise_availability(date, practitioner_doc):
	employee = None
	if practitioner_doc.employee:
		employee = practitioner_doc.employee
	elif practitioner_doc.user_id:
		employee = frappe.db.get_value("Employee", {"user_id": practitioner_doc.user_id}, "name")

	if employee:
		# check holiday
		if is_holiday(employee, date):
			frappe.throw(_("{0} is a holiday".format(date)), title=_("Not Available"))

		# check leave status
		if "hrms" in frappe.get_installed_apps():
			leave_record = frappe.db.sql(
				"""select half_day from `tabLeave Application`
				where employee = %s and %s between from_date and to_date
				and docstatus = 1""",
				(employee, date),
				as_dict=True,
			)
			if leave_record:
				if leave_record[0].half_day:
					frappe.throw(
						_("{0} is on a Half day Leave on {1}").format(practitioner_doc.name, date),
						title=_("Not Available"),
					)
				else:
					frappe.throw(
						_("{0} is on Leave on {1}").format(practitioner_doc.name, date), title=_("Not Available")
					)


def get_available_slots(practitioner_doc, date):
	available_slots = slot_details = []
	weekday = date.strftime("%A")
	practitioner = practitioner_doc.name

	for schedule_entry in practitioner_doc.practitioner_schedules:
		validate_practitioner_schedules(schedule_entry, practitioner)
		practitioner_schedule = frappe.get_doc("Practitioner Schedule", schedule_entry.schedule)

		if practitioner_schedule and not practitioner_schedule.disabled:
			available_slots = []
			for time_slot in practitioner_schedule.time_slots:
				if weekday == time_slot.day:
					available_slots.append(time_slot)

			if available_slots:
				appointments = []
				allow_overlap = 0
				service_unit_capacity = 0
				# fetch all appointments to practitioner by service unit
				filters = {
					"practitioner": practitioner,
					"service_unit": schedule_entry.service_unit,
					"appointment_date": date,
					"status": ["not in", ["Cancelled"]],
				}

				if schedule_entry.service_unit:
					slot_name = f"{schedule_entry.schedule}"
					allow_overlap, service_unit_capacity = frappe.get_value(
						"Healthcare Service Unit",
						schedule_entry.service_unit,
						["overlap_appointments", "service_unit_capacity"],
					)
					if not allow_overlap:
						# fetch all appointments to service unit
						filters.pop("practitioner")
				else:
					slot_name = schedule_entry.schedule
					# fetch all appointments to practitioner without service unit
					filters["practitioner"] = practitioner
					filters.pop("service_unit")

				appointments = frappe.get_all(
					"Patient Appointment",
					filters=filters,
					fields=["name", "appointment_time", "duration", "status", 
					        "appointment_date", "appointment_type", "end_time"],
				)
				
				# Now also fetch any unavailability appointments for this practitioner
				# This is critical - we need to ensure unavailable time slots are not shown as available
				unavailable_appointments = frappe.get_all(
					"Patient Appointment",
					filters={
						"practitioner": practitioner,
						"appointment_date": date,
						"status": "Unavailable",
						"appointment_type": "Unavailable"
					},
					fields=["name", "appointment_time", "duration", "status", 
					        "appointment_date", "appointment_type", "end_time"]
				)
				
				# Also get any block-based appointments that might overlap this practitioner's slots
				block_appointments = frappe.get_all(
					"Patient Appointment",
					filters={
						"practitioner": practitioner,
						"appointment_date": date,
						"status": ["not in", ["Cancelled"]],
						"end_time": ["is", "set"]
					},
					fields=["name", "appointment_time", "duration", "status", 
					        "appointment_date", "appointment_type", "end_time"]
				)
				
				# Combine with regular appointments - include all types of appointments
				# that could affect slot availability
				appointments.extend(unavailable_appointments)
				
				# Add block appointments that aren't already in the list
				existing_names = [app.name for app in appointments]
				for block_app in block_appointments:
					if block_app.name not in existing_names:
						appointments.append(block_app)

				slot_details.append(
					{
						"slot_name": slot_name,
						"service_unit": schedule_entry.service_unit,
						"avail_slot": available_slots,
						"appointments": appointments,
						"allow_overlap": allow_overlap,
						"service_unit_capacity": service_unit_capacity,
						"tele_conf": practitioner_schedule.allow_video_conferencing,
					}
				)
	return slot_details


def validate_practitioner_schedules(schedule_entry, practitioner):
	if schedule_entry.schedule:
		if not schedule_entry.service_unit:
			frappe.throw(
				_(
					"Practitioner {0} does not have a Service Unit set against the Practitioner Schedule {1}."
				).format(
					get_link_to_form("Healthcare Practitioner", practitioner),
					frappe.bold(schedule_entry.schedule),
				),
				title=_("Service Unit Not Found"),
			)

	else:
		frappe.throw(
			_("Practitioner {0} does not have a Practitioner Schedule assigned.").format(
				get_link_to_form("Healthcare Practitioner", practitioner)
			),
			title=_("Practitioner Schedule Not Found"),
		)


@frappe.whitelist()
def update_status(appointment_id, status):
	appointment_doc = frappe.get_doc("Patient Appointment", appointment_id)
	appointment_doc.status = "Cancelled"
	
	# Different handling based on appointment type
	if status == "Cancelled":
		if appointment_doc.appointment_type == "Unavailable":
			# For unavailability appointments, we need to bypass validation
			# Instead of saving the document which tries to modify set_only_once fields,
			# directly update the status in the database
			frappe.db.set_value("Patient Appointment", appointment_id, "status", "Cancelled")

			# Update the calendar event if it exists
			if appointment_doc.event:
				event_doc = frappe.get_doc("Event", appointment_doc.event)
				event_doc.status = "Cancelled"
				event_doc.save(ignore_permissions=True)
			
			frappe.msgprint(_("Unavailability record cancelled successfully"), alert=True)
			return
		else:
			# For regular appointments, use standard save and cancellation
			appointment_doc.save()
			appointment_booked = False
			cancel_appointment(appointment_id)
	else:
		appointment_doc.save()
		appointment_booked = True

	procedure_prescription = frappe.db.get_value(
		"Patient Appointment", appointment_id, "procedure_prescription"
	)
	if procedure_prescription:
		frappe.db.set_value(
			"Procedure Prescription", procedure_prescription, "appointment_booked", appointment_booked
		)


def send_confirmation_msg(doc):
	if frappe.db.get_single_value("Healthcare Settings", "send_appointment_confirmation"):
		message = frappe.db.get_single_value("Healthcare Settings", "appointment_confirmation_msg")
		try:
			send_message(doc, message)
		except Exception:
			frappe.log_error(frappe.get_traceback(), _("Appointment Confirmation Message Not Sent"))
			frappe.msgprint(_("Appointment Confirmation Message Not Sent"), indicator="orange")


@frappe.whitelist()
def make_encounter(source_name, target_doc=None):
	doc = get_mapped_doc(
		"Patient Appointment",
		source_name,
		{
			"Patient Appointment": {
				"doctype": "Patient Encounter",
				"field_map": [
					["appointment", "name"],
					["patient", "patient"],
					["practitioner", "practitioner"],
					["medical_department", "department"],
					["patient_sex", "patient_sex"],
					["invoiced", "invoiced"],
					["company", "company"],
				],
				"field_no_map": ["practitioner"],
			}
		},
		target_doc,
	)
	return doc


def send_appointment_reminder():
	if frappe.db.get_single_value("Healthcare Settings", "send_appointment_reminder"):
		remind_before = datetime.strptime(
			frappe.db.get_single_value("Healthcare Settings", "remind_before"), "%H:%M:%S"
		)
		reminder_dt = datetime.now() + timedelta(
			hours=remind_before.hour, minutes=remind_before.minute, seconds=remind_before.second
		)

		appointment_list = frappe.db.get_all(
			"Patient Appointment",
			{
				"appointment_datetime": ["between", (datetime.now(), reminder_dt)],
				"reminded": 0,
				"status": ["not in", ["Cancelled", "Needs Rescheduling", "Unavailable"]],
			},
		)

		for appointment in appointment_list:
			doc = frappe.get_doc("Patient Appointment", appointment.name)
			message = frappe.db.get_single_value("Healthcare Settings", "appointment_reminder_msg")
			send_message(doc, message)
			frappe.db.set_value("Patient Appointment", doc.name, "reminded", 1)


def send_message(doc, message):
	patient_mobile = frappe.db.get_value("Patient", doc.patient, "mobile")
	if patient_mobile:
		context = {"doc": doc, "alert": doc, "comments": None}
		if doc.get("_comments"):
			context["comments"] = json.loads(doc.get("_comments"))

		# jinja to string convertion happens here
		message = frappe.render_template(message, context)
		number = [patient_mobile]
		try:
			send_sms(number, message)
		except Exception as e:
			frappe.msgprint(_("SMS not sent, please check SMS Settings"), alert=True)


@frappe.whitelist()
def get_events(start, end, filters=None):
	"""Returns events for Gantt / Calendar view rendering.

	:param start: Start date-time.
	:param end: End date-time.
	:param filters: Filters (JSON).
	"""
	from frappe.desk.calendar import get_event_conditions

	conditions = get_event_conditions("Patient Appointment", filters)

	data = frappe.db.sql(
		"""
		select
		`tabPatient Appointment`.name, `tabPatient Appointment`.patient,
		`tabPatient Appointment`.practitioner, `tabPatient Appointment`.practitioner_name,
		`tabPatient Appointment`.status, `tabPatient Appointment`.duration,
		`tabPatient Appointment`.appointment_type, `tabPatient Appointment`.patient_name,
		`tabPatient Appointment`.service_unit, `tabPatient Appointment`.notes,
		timestamp(`tabPatient Appointment`.appointment_date, `tabPatient Appointment`.appointment_time) as 'start',
		`tabAppointment Type`.color
		from
		`tabPatient Appointment`
		left join `tabAppointment Type` on `tabPatient Appointment`.appointment_type=`tabAppointment Type`.name
		where
		(`tabPatient Appointment`.appointment_date between %(start)s and %(end)s)
		and `tabPatient Appointment`.status != 'Cancelled' and `tabPatient Appointment`.docstatus < 2 {conditions}""".format(
			conditions=conditions
		),
		{"start": start, "end": end},
		as_dict=True,
		update={"allDay": 0},
	)

	for item in data:
		item.end = item.start + timedelta(minutes=item.duration)
		
		# Special handling for unavailability appointments
		if item.appointment_type == "Unavailable":
			# Force color to be red for unavailability
			item.color = "#ff5858"
			
			# Set a special patient value for the calendar view to identify these
			item.patient = "UNAVAILABLE-BLOCK"
			
			# Ensure title is set to "Unavailable" if patient_name is null
			if not item.patient_name:
				item.patient_name = "UNAVAILABLE"

	return data


@frappe.whitelist()
def get_procedure_prescribed(patient):
	return frappe.db.sql(
		"""
			SELECT
				pp.name, pp.procedure, pp.parent, ct.practitioner,
				ct.encounter_date, pp.practitioner, pp.date, pp.department
			FROM
				`tabPatient Encounter` ct, `tabProcedure Prescription` pp
			WHERE
				ct.patient=%(patient)s and pp.parent=ct.name and pp.appointment_booked=0
			ORDER BY
				ct.creation desc
		""",
		{"patient": patient},
	)


# @frappe.whitelist()
# def get_prescribed_therapies(patient, therapy_plan):
# 	therapy_plan_details = frappe.db.sql(
# 		f"""
# 		SELECT 
# 			tpd.therapy_type, tpd.no_of_sessions, tpd.sessions_completed, tpd.custom_default_duration
# 		FROM 
# 			`tabTherapy Plan Detail`  tpd
# 		Left Join 
# 			`tabTherapy Plan` tp ON tp.name = tpd.parent
# 		Where 
# 			tpd.parent = '{therapy_plan}' and
# 			tp.patient = '{patient}'
# 		""", as_dict=1
# 	)
# 	return therapy_plan_details


@frappe.whitelist()
def create_therapy_sessions(appointment, therapy_types):
	"""
	Create Therapy Sessions from a Patient Appointment
	
	:param appointment: Name of the Patient Appointment
	:param therapy_types: List of Therapy Types to create sessions for
	:returns: List of created Therapy Sessions
	"""
	if isinstance(therapy_types, str):
		therapy_types = json.loads(therapy_types)
		
	appointment_doc = frappe.get_doc("Patient Appointment", appointment)
	created_sessions = []
	duration = 0
	for idx, therapy_type in enumerate(therapy_types):
		therapy_type = frappe._dict(therapy_type)
		# Skip if session already created
		if therapy_type.get("session_created"):
			continue

		# Create the therapy session
		therapy_session = frappe.new_doc("Therapy Session")
		therapy_session.patient = appointment_doc.patient
		therapy_session.therapy_type = therapy_type.therapy_type
		therapy_session.therapy_plan = appointment_doc.therapy_plan
		therapy_session.appointment = appointment_doc.name
		therapy_session.company = appointment_doc.company
		therapy_session.department = appointment_doc.department
		therapy_session.practitioner = appointment_doc.practitioner
		therapy_session.duration = therapy_type.duration or 20
		therapy_session.start_time = appointment_doc.appointment_time if idx == 0 else end_time
		therapy_session.service_unit = appointment_doc.service_unit
		therapy_session.start_date = appointment_doc.appointment_date
		
		# Set end time based on duration
		if appointment_doc.appointment_time:
			appointment_time = datetime.combine(
				getdate(appointment_doc.appointment_date),
				datetime.strptime(str(appointment_doc.appointment_time), '%H:%M:%S').time()
			) if idx == 0 else datetime.combine(
				getdate(appointment_doc.appointment_date),
				datetime.strptime(str(end_time), '%H:%M:%S').time()
			)
			appointment_time += timedelta(minutes=therapy_type.duration or duration or 20)
			therapy_session.end_time = appointment_time.strftime('%H:%M:%S')
			duration = therapy_type.duration or duration or 20
			end_time = appointment_time.strftime('%H:%M:%S')
		
		therapy_session.save()
		
		# Update the therapy in the appointment
		frappe.db.set_value(therapy_type.doctype, therapy_type.name, "session_created", 1)
		frappe.db.set_value(therapy_type.doctype, therapy_type.name, "therapy_session", therapy_session.name)
		created_sessions.append(therapy_session.name)
		
	if not created_sessions:
		frappe.msgprint("Therapy Sessions are already exists")
	return created_sessions


def update_appointment_status():
	def set_status(appointment_doc):
		today = getdate()
		appointment_date = getdate(appointment_doc.appointment_date)

		# If this is an unavailability appointment, always keep it as "Unavailable"
		if appointment_doc.appointment_type == "Unavailable":
			if appointment_doc.status != "Cancelled" and appointment_doc.status != "Unavailable":
				return"Unavailable"
			return
		
		# For new appointments, set default status based on date
		if appointment_doc.is_new():
			if appointment_date == today:
				return "Confirmed"
			elif appointment_date > today:
				return "Scheduled"
			else:
				return "No Show"
			return
			
		# If appointment is already marked as "Needs Rescheduling", we should check if it has been rescheduled
		if appointment_doc.status == "Needs Rescheduling" and appointment_doc.status != "Cancelled":
			# If this has been modified and saved, it means the appointment was rescheduled
			if appointment_doc.modified != appointment_doc.creation:
				if appointment_date > today:
					return "Scheduled"
				elif appointment_date == today:
					return "Open"
				return
			return

		# If appointment is created for today set status as Open else Scheduled
		if appointment_date == today:
			if appointment_doc.status not in ["Checked In", "Checked Out", "Open", "Confirmed", "Cancelled"]:
				return "Open"

		elif appointment_date > today and appointment_doc.status not in ["Scheduled", "Confirmed", "Cancelled"]:
			return "Scheduled"

		elif appointment_date < today and appointment_doc.status not in ["No Show", "Cancelled"]:
			return "No Show"

	
	# update the status of appointments daily
	appointments = frappe.get_all(
		"Patient Appointment", {"status": ("not in", ["Closed", "Cancelled", "Needs Rescheduling", "Unavailable"])}
	)

	for appointment in appointments:
		appointment_doc = frappe.get_doc("Patient Appointment", appointment.name)
		status = set_status(appointment_doc)
		if status:
			appointment_doc.db_set("status" , status, update_modified=False)

	

# Unavailability related methods

@frappe.whitelist()
def check_unavailability_conflicts(filters):
	"""
	Check for appointment conflicts when marking a practitioner or service unit as unavailable
	Returns a list of appointments that conflict with the unavailability
	"""
	filters = frappe.parse_json(filters)
	print(f"Check unavailability conflicts with filters: {filters}")
	
	if not filters:
		return []
	
	# Parse date and times
	appointment_date = getdate(filters.get("date"))
	from_time = get_time(filters.get("from_time"))
	to_time = get_time(filters.get("to_time"))
	
	# Create base filters
	appointment_filters = {
		"status": ["not in", ["Cancelled", "Needs Rescheduling", "Closed"]],
		"appointment_date": appointment_date,
	}
	
	# Add practitioner or service unit to filters based on unavailability_for
	if filters.get("unavailability_for") == "Practitioner":
		if filters.get("practitioner"):
			appointment_filters["practitioner"] = filters.get("practitioner")
	elif filters.get("unavailability_for") == "Service Unit":
		if filters.get("service_unit"):
			appointment_filters["service_unit"] = filters.get("service_unit")
	
	print(f"Appointment filters: {appointment_filters}")
	
	# Get all appointments for the date
	appointments = frappe.get_all(
		"Patient Appointment",
		filters=appointment_filters,
		fields=["name", "patient", "patient_name", "appointment_time", "appointment_type", "status", "duration"]
	)
	
	print(f"Found {len(appointments)} appointments on that date")
	
	# Define unavailability period
	unavailable_start = datetime.combine(appointment_date, from_time)
	unavailable_end = datetime.combine(appointment_date, to_time)
	
	conflicts = []
	
	# Check each appointment for time conflicts
	for appointment in appointments:
		# Skip appointments that are already marked as unavailable
		# if appointment.get("appointment_type") == "Unavailable":
		# 	continue
		
		# Get appointment time as datetime object for comparison
		if isinstance(appointment.appointment_time, str):
			appt_time_str = appointment.appointment_time
			try:
				appt_time = datetime.strptime(appt_time_str, "%H:%M:%S").time()
			except ValueError:
				try:
					# Try alternative format
					appt_time = datetime.strptime(appt_time_str, "%H:%M").time()
				except ValueError:
					frappe.logger().error(f"Could not parse appointment time: {appt_time_str}")
					continue
		elif isinstance(appointment.appointment_time, timedelta):
			midnight = datetime.combine(appointment_date, datetime.min.time())
			appt_time = (midnight + appointment.appointment_time).time()
		else:
			print(f"Unexpected appointment_time type: {type(appointment.appointment_time)}")
			continue
		
		# Calculate appointment start and end datetimes
		appt_start = datetime.combine(appointment_date, appt_time)
		appt_end = appt_start + timedelta(minutes=appointment.duration or 15)
		
		# Check for overlap
		# An overlap exists if:
		# - Appointment starts during unavailability period
		# - Appointment ends during unavailability period
		# - Appointment spans the entire unavailability period
		if (unavailable_start <= appt_start < unavailable_end) or \
		   (unavailable_start < appt_end <= unavailable_end) or \
		   (appt_start <= unavailable_start and appt_end >= unavailable_end):
			
			# Format time for display
			appointment['appointment_time'] = appt_time.strftime("%H:%M:%S")
			conflicts.append(appointment)
	
	return conflicts

@frappe.whitelist()
def get_unavailability_appointments(date=None):
	"""
	Get unavailability appointments for a given date
	
	Args:
		date: Date to check (defaults to today)
		
	Returns:
		List of unavailability appointments
	"""
	if not date:
		date = getdate()
	else:
		date = getdate(date)
	
	return frappe.get_all(
		"Patient Appointment",
		filters={
			"appointment_date": date,
			"appointment_type": "Unavailable",
			"status": ["!=", "Cancelled"]
		},
		fields=[
			"name", "practitioner", "practitioner_name", "service_unit", 
			"appointment_time", "duration", "status", "notes"
		]
	)

@frappe.whitelist()
def cancel_unavailability_appointment(appointment_name):
	"""
	Cancel an unavailability appointment
	
	Args:
		appointment_name: Name of the appointment to cancel
		
	Returns:
		True if successful
	"""
	if not appointment_name:
		frappe.throw(_("Appointment name is required"))
	
	appointment = frappe.get_doc("Patient Appointment", appointment_name)
	
	# Verify this is an unavailability appointment
	if appointment.appointment_type != "Unavailable":
		frappe.throw(_("This is not an unavailability appointment"))
	
	# Instead of saving the document which tries to modify set_only_once fields,
	# directly update the status in the database
	frappe.db.set_value("Patient Appointment", appointment_name, "status", "Cancelled")
	
	# Cancel the linked event if it exists
	if appointment.event:
		try:
			event_doc = frappe.get_doc("Event", appointment.event)
			event_doc.status = "Cancelled"
			event_doc.save(ignore_permissions=True)
		except Exception as e:
			frappe.log_error(f"Error cancelling event for unavailability appointment: {str(e)}")
	
	frappe.msgprint(_("Unavailability record cancelled successfully"), alert=True)
	return True

def setup_appointment_type_for_unavailability():
	"""Set up the Unavailable appointment type if it doesn't exist"""
	if not frappe.db.exists("Appointment Type", "Unavailable"):
		appointment_type = frappe.new_doc("Appointment Type")
		appointment_type.update({
			"appointment_type": "Unavailable",
			"default_duration": 60,
			"color": "#ff5858",
			"price": 0,
			"description": "System appointment type for marking unavailability"
		})
		appointment_type.insert(ignore_permissions=True)
		frappe.db.commit()

@frappe.whitelist()
def create_unavailability_appointment(data):
	"""
	Create an appointment to mark time as unavailable
	
	Args:
		data: A dict or JSON string containing:
			- unavailability_for: "Practitioner" or "Service Unit"
			- practitioner: Name of practitioner (if applicable)
			- service_unit: Name of service unit (if applicable)
			- date: Date for unavailability
			- from_time: Start time
			- to_time: End time
			- reason: Reason for unavailability
			- conflicts: List of conflicting appointments
			
	Returns:
		Created appointment document
	"""
	if isinstance(data, str):
		data = json.loads(data)
	
	# Setup Unavailable appointment type if it doesn't exist
	setup_appointment_type_for_unavailability()
	
	# Parse date and times
	date = getdate(data.get('date'))
	from_time = get_time(data.get('from_time'))
	to_time = get_time(data.get('to_time'))
	
	# Calculate duration in minutes - very important for proper calendar display
	from_datetime = datetime.combine(date, from_time)
	to_datetime = datetime.combine(date, to_time)
	duration = (to_datetime - from_datetime).total_seconds() / 60
	
	print(f"Creating unavailability from {from_time} to {to_time} on {date}")
	print(f"Calculated duration: {duration} minutes")
	
	# Detect if there are conflicts but don't modify them
	has_conflicts = False
	
	if data.get('conflicts'):
		conflicts = data.get('conflicts')
		if conflicts and isinstance(conflicts, list) and len(conflicts) > 0:
			has_conflicts = True
			print(f"Detected {len(conflicts)} conflicts, but not modifying them per user request")
	
	# Set the company - required field
	# In some versions of Healthcare, practitioners might not have a company field
	company = None
	try:
		if data.get('practitioner'):
			# First check if the company field exists in the doctype
			practitioner_meta = frappe.get_meta("Healthcare Practitioner")
			if practitioner_meta.has_field("company"):
				company = frappe.db.get_value("Healthcare Practitioner", data.get('practitioner'), "company")
	except Exception as e:
		print(f"Error getting company from practitioner: {str(e)}")
		company = None
	
	# If we couldn't get the company from the practitioner, use the default
	if not company:
		company = frappe.defaults.get_user_default('company')
		
	# If we still don't have a company, try to get the first company in the system
	if not company:
		companies = frappe.get_all("Company", limit=1)
		if companies:
			company = companies[0].name
			
	# Create a new appointment document - now using standard Frappe approach
	# instead of trying to directly manipulate the database
	appointment = frappe.new_doc("Patient Appointment")
	
	# Set all the standard fields
	appointment.naming_series = "HLC-APP-.YYYY.-"
	appointment.appointment_type = "Unavailable"
	appointment.status = "Unavailable"
	appointment.company = company
	appointment.appointment_for = data.get('unavailability_for', "Practitioner")
	appointment.appointment_date = date
	appointment.appointment_time = str(from_time)
	appointment.duration = duration
	appointment.notes = data.get('reason', "Marked as unavailable")
	
	# Set practitioner or service unit based on unavailability_for
	if data.get('unavailability_for') == "Practitioner":
		appointment.practitioner = data.get('practitioner')
		if data.get('practitioner'):
			try:
				practitioner_name = frappe.db.get_value("Healthcare Practitioner", data.get('practitioner'), "practitioner_name")
				appointment.practitioner_name = practitioner_name
			except Exception as e:
				print(f"Error getting practitioner name: {str(e)}")
				try:
					practitioner_doc = frappe.get_doc("Healthcare Practitioner", data.get('practitioner'))
					appointment.practitioner_name = practitioner_doc.practitioner_name
				except Exception:
					appointment.practitioner_name = "Unknown Practitioner"
				
	elif data.get('unavailability_for') == "Service Unit":
		appointment.service_unit = data.get('service_unit')
	
	# Set patient_name to indicate it's an unavailability record
	# Format times for better display
	from_time_str = from_time.strftime("%H:%M")
	to_time_str = to_time.strftime("%H:%M")
	time_range = f"{from_time_str} to {to_time_str}"
	
	if appointment.practitioner_name:
		appointment.patient_name = f"UNAVAILABLE: {appointment.practitioner_name} ({time_range})"
	elif appointment.service_unit:
		appointment.patient_name = f"UNAVAILABLE: {appointment.service_unit} ({time_range})"
	else:
		appointment.patient_name = f"UNAVAILABLE ({time_range})"
	
	# Explicitly set the title to match patient_name
	appointment.title = appointment.patient_name
	
	# Add end time data
	appointment.appointment_end_time = str(to_time)
	appointment.appointment_end_datetime = to_datetime.strftime('%Y-%m-%d %H:%M:%S')
	# Ensure end_time is properly formatted as HH:MM:SS
	appointment.end_time = to_time.strftime('%H:%M:%S')
	
	# Mark this as an unavailability appointment to bypass validation
	appointment.is_unavailability = True
	
	# Skip validation that would normally require a patient
	appointment.flags.ignore_validate = True
	appointment.flags.ignore_mandatory = True
	
	# Insert the document
	appointment.insert(ignore_permissions=True)
	
	print(f"Created unavailability appointment: {appointment.name}")
	print(f"Appointment duration: {duration} minutes, end time: {to_time}")
	
	# After insert, double-check that title matches patient_name and end_time is set
	update_values = {}
	if appointment.title != appointment.patient_name:
		update_values["title"] = appointment.patient_name
	
	# Double-check that end_time is set correctly
	if not appointment.end_time or appointment.end_time != to_time.strftime('%H:%M:%S'):
		update_values["end_time"] = to_time.strftime('%H:%M:%S')
	
	if update_values:
		frappe.db.set_value(
			"Patient Appointment",
			appointment.name,
			update_values,
			update_modified=False
		)
		print(f"Fixed values after insert: {update_values}")
	
	# Notify of update to refresh any views
	appointment.notify_update()
	
	# Include end_time in the response for the JavaScript
	return {
		"name": appointment.name,
		"date": date.strftime('%Y-%m-%d'),
		"from_time": from_time.strftime('%H:%M:%S'),
		"to_time": to_time.strftime('%H:%M:%S'),
		"end_time": to_time.strftime('%H:%M:%S'),
		"duration": duration
	}

@frappe.whitelist()
def update_appointment_end_times():
	"""
	Utility function to update appointment end times based on duration for existing appointments.
	Can be run as a patch or called manually to fix existing appointments.
	"""
	from datetime import datetime, timedelta
	from frappe.utils import getdate, get_time, flt
	
	count = 0
	# Get all appointments that have a duration but no end time
	appointments = frappe.get_all(
		"Patient Appointment", 
		filters={"duration": ["not in", ["", 0, None]]},
		fields=["name", "appointment_date", "appointment_time", "duration", "appointment_end_time"]
	)
	
	for appointment in appointments:
		if not appointment.appointment_end_time:
			try:
				start_dt = datetime.combine(
					getdate(appointment.appointment_date), 
					get_time(appointment.appointment_time)
				)
				end_dt = start_dt + timedelta(minutes=flt(appointment.duration))
				end_time = end_dt.time().strftime("%H:%M:%S")
				end_datetime = f"{appointment.appointment_date} {end_time}"
				
				frappe.db.set_value(
					"Patient Appointment", 
					appointment.name, 
					{
						"appointment_end_time": end_time,
						"appointment_end_datetime": end_datetime,
						"end_time": end_time
					},
					update_modified=False
				)
				count += 1
				
				# Update the calendar event too
				event_name = frappe.db.get_value("Patient Appointment", appointment.name, "event")
				if event_name:
					frappe.db.set_value("Event", event_name, "ends_on", end_dt, update_modified=False)
					
			except Exception as e:
				print(f"Error updating appointment {appointment.name}: {str(e)}")
	
	frappe.db.commit()
	print(f"Updated end times for {count} appointments")

@frappe.whitelist()
def update_unavailability_appointment_names():
	"""
	Utility function to update existing unavailability appointments with descriptive names
	including time range information. Can be run as a patch or called manually.
	"""
	# Get all unavailability appointments
	appointments = frappe.get_all(
		"Patient Appointment", 
		filters={
			"appointment_type": "Unavailable",
			"status": ["!=", "Cancelled"]
		},
		fields=["name", "practitioner", "practitioner_name", "service_unit", 
				"appointment_time", "appointment_end_time", "duration", 
				"appointment_date", "notes"]
	)
	
	count = 0
	for appointment in appointments:
		try:
			# Get properly formatted times
			from_time = get_time(appointment.appointment_time)
			from_time_str = from_time.strftime("%H:%M")
			
			# Get or calculate end time
			if appointment.appointment_end_time:
				to_time = get_time(appointment.appointment_end_time)
				to_time_str = to_time.strftime("%H:%M")
			else:
				# Calculate end time if not set
				if appointment.duration:
					start_dt = datetime.combine(getdate(appointment.appointment_date), from_time)
					end_dt = start_dt + timedelta(minutes=flt(appointment.duration))
					to_time_str = end_dt.time().strftime("%H:%M")
				else:
					to_time_str = "??:??"
			
			time_range = f"{from_time_str} to {to_time_str}"
			
			# Create new patient_name with time information
			patient_name = None
			if appointment.practitioner:
				patient_name = f"UNAVAILABLE: {appointment.practitioner_name or appointment.practitioner} ({time_range})"
			elif appointment.service_unit:
				patient_name = f"UNAVAILABLE: {appointment.service_unit} ({time_range})"
			else:
				patient_name = f"UNAVAILABLE ({time_range})"
			
			# Update the appointment
			if patient_name:
				title = patient_name  # Use same format for title
				frappe.db.set_value(
					"Patient Appointment", 
					appointment.name, 
					{
						"patient_name": patient_name,
						"title": title
					},
					update_modified=False
				)
				count += 1
				
		except Exception as e:
			print(f"Error updating appointment {appointment.name}: {str(e)}")
	
	frappe.db.commit()
	print(f"Updated names for {count} unavailability appointments")
	return count


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def apply_filter_on_therapy_type(doctype, txt, searchfield, start, page_len, filters):
	if not filters.get("therapy_plan"):
		frappe.throw("Please set therapy plan first")
	conditions = ''
	if txt:
		conditions += f" and therapy_type like '%{txt}%'"
	return frappe.db.sql(f"""
			Select therapy_type, no_of_sessions, custom_default_duration
			From `tabTherapy Plan Detail` as tpd
			Where parent = '{filters.get("therapy_plan")}' {conditions}
			""")