# Copyright (c) 2025, earthians Health Informatics Pvt. Ltd. and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _, generate_hash
from frappe.model.document import Document


class ImagingAppointment(Document):
	def autoname(self):
		self.name = generate_hash(length=16)  # accession number VR SH 16

	def before_insert(self):
		if not self.ups_instance_uid:
			settings = frappe.get_cached_doc("Healthcare Settings")
			if not settings.uid_root:
				frappe.throw(_("UPS Instance UID root is not configured in Healthcare Settings"))
			self.ups_instance_uid = (
				f"{settings.uid_root.rstrip('.')}.{frappe.utils.now_datetime().strftime('%Y%m%d%H%M%S%f')}"
			)

	def on_update(self):
		if self.status == "In Progress":
			pass  # nothing to do (?)
		elif self.status == "Completed" and self.study_instance_uid:
			frappe.db.set_value("Patient Appointment", self.appointment, "status", "Closed")

			self.create_imaging_study()
			self.create_observation()

	def create_imaging_study(self):
		if not frappe.db.exists("Imaging Study", {"study_instance_uid": self.study_instance_uid}):
			mpps_data = json.loads(self.n_set)
			study = frappe.new_doc("Imaging Study")
			study.patient = mpps_data.get("patient", self.patient)
			study.study_instance_uid = mpps_data.get("study_instance_uid", self.study_instance_uid)
			study.imaging_appointment = mpps_data.get("accession_number", self.name)
			study.station_ae = mpps_data.get("performed_station_ae", self.station_ae)
			study.completed_on = mpps_data.get("end_time", frappe.utils.now())
			study.performer = mpps_data.get("performer_name", "")
			study.status = "Pending Review"

			study.series = json.dumps(mpps_data.get("series", []), indent=1)
			study.instances = json.dumps(mpps_data.get("instances", []), indent=1)
			study.dataset = json.dumps(mpps_data.get("raw_ds", []), indent=1)
			study.save(ignore_permissions=True)
			study.reload()

			self.db_set("imaging_study", study.name)

	def create_observation(self):
		if not frappe.db.exists("Observation", {"appointment": self.name}):
			obs = frappe.new_doc("Observation")
			obs.patient = self.patient
			obs.observation_template = self.observation_template
			obs.observation_type = "Imaging"
			obs.accession_number = self.name
			obs.study_instance_uid = self.study_instance_uid
			obs.appointment = self.appointment
			obs.imaging_study = self.imaging_study
			obs.status = "Preliminary"
			obs.save(ignore_permissions=True)
