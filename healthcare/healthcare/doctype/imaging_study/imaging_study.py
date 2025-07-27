# Copyright (c) 2025, earthians Health Informatics Pvt. Ltd. and contributors
# For license information, please see license.txt

import json

import requests

import frappe
from frappe.model.document import Document
from frappe.utils.file_manager import save_file
from frappe.utils.password import get_decrypted_password


class ImagingStudy(Document):
	def after_insert(self):
		# trigger thumbnail fetch
		self.fetch_and_attach_thumbnails_for_study()

	def get_pacs_config(self):
		return frappe.get_cached_doc("Healthcare Settings").as_dict()

	@frappe.whitelist()
	def fetch_and_attach_thumbnails_for_study(self):
		if not self.series:
			return

		try:
			series_list = frappe.parse_json(self.series)
		except Exception as e:
			frappe.log_error(f"Invalid JSON in series: {e}", "Fetch Thumbnails")
			return

		config = self.get_pacs_config()
		base_url = config.get("pacs_base_url")
		base_url = base_url and base_url.rstrip("/")
		auth = (
			config.get("pacs_username"),
			get_decrypted_password("Healthcare Settings", "Healthcare Settings", fieldname="pacs_password"),
		)
		qido_rs_url = config.get("qido_rs_url")
		wado_rs_url = config.get("wado_rs_url")

		preview_attached = False
		structured_series = []

		for s in series_list:
			series_uid = s.get("series_uid")
			if not series_uid:
				frappe.log_error("QIDO - Series UID not found", "Fetch Thumbnails")
				continue

			qido_url = f"{base_url}/{qido_rs_url}".format(series_uid=series_uid)
			try:
				qido_resp = requests.get(
					qido_url, headers={"Accept": "application/json"}, auth=auth, timeout=10
				)
				qido_resp.raise_for_status()
				instance_results = qido_resp.json()
			except Exception as e:
				frappe.log_error(f"QIDO fetch failed for {series_uid}: {e}", "Fetch Thumbnails (QIDO)")
				continue

			instance_preview_files = []

			for inst in instance_results:
				try:
					study_uid = inst["0020000D"]["Value"][0]
					sop_instance_uid = inst["00080018"]["Value"][0]
					# series_uid_in_instance = inst["0020000E"]["Value"][0]
				except Exception as e:
					frappe.log_error(f"Missing tags in QIDO response: {e}", "Fetch Thumbnails (QIDO)")
					continue

				wado_url = f"{base_url}/{wado_rs_url.format(series_uid=series_uid, study_uid=study_uid, sop_instance_uid=sop_instance_uid)}"
				try:
					wado_resp = requests.get(wado_url, auth=auth, headers={"Accept": "image/jpeg"}, timeout=10)
					if wado_resp.status_code != 200:
						frappe.log_error(
							f"WADO preview failed: {wado_resp.status_code} - {wado_resp.text}",
							"Fetch Thumbnails (WADO)",
						)
						continue

					thumbnail_bytes = wado_resp.content
					fname = f"{sop_instance_uid}_preview.jpg"
					file_doc = save_file(
						fname=fname,
						content=thumbnail_bytes,
						dt="Imaging Study",
						dn=self.name,
						is_private=1,
						decode=False,
					)

					if not preview_attached:
						self.thumbnail = file_doc.file_url
						preview_attached = True

					instance_preview_files.append(
						{
							"sop_instance_uid": sop_instance_uid,
							"preview_url": wado_url,
							"file_url": file_doc.file_url,
						}
					)
				except Exception as e:
					frappe.log_error(f"WADO fetch failed for {sop_instance_uid}: {e}", "Fetch Thumbnails (WADO)")
					continue

			structured_series.append(
				{
					"series_uid": series_uid,
					"modality": s.get("modality"),
					"description": s.get("description"),
					"num_instances": len(instance_results),
					"instance_previews": instance_preview_files,
					"series_preview": instance_preview_files[0].get("file_url"),
				}
			)

		self.db_set("series_json", json.dumps(structured_series, indent=1))
