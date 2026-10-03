# Copyright (c) 2015, ESS and Contributors
# See license.txt

import frappe

from healthcare.healthcare.doctype.sample_collection.sample_collection import (
	SampleCollection,
	get_collection_status,
)
from healthcare.tests.utils import HealthcareTestSuite


class TestSampleCollection(HealthcareTestSuite):
	def test_validate_status_handles_all_collection_states(self):
		test_cases = [
			([], "Collected"),
			([frappe._dict({"status": "Open"})], "Pending"),
			([frappe._dict({"status": "Collected"})], "Collected"),
			([frappe._dict({"status": "Collected"}), frappe._dict({"status": "Open"})], "Partly Collected"),
		]

		for child_rows, expected_status in test_cases:
			with self.subTest(child_rows=child_rows, expected_status=expected_status):
				doc = frappe._dict(observation_sample_collection=child_rows, status=None)
				SampleCollection.validate(doc)
				self.assertEqual(doc.status, expected_status)

	def test_get_collection_status_handles_all_collection_states(self):
		test_cases = [
			([], "Collected"),
			([frappe._dict({"status": "Open"})], "Pending"),
			([frappe._dict({"status": "Collected"})], "Collected"),
			([frappe._dict({"status": "Collected"}), frappe._dict({"status": "Open"})], "Partly Collected"),
		]

		for child_rows, expected_status in test_cases:
			with self.subTest(child_rows=child_rows, expected_status=expected_status):
				self.assertEqual(get_collection_status(child_rows), expected_status)
