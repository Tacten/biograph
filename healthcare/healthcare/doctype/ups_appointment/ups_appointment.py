# Copyright (c) 2025, earthians Health Informatics Pvt. Ltd. and contributors
# For license information, please see license.txt

import json
import os

import shortuuid
from pydicom.uid import UID

import frappe
from frappe.model.document import Document

MPPS_SOP_CLASS = UID("1.2.840.10008.3.1.2.3.3")
STORAGE_SOP_CLASS = UID("1.2.840.10008.5.1.4.1.1.2")
CONFIG_PATH = os.path.expanduser("~/.marley_modality/config.yaml")

DEFAULTS = {  # settings
	"ae_title": "TEST_HARNESS",
	"ris": {"ae_title": "MARLEY-RIS", "host": "127.0.0.1", "port": 104},
	"pacs": {
		"host": "localhost",
		"port": 4242,
		"ae_title": "ORTHANC",
		"url": "http://localhost:8042/dicom-web/studies",
		"username": "orthanc",
		"password": "orthanc",
	},
	"sample_dicom": "./IMAGES/CT-1/ct-sample.dcm",
}


class UPSAppointment(Document):
	def before_insert(self):
		self.ups_instance_uid = str(shortuuid.uuid())

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
			study.ups_appointment = mpps_data.get("accession_number", self.name)
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
