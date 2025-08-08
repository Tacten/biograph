// Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Therapy Session', {
	setup: function(frm) {
		frm.get_field('exercises').grid.editable_fields = [
			{fieldname: 'exercise_type', columns: 7},
			{fieldname: 'counts_target', columns: 1},
			{fieldname: 'counts_completed', columns: 1},
			{fieldname: 'assistance_level', columns: 1}
		];

		frm.set_query('service_unit', function() {
			return {
				filters: {
					'is_group': false,
					'allow_appointments': true,
					'company': frm.doc.company
				}
			};
		});

		frm.set_query('appointment', function() {
			return {
				query: "healthcare.healthcare.doctype.therapy_session.therapy_session.get_appointment_query",
				filters: {
					therapy_type: frm.doc.therapy_type,
					therapy_plan: frm.doc.therapy_plan,
					is_new : frm.is_new(),
					name : frm.doc.name
				},
			};
		});

		frm.set_query('service_request', function() {
			return {
				filters: {
					'patient': frm.doc.patient,
					'status': 'Active',
					'docstatus': 1,
					'template_dt': 'Therapy Type'
				}
			};
		});

		frm.set_query('batch_no', 'items', function(doc, cdt, cdn) {
			let item = locals[cdt][cdn];
			if (!item.item_code) {
				frappe.throw(__('Please enter Item Code to get Batch Number'));
			} else {
				let filters = {'item_code': item.item_code};

				return {
					query : 'erpnext.controllers.queries.get_batch_no',
					filters: filters
				};
			}
		});
	},

	refresh: function(frm) {
		if (frm.doc.therapy_plan) {
			frm.trigger('filter_therapy_types');
		}
		if (frm.is_new() && frm.doc.therapy_plan) {
			frm.call({
				method : "validate_no_of_session",
				args : {
					therapy_plan : frm.doc.therapy_plan	
				},
				callback:(r)=>{
					if(r.message){
						console.log(r.message)
						frappe.throw(`Maximum number of sessions ${r.message[1]} already created for this Therapy Plan.`)
					}
				}
			})
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
		});

		if (!frm.doc.__islocal) {
			frm.dashboard.add_indicator(__('Counts Targeted: {0}', [frm.doc.total_counts_targeted]), 'blue');
			frm.dashboard.add_indicator(__('Counts Completed: {0}', [frm.doc.total_counts_completed]),
				(frm.doc.total_counts_completed < frm.doc.total_counts_targeted) ? 'orange' : 'green');

			frm.add_custom_button(__("Clinical Note"), function() {
				frappe.route_options = {
					"patient": frm.doc.patient,
					"reference_doc": "Therapy Session",
					"reference_name": frm.doc.name,
					"practitioner": frm.doc.practitioner
				}
				frappe.new_doc("Clinical Note");
			},__('Create'));
		}

		if (frm.doc.docstatus === 1) {
			frm.add_custom_button(__('Patient Assessment'), function() {
				frappe.model.open_mapped_doc({
					method: 'healthcare.healthcare.doctype.patient_assessment.patient_assessment.create_patient_assessment',
					frm: frm,
				})
			}, 'Create');

			frappe.db.get_value('Therapy Plan', {'name': frm.doc.therapy_plan}, 'therapy_plan_template', (r) => {
				if (r && !r.therapy_plan_template) {
					frm.add_custom_button(__('Sales Invoice'), function() {
						frappe.model.open_mapped_doc({
							method: 'healthcare.healthcare.doctype.therapy_session.therapy_session.invoice_therapy_session',
							frm: frm,
						});
					}, 'Create');
				}
			});
		}
		if (frm.doc.consume_stock) {
			frm.set_indicator_formatter('item_code',
				function(doc) { return (doc.qty<=doc.actual_qty) ? 'green' : 'orange' ; });
		}

		if (frm.doc.docstatus == 1 && frm.doc.items && frm.doc.items.length > 0){
			if(frm.doc.consumption_status=="Consumption Pending"){
				frm.add_custom_button(__('Start Consumption'), function() {
					frappe.call({
						doc: frm.doc,
						method: 'check_item_stock',
						callback: function(r) {
							if (!r.exc) {
								if (r.message == 'insufficient stock') {
									frappe.call({
										doc: frm.doc,
										method: "update_consumption_status",
										args: {
											status: "Insufficient Stock"
										},
										callback: function() {
											frm.reload_doc();
										}
									});
								} else {
									frm.trigger('consume_stocks');
								}
							}
						}
					});
				}).addClass("btn-primary");
			}
			if(frm.doc.consumption_status=="Insufficient Stock"){
				frm.add_custom_button(__('Add Stock'), function() {
					frm.trigger('make_material_receipt');
				}).addClass("btn-primary");
			}

		}

		frappe.after_ajax(() => {
			// Remove existing if already added
			const existing = document.querySelector('.custom-form-indicator');
			if (existing) existing.remove();

			if (frm.doc.docstatus === 1 && frm.doc.consumption_status && frm.doc.items?.length) {
				// Get the status pill
				const indicatorPill = document.querySelector('.title-area .indicator-pill');

				if (indicatorPill && indicatorPill.parentNode) {
					const pill = document.createElement('span');
					pill.className = 'indicator-pill no-indicator-dot custom-form-indicator';
					pill.style.marginLeft = '10px';
					pill.style.borderRadius = '3px';
					pill.style.padding = '3px 8px';
					pill.style.fontSize = '13px';
					pill.style.whiteSpace = 'nowrap';   // disables line wrapping

					if (frm.doc.consumption_status === 'Consumption Pending' || frm.doc.consumption_status === 'Insufficient Stock') {
						pill.style.backgroundColor = '#fff1e7ff';  // light orange background
						pill.style.color = '#bd3e0cff'; // dark orange text
					}else{
						pill.style.backgroundColor = '#dff0d8';  // light green background
						pill.style.color = '#3c763d'; // dark green text
					}

					pill.innerHTML = frm.doc.consumption_status;

					// Append next to the original indicator pill
					indicatorPill.parentNode.appendChild(pill);
				}
			}
		});

	},

	make_material_receipt: function(frm) {
		let msg = __('Stock quantity to start the Session is not available in the Warehouse {0}. Do you want to record a Stock Entry?', [frm.doc.warehouse.bold()]);
		frappe.confirm(
			msg,
			function() {
				frappe.call({
					doc: frm.doc,
					method: 'make_material_receipt',
					freeze: true,
					callback: function(r) {
						if (!r.exc) {
							frappe.call({
								doc: frm.doc,
								method: "update_consumption_status",
								args: {
									status: "Consumption Pending"
								},
								callback: function() {
									frm.reload_doc();
								}
							});
							frm.reload_doc();
							let doclist = frappe.model.sync(r.message);
							frappe.set_route('Form', doclist[0].doctype, doclist[0].name);
						}
					}
				});
			}
		);
	},

	consume_stocks: function(frm) {
		msg = __('Complete {0} and Consume Stock?', [frm.doc.name]);
		frappe.confirm(
			msg,
			function() {
				frappe.call({
					method: 'consume_stocks',
					doc: frm.doc,
					freeze: true,
					callback: function(r) {
						if (r.message) {
							frappe.show_alert({
								message: __('Stock Entry {0} created', ['<a class="bold" href="/app/stock-entry/'+ r.message + '">' + r.message + '</a>']),
								indicator: 'green'
							});
						}
						frm.reload_doc();
					}
				});
			}
		);
	},

	therapy_plan: function(frm) {
		if (frm.doc.therapy_plan) {
			frm.trigger('filter_therapy_types');
		}
	},

	filter_therapy_types: function(frm) {
		frappe.call({
			'method': 'frappe.client.get',
			args: {
				doctype: 'Therapy Plan',
				name: frm.doc.therapy_plan
			},
			callback: function(data) {
				let therapy_types = (data.message.therapy_plan_details || []).map(function(d){ return d.therapy_type; });
				frm.set_query('therapy_type', function() {
					return {
						filters: { 'therapy_type': ['in', therapy_types]}
					};
				});
			}
		});
	},

	patient: function(frm) {
		if (frm.doc.patient) {
			frappe.call({
				'method': 'healthcare.healthcare.doctype.patient.patient.get_patient_detail',
				args: {
					patient: frm.doc.patient
				},
				callback: function (data) {
					let age = '';
					if (data.message.dob) {
						age = calculate_age(data.message.dob);
					} else if (data.message.age) {
						age = data.message.age;
						if (data.message.age_as_on) {
							age = __('{0} as on {1}', [age, data.message.age_as_on]);
						}
					}
					frm.set_value('patient_age', age);
					frm.set_value('gender', data.message.sex);
					frm.set_value('patient_name', data.message.patient_name);
				}
			});
		} else {
			frm.set_value('patient_age', '');
			frm.set_value('gender', '');
			frm.set_value('patient_name', '');
		}
	},

	appointment: function(frm) {
		if (frm.doc.appointment) {
			frappe.call({
				'method': 'frappe.client.get',
				args: {
					doctype: 'Patient Appointment',
					name: frm.doc.appointment
				},
				callback: function(data) {
					let values = {
						'patient':data.message.patient,
						'practitioner': data.message.practitioner,
						'department': data.message.department,
						'start_date': data.message.appointment_date,
						'start_time': data.message.appointment_time,
						'service_unit': data.message.service_unit,
						'company': data.message.company,
						'duration': data.message.duration
					};
					frm.set_value(values);
				}
			});
		}
	},

	therapy_type: function(frm) {
		if (frm.doc.therapy_type) {
			frappe.call({
				'method': 'frappe.client.get',
				args: {
					doctype: 'Therapy Type',
					name: frm.doc.therapy_type
				},
				callback: function(data) {
					frm.set_value('duration', data.message.default_duration);
					frm.set_value('rate', data.message.rate);
					frm.set_value('service_unit', data.message.healthcare_service_unit);
					frm.set_value('department', data.message.medical_department);
					frm.set_value('consume_stock', data.message.consume_stock);
					frm.doc.exercises = [];
					frm.events.set_warehouse(frm);
					frm.events.set_therapy_consumables(frm);
					$.each(data.message.exercises, function(_i, e) {
						let exercise = frm.add_child('exercises');
						exercise.exercise_type = e.exercise_type;
						exercise.difficulty_level = e.difficulty_level;
						exercise.counts_target = e.counts_target;
						exercise.assistance_level = e.assistance_level;
					});
					frm.clear_table("codification_table")
					$.each(data.message.codification_table, function(k, val) {
						if (val.code_value) {
							let mcode = frm.add_child("codification_table");
							mcode.code_value = val.code_value
							mcode.code_system = val.code_system
							mcode.code = val.code
							mcode.description = val.description
							mcode.system = val.system
						}
					});
					refresh_field("codification_table");
					refresh_field('exercises');
				}
			});
		} else {
			frm.clear_table("codification_table")
			frm.refresh_field("codification_table");
		}
	},

	set_warehouse: function(frm) {
		if (!frm.doc.warehouse) {
			frappe.call({
				method: 'frappe.client.get_value',
				args: {
					doctype: 'Stock Settings',
					fieldname: 'default_warehouse'
				},
				callback: function (data) {
					frm.set_value('warehouse', data.message.default_warehouse);
				}
			});
		}
	},

	set_therapy_consumables: function(frm) {
		frappe.call({
			method: 'healthcare.healthcare.doctype.therapy_session.therapy_session.get_therapy_consumables',
			args: {
				therapy_type: frm.doc.therapy_type
			},
			callback: function(data) {
				if (data.message) {
					frm.doc.items = [];
					$.each(data.message, function(i, v) {
						let item = frm.add_child('items');
						item.item_code = v.item_code;
						item.item_name = v.item_name;
						item.uom = v.uom;
						item.stock_uom = v.stock_uom;
						item.qty = flt(v.qty);
						item.transfer_qty = v.transfer_qty;
						item.conversion_factor = v.conversion_factor;
						item.invoice_separately_as_consumables = v.invoice_separately_as_consumables;
						item.batch_no = v.batch_no;
					});
					refresh_field('items');
				}
			}
		});
	}
});

frappe.ui.form.on('Clinical Procedure Item', {
	qty: function(frm, cdt, cdn) {
		let d = locals[cdt][cdn];
		frappe.model.set_value(cdt, cdn, 'transfer_qty', d.qty*d.conversion_factor);
	},

	uom: function(doc, cdt, cdn) {
		let d = locals[cdt][cdn];
		if (d.uom && d.item_code) {
			return frappe.call({
				method: 'erpnext.stock.doctype.stock_entry.stock_entry.get_uom_details',
				args: {
					item_code: d.item_code,
					uom: d.uom,
					qty: d.qty
				},
				callback: function(r) {
					if (r.message) {
						frappe.model.set_value(cdt, cdn, r.message);
					}
				}
			});
		}
	},

	item_code: function(frm, cdt, cdn) {
		let d = locals[cdt][cdn];
		let args = null;
		if (d.item_code) {
			args = {
				'doctype' : 'Clinical Procedure',
				'item_code' : d.item_code,
				'company' : frm.doc.company,
				'warehouse': frm.doc.warehouse
			};
			return frappe.call({
				method: 'healthcare.healthcare.doctype.clinical_procedure_template.clinical_procedure_template.get_item_details',
				args: {args: args},
				callback: function(r) {
					if (r.message) {
						let d = locals[cdt][cdn];
						$.each(r.message, function(k, v) {
							d[k] = v;
						});
						refresh_field('items');
					}
				}
			});
		}
	}
});

let calculate_age = function(birth) {
	let ageMS = Date.parse(Date()) - Date.parse(birth);
	let age = new Date();
	age.setTime(ageMS);
	let years =  age.getFullYear() - 1970;
	return `${years} ${__('Years(s)')} ${age.getMonth()} ${__('Month(s)')} ${age.getDate()} ${__('Day(s)')}`;
};
