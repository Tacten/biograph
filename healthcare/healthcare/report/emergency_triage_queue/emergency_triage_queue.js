// Copyright (c) 2026, earthians Health Informatics Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.query_reports["Emergency Triage Queue"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
		},
	],
	formatter(value, row, column, data, default_formatter) {
		if (column.fieldname === "acuity") {
			return value || "";
		}
		return default_formatter(value, row, column, data);
	},
};
