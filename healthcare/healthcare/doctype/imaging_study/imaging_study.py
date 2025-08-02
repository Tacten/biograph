# Copyright (c) 2025, earthians Health Informatics Pvt. Ltd. and contributors
# For license information, please see license.txt

import json

import requests

import frappe
from frappe.model.document import Document
from frappe.utils.password import get_decrypted_password


class ImagingStudy(Document):
	def after_insert(self):
		self.build_series_with_previews()

	def build_series_with_previews(self):
		dataset = json.loads(self.dataset) if isinstance(self.dataset, str) else self.dataset
		if not dataset:
			return

		config = self.get_config()
		auth = self.get_auth(config)
		study_uid = dataset.get("0020000D", {}).get("Value", [None])[0]
		series_list = dataset.get("00400340", {}).get("Value", [])
		preview_json = []

		for series in series_list:
			series_uid = series.get("0020000E", {}).get("Value", [None])[0]
			description = series.get("0008103E", {}).get("Value", [None])[0]
			modality = series.get("00080060", {}).get("Value", [None])[0]

			if not series_uid:
				continue

			instance_uids = self.get_instance_metadata(config, study_uid, series_uid, auth)
			instance_count = len(instance_uids)
			first_instance_uid = instance_uids[0] if instance_uids else None

			entry = {
				"SeriesInstanceUID": series_uid,
				"SeriesDescription": description,
				"Modality": modality,
				"InstanceCount": instance_count,
			}

			if first_instance_uid:
				file_url = self.fetch_and_attach_preview(
					config, study_uid, series_uid, first_instance_uid, auth
				)
				if file_url:
					entry["preview_url"] = file_url

			preview_json.append(entry)

		if preview_json:
			self.db_set("preview_json", json.dumps(preview_json, indent=1))

	def get_instance_metadata(self, config, study_uid, series_uid, auth):
		base_url = config.get("pacs_base_url", "").rstrip("/")
		qido_url = config.get("qido_rs_url", "").lstrip("/")
		url = f"{base_url}/{qido_url}".format(series_uid=series_uid)

		try:
			resp = requests.get(url, auth=auth, timeout=10)
			resp.raise_for_status()
			instances = resp.json()
			return [
				item.get("00080018", {}).get("Value", [None])[0] for item in instances if "00080018" in item
			]
		except Exception as e:
			frappe.log_error(f"{str(e)}\n{url}", "QIDO-RS failure")
			return []

	def fetch_and_attach_preview(self, config, study_uid, series_uid, instance_uid, auth):
		base_url = config.get("pacs_base_url", "").rstrip("/")
		wado_url = config.get("wado_rs_url", "").lstrip("/")
		url = f"{base_url}/{wado_url}".format(
			study_uid=study_uid, series_uid=series_uid, sop_instance_uid=instance_uid
		)

		try:
			resp = requests.get(url, headers={"Accept": "image/jpeg"}, auth=auth, timeout=10)
			resp.raise_for_status()
			jpeg = resp.content
			return self.attach_preview_file(series_uid, jpeg)
		except Exception as e:
			frappe.log_error(f"{str(e)}\n{url}", "WADO-RS preview failed")
			return None

	def get_config(self):
		return frappe.get_cached_doc("Healthcare Settings").as_dict()

	def get_auth(self, config):
		return (
			config.get("pacs_username"),
			get_decrypted_password("Healthcare Settings", "Healthcare Settings", fieldname="pacs_password"),
		)

	def get_first_instance_uid(self, series):
		ref_seq = series.get("00081140", {}).get("Value", [])
		return ref_seq[0].get("00081155", {}).get("Value", [None])[0] if ref_seq else None

	def attach_preview_file(self, series_uid, jpeg_data, filename=None):
		file_doc = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": filename or f"{series_uid}.jpeg",
				"attached_to_doctype": "Imaging Study",
				"attached_to_name": self.name,
				"content": jpeg_data,
				"is_private": 1,
			}
		)
		file_doc.save()
		return file_doc.file_url


def humanize_dicom_json(dicom_json):
	from pydicom.datadict import keyword_for_tag
	from pydicom.tag import Tag

	if isinstance(dicom_json, str):
		dicom_json = json.loads(dicom_json)

	def tag_label(tag_str):
		try:
			tag = Tag(int(tag_str[:4], 16), int(tag_str[4:], 16))
			keyword = keyword_for_tag(tag) or "Unknown"
			return f"{keyword} ({tag.group:04X},{tag.element:04X})"
		except Exception:
			return tag_str

	def parse(item):
		if not isinstance(item, dict):
			return item
		parsed = {}
		for tag_str, value_dict in item.items():
			label = tag_label(tag_str)
			if isinstance(value_dict, dict) and value_dict.get("vr") == "SQ":
				parsed[label] = [parse(i) for i in value_dict.get("Value", []) if isinstance(i, dict)]
			else:
				parsed[label] = value_dict.get("Value", [])
		return parsed

	return parse(dicom_json)


def build_dicom_hierarchy(mpps_data):
	def get_val(obj, tag):
		return obj.get(tag, {}).get("Value", [None])[0]

	study_uid = get_val(mpps_data, "0020000D")

	result = {"StudyInstanceUID": study_uid, "Series": []}

	series_list = mpps_data.get("00400340", {}).get("Value", [])
	for series in series_list:
		series_uid = get_val(series, "0020000E")
		modality = get_val(series, "00080060")
		description = get_val(series, "0008103E")

		instances = []
		for ref in series.get("00081140", {}).get("Value", []):
			sop_uid = get_val(ref, "00081155")
			sop_class = get_val(ref, "00081150")
			if sop_uid and sop_class:
				instances.append({"SOPInstanceUID": sop_uid, "SOPClassUID": sop_class})

		result["Series"].append(
			{
				"SeriesInstanceUID": series_uid,
				"Modality": modality,
				"SeriesDescription": description,
				"Instances": instances,
			}
		)

	return result
