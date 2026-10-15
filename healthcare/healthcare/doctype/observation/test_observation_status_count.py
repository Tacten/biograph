from frappe.tests import UnitTestCase

from healthcare.healthcare.doctype.observation.observation import (
	aggregate_and_return_observation_data,
	return_child_observation_data_as_dict,
)


class TestObservationStatusCount(UnitTestCase):
	def test_leaf_without_permitted_data_type_is_counted(self):
		leaf = {
			"name": "OBS-IMG",
			"has_component": 0,
			"permitted_data_type": None,
			"status": "Approved",
		}
		_, length = aggregate_and_return_observation_data([leaf])
		self.assertEqual(length, 1)

		child = {
			"name": "OBS-CHILD",
			"has_component": 0,
			"permitted_data_type": "",
			"status": "Approved",
		}
		_, child_length = return_child_observation_data_as_dict([child], {"name": "OBS-PARENT"}, 0)
		self.assertEqual(child_length, 1)
