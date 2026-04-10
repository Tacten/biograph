frappe.provide("healthcare.utils");

healthcare.utils.set_codification_table_query = function (frm) {
	const grid = frm.fields_dict["codification_table"]?.grid;
	if (!grid) return;

	grid.get_field("code_value_set").get_query = function (doc, cdt, cdn) {
		let row = locals[cdt][cdn];
		if (!row) return;

		if (row.code_system) {
			return {
				filters: {
					code_system: row.code_system,
				},
			};
		}
	};

	grid.get_field("code_value").get_query = function (doc, cdt, cdn) {
		let row = locals[cdt][cdn];
		if (!row) return;

		if (row.code_system && row.code_value_set) {
			return {
				filters: {
					code_system: row.code_system,
					value_set: row.code_value_set,
				},
			};
		}

		if (row.code_system) {
			return {
				filters: {
					code_system: row.code_system,
				},
			};
		}
	};
};

healthcare.utils.before_save_check = async function (frm) {
	const codification_rows = frm.doc.codification_table || [];

	for (const row of codification_rows) {
		if (!row.code_value) {
			continue;
		}

		try {
			const response = await frappe.call({
				method: "healthcare.healthcare.utils.get_codification_row_code_data",
				args: {
					code_value: row.code_value,
					code_system: row.code_system,
				},
			});

			const server_value_set = response?.message?.row_data?.value_set;

			if (row.code_value_set && row.code_value_set !== server_value_set) {
				frappe.msgprint(__("Mismatch in Code-data for row {0}", [row.idx]));
				frappe.validated = false;
				return false;
			}
		} catch (e) {
			frappe.msgprint(__("Error checking row {0}: {1}", [row.idx, e.message]));
			frappe.validated = false;
			return false;
		}
	}

	return true;
};

healthcare.utils.auto_table_code_val_set = function (frm, cdt, cdn) {
	var row = locals[cdt][cdn];

	if (!row.code_value_set && row.code_value) {
		frappe.call({
			method: "frappe.client.get_value",
			args: {
				doctype: "Code Value",
				filters: {
					name: row.code_value,
					code_system: row.code_system,
				},
				fieldname: ["value_set"],
			},
			callback: function (response) {
				if (response.message && response.message.value_set) {
					frappe.model.set_value(
						cdt,
						cdn,
						"code_value_set",
						response.message.value_set,
					);
					frm.refresh_field("codification_table");
				}
			},
		});
	}
};
