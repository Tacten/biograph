# Copyright (c) 2025, earthians and contributors
# For license information, please see license.txt

import frappe


def get_dicomweb_verification():
	"""Simple ping-like check for DICOMWeb clients"""
	return {
		"status": "success",
		"message": "Marley DICOMWeb service is online.",
		"timestamp": frappe.utils.now(),
	}


def get_conformance_statement():
	"""Return a minimal conformance statement or HTML page"""
	return {
		"service": "DICOMWeb UPS-RS",
		"version": "16.0.0-dev",
		"organization": "Marley Health",
		"contact": "support@marleyhealth.io",
		"supported_endpoints": [
			"POST /dicom-web/workitems",
			"PUT /dicom-web/workitems/{uid}",
			"POST /dicom-web/workitems/{uid}/claim",
			"POST /dicom-web/workitems/{uid}/cancelrequest",
			"POST /dicom-web/workitems/{uid}/workitemevent",
			"GET /dicom-web/workitems",
		],
		"formats": ["application/dicom+json"],
		"authentication": "Header-based: X-AE-TITLE + X-AE-TOKEN",
		"note": "Only UPS-RS is supported at this endpoint.\n\
			If UPS SOP Instance UID is not available, you can use Accession Number or Study Instance UID for workitem updates",
	}
