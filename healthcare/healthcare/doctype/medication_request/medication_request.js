// Copyright (c) 2022, healthcare and contributors
// For license information, please see license.txt
{% include "healthcare/healthcare/service_request.js" %}

frappe.ui.form.on('Medication Request', {
    refresh: function(frm) {
        frm.set_query("status", function () {
			return {
				"filters": {
					"code_system": "Medication Request Status",
				}
			};
		});

		frappe.require("assets/healthcare/js/utils.js", function () {
			healthcare.utils.set_codification_table_query(frm);
		});
	},

	before_save: async function (frm) {
		await new Promise(function (resolve) {
			frappe.require("assets/healthcare/js/utils.js", resolve);
		});
		await healthcare.utils.before_save_check(frm);
	},
});

frappe.ui.form.on("Codification Table", {
	code_value_set: function (frm, cdt, cdn) {
		frappe.require("assets/healthcare/js/utils.js", function () {
			healthcare.utils.set_codification_table_query(frm);
		});
	},
	code_system: function (frm, cdt, cdn) {
		frappe.require("assets/healthcare/js/utils.js", function () {
			healthcare.utils.set_codification_table_query(frm);
		});
	},
	code_value: function (frm, cdt, cdn) {
		var row = locals[cdt][cdn];
		if (!row.code_value_set) {
			frappe.require("assets/healthcare/js/utils.js", function () {
				healthcare.utils.auto_table_code_val_set(frm, cdt, cdn);
			});
		}
		frappe.require("assets/healthcare/js/utils.js", function () {
			healthcare.utils.set_codification_table_query(frm);
		});
	},
})
