// Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Therapy Type', {
	setup: function(frm) {
		frm.get_field('exercises').grid.editable_fields = [
			{fieldname: 'exercise_type', columns: 7},
			{fieldname: 'difficulty_level', columns: 1},
			{fieldname: 'counts_target', columns: 1},
			{fieldname: 'assistance_level', columns: 1}
		];
	},

	refresh: function(frm) {
		if (!frm.doc.__islocal) {
			cur_frm.add_custom_button(__('Change Item Code'), function() {
				change_template_code(frm.doc);
			});
		}

		frm.set_query("code_value", "codification_table", function(doc, cdt, cdn) {
			let row = frappe.get_doc(cdt, cdn);
			if (row.code_system) {
				return {
					filters: {
						code_system: row.code_system
					}
				};
			}
		})

		frm.set_query('staff_role', function () {
			return {
				filters: {
					'restrict_to_domain': 'Healthcare'
				}
			};
		});
	},

	therapy_type: function(frm) {
		if (!frm.doc.item_code)
			frm.set_value('item_code', frm.doc.therapy_type);
		if (!frm.doc.description)
			frm.set_value('description', frm.doc.therapy_type);
	},
});

let change_template_code = function(doc) {
	let d = new frappe.ui.Dialog({
		title:__('Change Item Code'),
		fields:[
			{
				'fieldtype': 'Data',
				'label': 'Item Code',
				'fieldname': 'item_code',
				reqd: 1
			}
		],
		primary_action: function() {
			let values = d.get_values();

			if (values) {
				frappe.call({
					'method': 'healthcare.healthcare.doctype.therapy_type.therapy_type.change_item_code_from_therapy',
					'args': {item_code: values.item_code, doc: doc},
					callback: function () {
						cur_frm.reload_doc();
						frappe.show_alert({
							message: 'Item Code renamed successfully',
							indicator: 'green'
						});
					}
				});
			}
			d.hide();
		},
		primary_action_label: __('Change Item Code')
	});
	d.show();

	d.set_values({
		'item_code': doc.item_code
	});
};


frappe.ui.form.on('Clinical Procedure Item', {
	qty: function (frm, cdt, cdn) {
		let d = locals[cdt][cdn];
		frappe.model.set_value(cdt, cdn, 'transfer_qty', d.qty * d.conversion_factor);
		console.log(d.qty, d.conversion_factor, d.transfer_qty);
	},

	uom: function (doc, cdt, cdn) {
		let d = locals[cdt][cdn];
		if (d.uom && d.item_code) {
			return frappe.call({
				method: 'erpnext.stock.doctype.stock_entry.stock_entry.get_uom_details',
				args: {
					item_code: d.item_code,
					uom: d.uom,
					qty: d.qty
				},
				callback: function (r) {
					if (r.message) {
						frappe.model.set_value(cdt, cdn, r.message);
					}
				}
			});
		}
	},

	item_code: function (frm, cdt, cdn) {
		let d = locals[cdt][cdn];
		if (d.item_code) {
			let args = {
				'item_code': d.item_code,
				'transfer_qty': d.transfer_qty,
				'quantity': d.qty
			};
			return frappe.call({
				method: 'healthcare.healthcare.doctype.therapy_type.therapy_type.get_item_details',
				args: { args: args },
				callback: function (r) {
					if (r.message) {
						let d = locals[cdt][cdn];
						$.each(r.message, function (k, v) {
							d[k] = v;
						});
						refresh_field('items');
					}
				}
			});
		}
	}
});