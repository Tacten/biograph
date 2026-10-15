// Copyright (c) 2026, earthians Health Informatics Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.provide("healthcare.emergency");

frappe.listview_settings["Emergency Record"] = {
	add_fields: ["triage_level", "status"],

	get_indicator(doc) {
		const colors = {
			Registered: "blue",
			Triaged: "orange",
			"In Treatment": "yellow",
			"Awaiting Disposition": "purple",
			Closed: "green",
			Cancelled: "gray",
		};
		return [__(doc.status), colors[doc.status] || "gray", "status,=," + doc.status];
	},

	onload(listview) {
		if (healthcare.emergency.triage_colors) {
			return;
		}
		frappe.db
			.get_list("Triage Level", { fields: ["name", "color"], limit: 0 })
			.then(rows => {
				healthcare.emergency.triage_colors = {};
				rows.forEach(
					row => (healthcare.emergency.triage_colors[row.name] = row.color),
				);
				listview.refresh();
			});
	},

	formatters: {
		triage_level(value) {
			if (!value) {
				return "";
			}
			const colors = healthcare.emergency.triage_colors || {};
			const color = colors[value] || "#a6b1b9";
			return `<span style="display:inline-flex;align-items:center;gap:6px">
				<span style="width:10px;height:10px;border-radius:50%;background:${color}"></span>
				${frappe.utils.escape_html(value)}
			</span>`;
		},
	},
};
