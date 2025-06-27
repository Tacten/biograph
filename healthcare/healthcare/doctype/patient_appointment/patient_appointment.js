// Copyright (c) 2016, ESS LLP and contributors
// For license information, please see license.txt
frappe.provide('erpnext.queries');
frappe.ui.form.on('Patient Appointment', {
	setup: function(frm) {
		frm.custom_make_buttons = {
			'Vital Signs': 'Vital Signs',
			'Patient Encounter': 'Patient Encounter'
		};
	},

	onload: function(frm) {
		if (frm.is_new()) {
			frm.set_value('appointment_time', null);
			frm.disable_save();
		}
		if(frm.doc.therapy_plan && frm.doc.__islocal){
			frm.set_value("appointment_type", "Therapy Session")
		}
	},

	refresh: function(frm) {
		if (frm.is_new()) {
            // Manually set the indicator to "Not Saved"
			frm.page.set_indicator(__("Not Saved"), "orange");
        }
		if(frm.doc.therapy_plan && frm.doc.__islocal){
			frm.set_value("appointment_type", "Therapy Session")
		}
		frm.set_query('patient', function() {
			return {
				filters: { 'status': 'Active' }
			};
		});

		frm.set_query("therapy_type", "therapy_types", function (doc, cdt, cdn) {
			let d = locals[cdt][cdn];
			return {
				query : "healthcare.healthcare.doctype.patient_appointment.patient_appointment.apply_filter_on_therapy_type",
				filters : {
					therapy_plan : doc.therapy_plan
				}
			};
		});

		frm.set_query('practitioner', function() {
			if (frm.doc.department) {
				return {
					filters: {
						'department': frm.doc.department
					}
				};
			}
		});

		frm.set_query('service_unit', function() {
			return {
				query: 'healthcare.controllers.queries.get_healthcare_service_units',
				filters: {
					company: frm.doc.company,
					inpatient_record: frm.doc.inpatient_record,
					allow_appointments: 1,
				}
			};
		});

		frm.set_query('therapy_plan', function() {
			return {
				filters: {
					'patient': frm.doc.patient
				}
			};
		});

		frm.set_query('service_request', function() {
			return {
				filters: {
					'patient': frm.doc.patient,
					'status': 'Active',
					'docstatus': 1,
					'template_dt': ['in', ['Clinical Procedure', 'Therapy Type']]
				}
			};
		});

		if (frm.is_new()) {
			frm.page.clear_primary_action();
			if (frm.doc.appointment_for) {
				frm.trigger('appointment_for');
			}
		} else {
			frm.page.set_primary_action(__('Save'), () => frm.save());
		}

		// Handle Unavailable appointment - this always returns early
		if (frm.doc.appointment_type === "Unavailable" && frm.doc.status !== "Cancelled") {
			frm.add_custom_button(__('Cancel Unavailability'), function() {
				update_status(frm, 'Cancelled');
			}).addClass("btn-danger");
			
			return; // Return early to not add other buttons for this status
		}
		
		// Handle Block Booking appointment - add custom cancel button but don't return early
		if (frm.doc.appointment_type === "Block Booking" && frm.doc.status !== "Cancelled") {
			frm.add_custom_button(__('Cancel'), function() {
				update_status(frm, 'Cancelled');
			});
		}

		if (frm.doc.patient) {
			frm.add_custom_button(__('Patient History'), function() {
				frappe.route_options = { 'patient': frm.doc.patient };
				frappe.set_route('patient_history');
			}, __('View'));
		}

		// Handle appointments with "Needs Rescheduling" status
		if (frm.doc.status === "Needs Rescheduling") {
			frm.add_custom_button(__('Reschedule'), function() {
				reschedule_appointment(frm);
			}).addClass("btn-primary");
			
			frm.add_custom_button(__('Cancel'), function() {
				update_status(frm, 'Cancelled');
			});
			
			return; // Return early to not add other buttons for this status
		}

		if (["Open", "Checked In", "Confirmed"].includes(frm.doc.status) || (frm.doc.status == "Scheduled" && !frm.doc.__islocal)) {
			frm.add_custom_button(__('Cancel'), function() {
				update_status(frm, 'Cancelled');
			});
			frm.add_custom_button(__('Reschedule'), function() {
				check_and_set_availability(frm);
			});

			if (frm.doc.procedure_template) {
				frm.add_custom_button(__('Clinical Procedure'), function() {
					frappe.model.open_mapped_doc({
						method: 'healthcare.healthcare.doctype.clinical_procedure.clinical_procedure.make_procedure',
						frm: frm,
					});
				}, __('Create'));
			} else if (frm.doc.therapy_type) {
				frm.add_custom_button(__('Therapy Session'), function() {
					frappe.model.open_mapped_doc({
						method: 'healthcare.healthcare.doctype.therapy_session.therapy_session.create_therapy_session',
						frm: frm,
					})
				}, 'Create');
			} else {
				frm.add_custom_button(__('Patient Encounter'), function() {
					frappe.model.open_mapped_doc({
						method: 'healthcare.healthcare.doctype.patient_appointment.patient_appointment.make_encounter',
						frm: frm,
					});
				}, __('Create'));
			}

			frm.add_custom_button(__('Vital Signs'), function() {
				create_vital_signs(frm);
			}, __('Create'));

			if (["Open", "Scheduled"].includes(frm.doc.status)) {
				frm.add_custom_button(__("Confirm"), function() {
					frm.set_value("status", "Confirmed");
					frm.save();
				}, __("Status"));
			}
		}

		if (!frm.doc.__islocal && ["Open", "Confirmed"].includes(frm.doc.status) && frm.doc.appointment_based_on_check_in) {
			frm.add_custom_button(__("Check In"), () => {
				frm.set_value("status", "Checked In");
				frm.save();
			});
		}

		frm.trigger("make_invoice_button");
		frm.trigger("validate_no_of_session");

	},
	validate_no_of_session:(frm)=>{
		if(frm.doc.appointment_type == "Therapy Session" && frm.doc.therapy_plan){
			frappe.call({
				method : "healthcare.healthcare.doctype.therapy_session.therapy_session.validate_no_of_session",
				args : {
					therapy_plan : frm.doc.therapy_plan
				},
				callback : (r) =>{
					if(r.message){
						frm.set_df_property("create_therapy_sessions", "hidden", 1);
					}
				}
			})
		}
	},
	make_invoice_button: function (frm) {
		// add button to invoice when show_payment_popup enabled
		if (!frm.is_new() && !frm.doc.invoiced && frm.doc.status != "Cancelled") {
			frappe.db.get_single_value("Healthcare Settings", "show_payment_popup").then(async val => {
				let fee_validity = (await frappe.call(
					"healthcare.healthcare.doctype.fee_validity.fee_validity.get_fee_validity",
					{ "appointment_name": frm.doc.name, "date": frm.doc.appointment_date , "ignore_status": true })).message;

				if (val && !fee_validity.length) {
					frm.add_custom_button(__("Make Payment"), function () {
						make_payment(frm, val);
					});
				}
			});
        }
	},

	appointment_for: function(frm) {
		if (frm.doc.appointment_for == 'Practitioner') {
			if (!frm.doc.practitioner) {
				frm.set_value('department', '');
			}
			frm.set_value('service_unit', '');
			frm.trigger('set_check_availability_action');
		} else if (frm.doc.appointment_for == 'Service Unit') {
			frm.set_value({
				'practitioner': '',
				'practitioner_name': '',
				'department': '',
			});
			frm.trigger('set_book_action');
		} else if (frm.doc.appointment_for == 'Department') {
			frm.set_value({
				'practitioner': '',
				'practitioner_name': '',
				'service_unit': '',
			});
			frm.trigger('set_book_action');
		} else {
			if (frm.doc.appointment_for == 'Department') {
				frm.set_value('service_unit', '');
			}
			frm.set_value({
				'practitioner': '',
				'practitioner_name': '',
				'department': '',
				'service_unit': '',
			});
			frm.page.clear_primary_action();
		}
	},

	set_book_action: function(frm) {
		frm.page.set_primary_action(__('Book'), async function() {
			frm.enable_save();
			await frm.save();
			if (!frm.is_new()) {
				await frappe.db.get_single_value("Healthcare Settings", "show_payment_popup").then(val => {
					frappe.call({
						method: "healthcare.healthcare.doctype.fee_validity.fee_validity.check_fee_validity",
						args: { "appointment": frm.doc },
						callback: (r) => {
							if (val && !r.message && !frm.doc.invoiced) {
								make_payment(frm, val);
							}
						}
					});
				});
			}
		});
	},

	set_check_availability_action: function(frm) {
		frm.page.set_primary_action(__('Check Availability'), function() {
			if (!frm.doc.patient) {
				frappe.utils.scroll_to(frm.get_field("patient").$wrapper, true, 30);
				frappe.msgprint({
					title: __('Not Allowed'),
					message: __('Please select Patient first'),
					indicator: 'red'
				});
			} else if ( !frm.doc.therapy_plan && frm.doc.appointment_type == "Therapy Session"){
				frappe.utils.scroll_to(frm.get_field("therapy_plan").$wrapper, true, 30);
				frappe.msgprint({
					title: __('Not Allowed'),
					message: __('Please select Therapy Plan first'),
					indicator: 'red'
				});
			} else {
				check_and_set_availability(frm);
			}
		});
	},

	patient: function(frm) {
		if (frm.doc.patient) {
			frm.trigger('toggle_payment_fields');
			frm.trigger('appointment_for');
			frappe.call({
				method: 'frappe.client.get',
				args: {
					doctype: 'Patient',
					name: frm.doc.patient
				},
				callback: function(data) {
					let age = null;
					if (data.message.dob) {
						age = calculate_age(data.message.dob);
					}
					frappe.model.set_value(frm.doctype, frm.docname, 'patient_age', age);
				}
			});
		} else {
			frm.set_value('patient_name', '');
			frm.set_value('patient_sex', '');
			frm.set_value('patient_age', '');
			frm.set_value('inpatient_record', '');
		}
	},

	practitioner: function(frm) {
		if (frm.doc.practitioner) {
			frm.events.set_payment_details(frm);
		}
	},

	appointment_type: function(frm) {
		if (frm.doc.appointment_type) {
			if (frm.doc.appointment_for && frm.doc[frappe.scrub(frm.doc.appointment_for)]) {
				frm.events.set_payment_details(frm);
			}
		}
	},

	department: function(frm) {
		if (frm.doc.department && frm.doc.appointment_for == 'Department') {
			frm.events.set_payment_details(frm);
		}
	},

	service_unit: function(frm) {
		if (frm.doc.service_unit && frm.doc.appointment_for == 'Service Unit') {
			frm.events.set_payment_details(frm);
		}
	},

	set_payment_details: function(frm) {
		frappe.db.get_single_value('Healthcare Settings', 'show_payment_popup').then(val => {
			if (val) {
				frappe.call({
					method: 'healthcare.healthcare.utils.get_appointment_billing_item_and_rate',
					args: {
						doc: frm.doc
					},
					callback: function(data) {
						if (data.message) {
							frappe.model.set_value(frm.doctype, frm.docname, 'paid_amount', data.message.practitioner_charge);
							frappe.model.set_value(frm.doctype, frm.docname, 'billing_item', data.message.service_item);
						}
					}
				});
			}
		});
	},

	therapy_plan: function(frm) {
		// Clear therapy types when therapy plan changes
		frm.set_value('therapy_types', []);
		
		// Auto-fetch therapy types when therapy plan is selected
		if (frm.doc.therapy_plan) {
			frm.call('get_therapy_types').then(r => {
				if(r.message == "Completed"){
					frm.set_value("therapy_plan", "")
					frappe.throw("Oops!.. Selected Therapy Plan is Completed")
				}
				if (r.message && r.message.length) {
					r.message.forEach(therapy => {
						let row = frappe.model.add_child(frm.doc, 'Patient Appointment Therapy', 'therapy_types');
						row.therapy_type = therapy.therapy_type;
						row.therapy_name = therapy.therapy_name;
						row.duration = therapy.duration;
						row.no_of_sessions = therapy.no_of_sessions;
					});
					
					frm.refresh_field('therapy_types');
					frappe.show_alert({
						message: __('Therapies for the plan {0} added successfully', [frm.doc.therapy_plan]),
						indicator: 'green'
					});
				}
			});
		}
		frm.trigger("validate_no_of_session");
		frm.set_query("therapy_type", "therapy_types", function (doc, cdt, cdn) {
			let d = locals[cdt][cdn];
			return {
				query : "healthcare.healthcare.doctype.patient_appointment.patient_appointment.apply_filter_on_therapy_type",
				filters : {
					therapy_plan : doc.therapy_plan
				}
			};
		});
	},


	therapy_type: function(frm) {
		if (frm.doc.therapy_type) {
			frappe.db.get_value('Therapy Type', frm.doc.therapy_type, 'default_duration', (r) => {
				if (r.default_duration) {
					frm.set_value('duration', r.default_duration)
				}
			});
		}
	},

	get_procedure_from_encounter: function(frm) {
		get_prescribed_procedure(frm);
	},

	toggle_payment_fields: function(frm) {
		frappe.call({
			method: 'healthcare.healthcare.doctype.patient_appointment.patient_appointment.check_payment_reqd',
			args: { 'patient': frm.doc.patient },
			callback: function(data) {
				if (data.message.fee_validity) {
					// if fee validity exists and show payment popup is enabled,
					// show payment fields as non-mandatory
					frm.toggle_display('mode_of_payment', 0);
					frm.toggle_display('paid_amount', 0);
					frm.toggle_display('billing_item', 0);
					frm.toggle_reqd('paid_amount', 0);
					frm.toggle_reqd('billing_item', 0);
				} else if (data.message) {
					frm.toggle_display('mode_of_payment', 1);
					frm.toggle_display('paid_amount', 1);
					frm.toggle_display('billing_item', 1);
					frm.toggle_reqd('paid_amount', 1);
					frm.toggle_reqd('billing_item', 1);
				} else {
					// if show payment popup is disabled, hide fields
					frm.toggle_display('mode_of_payment', data.message ? 1 : 0);
					frm.toggle_display('paid_amount', data.message ? 1 : 0);
					frm.toggle_display('billing_item', data.message ? 1 : 0);
					frm.toggle_reqd('paid_amount', data.message ? 1 : 0);
					frm.toggle_reqd('billing_item', data.message ? 1 : 0);
				}
			}
		});
	},

	// get_prescribed_therapies: function(frm) {
	// 	frappe.call({
	// 		method: "healthcare.healthcare.doctype.patient_appointment.patient_appointment.get_prescribed_therapies",
	// 		args: { patient: frm.doc.patient, therapy_plan : frm.doc.therapy_plan },
	// 		callback: function(r) {
	// 			if (r.message) {
	// 				frm.set_value("therapy_types", [])
	// 				r.message.forEach(e =>{
	// 					var s = frm.add_child('therapy_types');
	// 					s.therapy_type = e.therapy_type
	// 					s.duration = e.custom_default_duration
	// 				})
	// 				refresh_field('therapy_types');
	// 			} else {
	// 				frappe.msgprint({
	// 					title: __('Not Therapies Prescribed'),
	// 					message: __('There are no Therapies prescribed for Patient {0}', [frm.doc.patient.bold()]),
	// 					indicator: 'blue'
	// 				});
	// 			}
	// 		}
	// 	});	
	// },

	create_therapy_sessions: function(frm) {
		if (!frm.doc.therapy_types || !frm.doc.therapy_types.length) {
			frappe.msgprint(__('No therapy types selected'));
			return;
		}

		frappe.call({
			method: 'healthcare.healthcare.doctype.patient_appointment.patient_appointment.create_therapy_sessions',
			args: {
				appointment: frm.doc.name,
				therapy_types: frm.doc.therapy_types
			},
			freeze: true,
			freeze_message: __('Creating Therapy Sessions...'),
			callback: function(r) {
				if (r.message && r.message.length) {
					console.log(r.message)
					frappe.show_alert({
						message: __('Therapy Sessions created successfully'),
						indicator: 'green'
					});
					frm.reload_doc();
				}
			}
		});
	}
});

let check_and_set_availability = function(frm) {
	let selected_slot = null;
	let service_unit = null;
	let duration = null;
	let add_video_conferencing = null;
	let overlap_appointments = null;
	let appointment_based_on_check_in = false;
	let is_block_booking = false;
	let service_unit_values=[]

	show_availability();

	function show_empty_state(practitioner, appointment_date) {
		frappe.msgprint({
			title: __('Not Available'),
			message: __('Healthcare Practitioner {0} not available on {1}', [practitioner.bold(), appointment_date.bold()]),
			indicator: 'red'
		});
	}

	function show_availability() {
		let selected_practitioner = '';
		let d = new frappe.ui.Dialog({
			title: __('Available slots'),
			fields: [
				{ fieldtype: 'Link', options: 'Medical Department', reqd: 1, fieldname: 'department', label: 'Medical Department' },
				{ fieldtype: 'Column Break' },
				{ fieldtype: 'Link', options: 'Healthcare Practitioner', reqd: 1, fieldname: 'practitioner', label: 'Healthcare Practitioner' },
				{ fieldtype: 'Column Break' },
				{ fieldtype: 'Date', reqd: 1, fieldname: 'appointment_date', label: 'Date', min_date: new Date(frappe.datetime.get_today()) },
				{ fieldtype: 'Section Break' },
				{ 
					fieldtype: 'Check', 
					fieldname: 'block_booking', 
					label: 'Block Booking', 
					default: 0,
					description: __('Enable to book an appointment for a custom time block instead of predefined slots'),
					onchange: function() {
						is_block_booking = this.get_value();
						toggle_booking_type(d, is_block_booking);
					}
				},
				{ fieldtype: 'Section Break', fieldname: 'slots_section' },
				{ fieldtype: 'Link', options: 'Healthcare Service Unit', reqd: 0, hidden: 1, fieldname: 'service_unit', label: 'Service Unit' },
				{ 
					fieldtype: 'Time', 
					fieldname: 'from_time', 
					label: 'From Time', 
					reqd: 0,
					hidden: 1,
					default: '09:00:00',
					description: __('Start time of the block appointment') 
				},
				{ 
					fieldtype: 'Time', 
					fieldname: 'to_time', 
					label: 'To Time', 
					reqd: 0, 
					hidden: 1,
					default: '17:00:00',
					description: __('End time of the block appointment')
				},
				{ fieldtype: 'HTML', fieldname: 'available_slots' },
			],
			primary_action_label: __('Book'),
			primary_action: async function() {
				if (is_block_booking) {
					let values = d.get_values();
					frm.doc.service_unit=values.service_unit
					
					if (!values) return;
					
					if (values.from_time >= values.to_time) {
						frappe.throw(__("From Time must be before To Time"));
						return;
					}
					
					if (values.from_time && typeof values.from_time === 'string') {
						if (!values.from_time.includes(':')) {
							values.from_time = values.from_time + ":00";
						}
						if (values.from_time.split(':').length === 2) {
							values.from_time = values.from_time + ":00";
						}
					}
					
					if (values.to_time && typeof values.to_time === 'string') {
						if (!values.to_time.includes(':')) {
							values.to_time = values.to_time + ":00";
						}
						if (values.to_time.split(':').length === 2) {
							values.to_time = values.to_time + ":00";
						}
					}
					
					try {
						let from_datetime = frappe.datetime.str_to_obj(values.appointment_date + " " + values.from_time);
						let to_datetime = frappe.datetime.str_to_obj(values.appointment_date + " " + values.to_time);
						let duration_minutes = (to_datetime - from_datetime) / (1000 * 60);
						values.duration = duration_minutes;
					} catch (e) {
						console.error("Error calculating duration:", e);
					}
					const inputDateTime = new Date(values.appointment_date + " " + values.from_time);
					const now = new Date();
					if (inputDateTime < now) {
						frappe.throw("<b>Invalid time selection: Appointments cannot be scheduled for a past date and time.</b>")
					}
					frappe.show_alert({
						message: __("Checking for conflicts..."),
						indicator: "blue"
					});
					
					let formValues = {
						practitioner: values.practitioner,
						department: values.department,
						service_unit: values.service_unit,
						date: values.appointment_date,
						from_time: values.from_time,
						to_time: values.to_time,
						duration: values.duration
					};
					
					d.hide();
					
					frappe.call({
						method: "healthcare.healthcare.doctype.patient_appointment.patient_appointment.check_unavailability_conflicts",
						args: {
							filters: formValues
						},
						callback: function(r) {
							if (r.message && Array.isArray(r.message) && r.message.length > 0) {
								show_block_booking_conflict_dialog(formValues, r.message);
							} else {
								create_block_appointment(formValues, frm);
							}
						}
					});
				} else {
					frm.set_value('appointment_time', selected_slot);
					add_video_conferencing = add_video_conferencing && !d.$wrapper.find(".opt-out-check").is(":checked")
						&& !overlap_appointments

					frm.set_value('add_video_conferencing', add_video_conferencing);
					if (!frm.doc.duration) {
						frm.set_value('duration', duration);
					}
					let practitioner = frm.doc.practitioner;

					frm.set_value('practitioner', d.get_value('practitioner'));
					frm.set_value('department', d.get_value('department'));
					frm.set_value('appointment_date', d.get_value('appointment_date'));
					
					if (duration) {
						let start_time = moment(selected_slot, 'HH:mm:ss');
						
						let end_time = moment(start_time).add(duration, 'minutes');
						
						let end_time_str = end_time.format('HH:mm:ss');
						
						frm.set_value('end_time', end_time_str);
					}
					
					frm.set_value('appointment_based_on_check_in', appointment_based_on_check_in ? 1 : 0);

					if (service_unit) {
						frm.set_value('service_unit', service_unit);
					}
					
					if (frm.doc.status === 'Needs Rescheduling') {
						let appointment_date = moment(d.get_value('appointment_date'));
						let today = moment().startOf('day');
						
						if (appointment_date.isAfter(today)) {
							frm.set_value('status', 'Scheduled');
						} else if (appointment_date.isSame(today)) {
							frm.set_value('status', 'Open');
						}
					}

					d.hide();
					frm.enable_save();
					await frm.save();
					if (!frm.is_new() && (!practitioner || practitioner == d.get_value('practitioner'))) {
						await frappe.db.get_single_value("Healthcare Settings", "show_payment_popup").then(val => {
							frappe.call({
								method: "healthcare.healthcare.doctype.fee_validity.fee_validity.check_fee_validity",
								args: { "appointment": frm.doc },
								callback: (r) => {
									if (val && !r.message && !frm.doc.invoiced) {
										make_payment(frm, val);
									} else {
										frappe.call({
											method: "healthcare.healthcare.doctype.patient_appointment.patient_appointment.update_fee_validity",
											args: { "appointment": frm.doc }
										});
									}
								}
							});
						});
					}
					d.get_primary_btn().attr('disabled', true);
				}
			}
		});

		d.set_values({
			'department': frm.doc.department,
			'practitioner': frm.doc.practitioner,
			'appointment_date': frm.doc.appointment_date,
		});

		let selected_department = frm.doc.department;

		d.fields_dict['department'].df.onchange = () => {
			if (selected_department != d.get_value('department')) {
				d.set_values({
					'practitioner': ''
				});
				selected_department = d.get_value('department');
			}
			if (d.get_value('department')) {
				d.fields_dict.practitioner.get_query = function() {
					return {
						filters: {
							'department': selected_department
						}
					};
				};
			}
		};

		d.fields_dict.service_unit.get_query = function() {
			return {
				filters: {
					'name': ["in", service_unit_values]
				}
			};
		};

		d.get_primary_btn().attr('disabled', true);

		let fd = d.fields_dict;

		d.fields_dict['appointment_date'].df.onchange = () => {
			if (is_block_booking) {
				if (d.get_value('appointment_date') && d.get_value('from_time') && d.get_value('to_time') && 
				    d.get_value('from_time') < d.get_value('to_time')) {
					d.get_primary_btn().attr('disabled', null);
				}
			} else {
				show_slots(d, fd);
			}
		};
		
		d.fields_dict['from_time'].df.onchange = () => {
			if (is_block_booking && d.get_value('appointment_date') && 
			    d.get_value('from_time') && d.get_value('to_time') && 
			    d.get_value('from_time') < d.get_value('to_time')) {
				d.get_primary_btn().attr('disabled', null);
			}
		};
		
		d.fields_dict['to_time'].df.onchange = () => {
			if (is_block_booking && d.get_value('appointment_date') && 
			    d.get_value('from_time') && d.get_value('to_time') && 
			    d.get_value('from_time') < d.get_value('to_time')) {
				d.get_primary_btn().attr('disabled', null);
			}
			if((d.get_value('from_time') > d.get_value('to_time')) || (d.get_value('from_time') == d.get_value('to_time'))) {
				frappe.throw("<b>From Time must be before to time</b>")
			}
		};
		
		d.fields_dict['practitioner'].df.onchange = async () => {
			if (d.get_value('practitioner') && d.get_value('practitioner') != selected_practitioner) {
				selected_practitioner = d.get_value('practitioner');

				let r = await frappe.call({
					doc:frm.doc,
					method: "get_service_unit_values",
					args: {
						selected_practitioner
					}
				});
				service_unit_values = r.message;

				if (!is_block_booking) {
					show_slots(d, fd);
				} else if (d.get_value('appointment_date') && 
				    d.get_value('from_time') && d.get_value('to_time') && 
				    d.get_value('from_time') < d.get_value('to_time')) {
					d.get_primary_btn().attr('disabled', null);
				}
			}
		};

		d.show();
	}
	
	function toggle_booking_type(d, is_block) {
		if (is_block) {
			d.set_df_property('available_slots', 'hidden', 1);
			d.set_df_property('from_time', 'hidden', 0);
			d.set_df_property('to_time', 'hidden', 0);
			if(service_unit_values.length>1){
				d.set_df_property('service_unit', 'hidden', 0);
			}else{
				d.set_value("service_unit",service_unit_values[0])
			}
			d.set_df_property('from_time', 'reqd', 1);
			d.set_df_property('to_time', 'reqd', 1);
			d.set_df_property('service_unit', 'reqd', 1);
			
			selected_slot = null;
			
			d.set_title(__('Block Time Booking'));
			
			d.fields_dict.available_slots.$wrapper.html('');
			
			if (d.get_value('appointment_date') && d.get_value('practitioner') && 
			    d.get_value('from_time') && d.get_value('to_time') && 
			    d.get_value('from_time') < d.get_value('to_time')) {
				d.get_primary_btn().attr('disabled', null);
			} else {
				d.get_primary_btn().attr('disabled', true);
			}
		} else {
			d.set_df_property('available_slots', 'hidden', 0);
			d.set_df_property('from_time', 'hidden', 1);
			d.set_df_property('to_time', 'hidden', 1);
			d.set_df_property('service_unit', 'hidden', 1);
			d.set_df_property('from_time', 'reqd', 0);
			d.set_df_property('to_time', 'reqd', 0);
			d.set_df_property('service_unit', 'reqd', 0);
			
			d.set_title(__('Available slots'));
			
			if (d.get_value('practitioner') && d.get_value('appointment_date')) {
				show_slots(d, d.fields_dict);
			}
		}
	}
	
	function show_block_booking_conflict_dialog(values, conflicts) {
		let conflict_html = `<div class="conflicts-container">
			<div class="alert alert-danger">
				<strong>${__("Cannot book time block appointment!")}</strong> ${__("The following appointments conflict with the selected time:")}
			</div>
			<div class="conflict-list" style="max-height: 300px; overflow-y: auto;">
				<table class="table table-bordered">
					<thead>
						<tr>
							<th>${__("Patient")}</th>
							<th>${__("Time")}</th>
							<th>${__("Type")}</th>
							<th>${__("Status")}</th>
						</tr>
					</thead>
					<tbody>`;
		
		conflicts.forEach(function(conflict) {
			conflict_html += `<tr>
				<td>${conflict.patient_name || conflict.patient}</td>
				<td>${conflict.appointment_time}</td>
				<td>${conflict.appointment_type || ""}</td>
				<td>${conflict.status}</td>
			</tr>`;
		});
		
		conflict_html += `</tbody>
				</table>
			</div>
			<div class="alert alert-info mt-3">
				${__("Total conflicting appointments: ")} <strong>${conflicts.length}</strong>
			</div>
			<div class="alert alert-warning">
				<strong>${__("Important:")}</strong> ${__("You must cancel these appointments before booking a time block appointment for this time.")}
			</div>
		</div>`;
		
		let d = new frappe.ui.Dialog({
			title: __("Appointment Conflicts Detected"),
			fields: [
				{
					fieldtype: "HTML",
					fieldname: "conflicts_html",
					options: conflict_html
				}
			],
			primary_action_label: __("Go Back"),
			primary_action: function() {
				d.hide();
				check_and_set_availability(frm);
			}
		});
		
		d.show();
	}
	
	function create_block_appointment(values, frm) {
		// Check if patient is selected
		if (!frm.doc.patient) {
			frappe.msgprint({
				title: __('Patient Required'),
				message: __('Please select a patient before booking a block appointment'),
				indicator: 'red'
			});
			check_and_set_availability(frm); // Reopen the dialog
			return;
		}
		
		frappe.confirm(
			__("Are you sure you want to book this time block appointment?"),
			function() {
				// Calculate duration in minutes based on from and to time
				let from_time_obj = moment(values.from_time, 'HH:mm:ss');
				let to_time_obj = moment(values.to_time, 'HH:mm:ss');
				
				// Ensure to_time is after from_time
				if (to_time_obj.isBefore(from_time_obj)) {
					frappe.msgprint({
						title: __('Invalid Time Range'),
						message: __('End time must be after start time'),
						indicator: 'red'
					});
					return;
				}
				
				// Calculate duration in minutes
				let duration_minutes = to_time_obj.diff(from_time_obj, 'minutes');
				
				console.log("Block appointment details:", {
					from: values.from_time,
					to: values.to_time,
					duration: duration_minutes
				});
				
				// Set the form values from the block booking dialog
				frm.set_value('appointment_date', values.date);
				frm.set_value('appointment_time', values.from_time);
				frm.set_value('end_time', values.to_time);
				frm.set_value('duration', duration_minutes);
				
				// Ensure these fields are also set for completeness
				frm.set_value('end_time', values.to_time);
				
				// Set the appointment datetime for proper filtering
				let appointment_datetime = moment(values.date).format('YYYY-MM-DD') + ' ' + values.from_time;
				frm.set_value('appointment_datetime', appointment_datetime);
				
				// Set appointment end datetime 
				let appointment_end_datetime = moment(values.date).format('YYYY-MM-DD') + ' ' + values.to_time;
				frm.set_value('appointment_datetime', appointment_end_datetime);
				
				// Set practitioner/department
				frm.set_value('practitioner', values.practitioner);
				if (values.department) {
					frm.set_value('department', values.department);
				}
				
				// Calculate the status based on the appointment date
				let appointment_date = moment(values.date);
				let today = moment().startOf('day');
				
				if (appointment_date.isAfter(today)) {
					frm.set_value('status', 'Scheduled');
				} else if (appointment_date.isSame(today)) {
					frm.set_value('status', 'Open');
				}
				
				frm.enable_save();
				frm.save()
					.then(() => {
						// Add a reload to ensure UI is updated properly
						frm.reload_doc();
						
						frappe.show_alert({
							message: __("Time block appointment for {0} booked successfully from {1} to {2}", [
								frm.doc.patient_name, 
								moment(values.from_time, 'HH:mm:ss').format('hh:mm A'),
								moment(values.to_time, 'HH:mm:ss').format('hh:mm A')
							]),
							indicator: "green"
						}, 5);
						
						// Refresh any views if needed
						if (cur_list && cur_list.doctype === "Patient Appointment") {
							cur_list.refresh();
						}
					})
					.catch((err) => {
						console.error("Error saving block appointment:", err);
						frappe.msgprint({
							title: __('Error'),
							message: __('Failed to save block appointment. Please try again.'),
							indicator: 'red'
						});
					});
			}
		);
	}

	function show_slots(d, fd) {
		if (d.get_value('appointment_date') && d.get_value('practitioner')) {
			fd.available_slots.html('');
			frappe.call({
				method: 'healthcare.healthcare.doctype.patient_appointment.patient_appointment.get_availability_data',
				args: {
					practitioner: d.get_value('practitioner'),
					date: d.get_value('appointment_date'),
					appointment: frm.doc
				},
				callback: (r) => {
					let data = r.message;
					if (data.slot_details.length > 0) {
						let $wrapper = d.fields_dict.available_slots.$wrapper;

						let slot_html = get_slots(data.slot_details, data.fee_validity, d.get_value('appointment_date'));

						$wrapper
							.css('margin-bottom', 0)
							.addClass('text-center')
							.html(slot_html);

						$wrapper.on('click', 'button', function() {
							let $btn = $(this);
							$wrapper.find('button').removeClass('btn-outline-primary');
							$btn.addClass('btn-outline-primary');
							selected_slot = $btn.attr('data-name');
							service_unit = $btn.attr('data-service-unit');
							appointment_based_on_check_in = $btn.attr('data-day-appointment');
							duration = $btn.attr('data-duration');
							add_video_conferencing = parseInt($btn.attr('data-tele-conf'));
							overlap_appointments = parseInt($btn.attr('data-overlap-appointments'));
							if ($btn.attr('data-tele-conf') == 1) {
								if (d.$wrapper.find(".opt-out-conf-div").length) {
									d.$wrapper.find(".opt-out-conf-div").show();
								} else {
									overlap_appointments ?
										d.footer.prepend(
											`<div class="opt-out-conf-div ellipsis text-muted" style="vertical-align:text-bottom;">
												<label>
													<span class="label-area">
													${__("Video Conferencing disabled for group consultations")}
													</span>
												</label>
											</div>`
										)
									:
										d.footer.prepend(
											`<div class="opt-out-conf-div ellipsis" style="vertical-align:text-bottom;">
											<label>
												<input type="checkbox" class="opt-out-check"/>
												<span class="label-area">
												${__("Do not add Video Conferencing")}
												</span>
											</label>
										</div>`
										);
								}
							} else {
								d.$wrapper.find(".opt-out-conf-div").hide();
							}

							d.get_primary_btn().attr('disabled', null);
						});

					} else {
						show_empty_state(d.get_value('practitioner'), d.get_value('appointment_date'));
					}
				},
				freeze: true,
				freeze_message: __('Fetching Schedule...')
			});
		} else {
			fd.available_slots.html(__('Appointment date and Healthcare Practitioner are Mandatory').bold());
		}
	}

	function get_slots(slot_details, fee_validity, appointment_date) {
		let slot_html = '';
		let appointment_count = 0;
		let disabled = false;
		let start_str, slot_start_time, slot_end_time, interval, count, count_class, tool_tip, available_slots;

		slot_details.forEach((slot_info) => {
			slot_html += `<div class="slot-info">`;
			if (fee_validity && fee_validity != 'Disabled') {
				slot_html += `
					<span style="color:green">
					${__('Patient has fee validity till')} <b>${moment(fee_validity.valid_till).format('DD-MM-YYYY')}</b>
					</span><br>`;
			} else if (fee_validity != 'Disabled') {
				slot_html += `
					<span style="color:red">
					${__('Patient has no fee validity')}
					</span><br>`;
			}

			slot_html += `
				<span><b>
				${__('Practitioner Schedule: ')} </b> ${slot_info.slot_name}
					${slot_info.tele_conf && !slot_info.allow_overlap ? '<i class="fa fa-video-camera fa-1x" aria-hidden="true"></i>' : ''}
				</span><br>
				<span><b> ${__('Service Unit: ')} </b> ${slot_info.service_unit}</span>`;
				if (slot_info.service_unit_capacity) {
					slot_html += `<br><span> <b> ${__('Maximum Capacity:')} </b> ${slot_info.service_unit_capacity} </span>`;
				}

				slot_html += '</div><br>';

				slot_html += slot_info.avail_slot.map(slot => {
						appointment_count = 0;
						disabled = false;
						count_class = tool_tip = '';
						start_str = slot.from_time;
						slot_start_time = moment(slot.from_time, 'HH:mm:ss');
						slot_end_time = moment(slot.to_time, 'HH:mm:ss');
						interval = (slot_end_time - slot_start_time) / 60000 | 0;

						let now = moment();
						let booked_moment = "";
						if((now.format("YYYY-MM-DD") == appointment_date) && (slot_start_time.isBefore(now) && !slot.maximum_appointments)){
							disabled = true;
						} else {
							slot_info.appointments.forEach((booked) => {
								// Get the start time of the booked appointment
								booked_moment = moment(booked.appointment_time, 'HH:mm:ss');
								
								// Get the end time - either from explicit end_time or calculated from duration
								let end_time;
								if (booked.end_time) {
									// Use explicit end time if available (block appointments)
									end_time = moment(booked.end_time, 'HH:mm:ss');
								} else {
									// Otherwise calculate from duration
									end_time = booked_moment.clone().add(booked.duration, 'minutes');
								}

								// Special handling for Unavailable appointments
								if (booked.status === "Unavailable" && booked.appointment_type === "Unavailable") {
									if (slot_start_time.isBefore(end_time) && slot_end_time.isAfter(booked_moment)) {
										disabled = true;
										tool_tip = __("Practitioner unavailable at this time");
										return false;
									}
								}

								// Handle maximum appointments capacity
								if (slot.maximum_appointments) {
									if (booked.appointment_date == appointment_date) {
										appointment_count++;
									}
								}
								
								// Check if the slot time matches exactly with a booked appointment
								if (booked_moment.isSame(slot_start_time) || booked_moment.isBetween(slot_start_time, slot_end_time)) {
									if (booked.duration == 0) {
										disabled = true;
										return false;
									}
								}

								// Overlap checks
								if (slot_info.allow_overlap != 1) {
									// Check if the current slot overlaps with any booked appointment
									// This handles the case where a block appointment might span multiple slots
									let slot_overlaps_with_booked = (
										// Slot starts during the booked appointment
										(slot_start_time.isSameOrAfter(booked_moment) && slot_start_time.isBefore(end_time)) ||
										// Slot ends during the booked appointment
										(slot_end_time.isAfter(booked_moment) && slot_end_time.isSameOrBefore(end_time)) ||
										// Slot completely contains the booked appointment
										(slot_start_time.isSameOrBefore(booked_moment) && slot_end_time.isSameOrAfter(end_time))
									);
									
									if (slot_overlaps_with_booked) {
										disabled = true;
										return false;
									}
								} else {
									if (slot_start_time.isBefore(end_time) && slot_end_time.isAfter(booked_moment)) {
										appointment_count++;
									}
									if (appointment_count >= slot_info.service_unit_capacity) {
										disabled = true;
										return false;
									}
								}
							});
						}
						if (slot_info.allow_overlap == 1 && slot_info.service_unit_capacity > 1) {
							available_slots = slot_info.service_unit_capacity - appointment_count;
							count = `${(available_slots > 0 ? available_slots : __('Full'))}`;
							count_class = `${(available_slots > 0 ? 'badge-success' : 'badge-danger')}`;
							tool_tip =`${available_slots} ${__('slots available for booking')}`;
						}

						if (slot.maximum_appointments) {
							if (appointment_count >= slot.maximum_appointments) {
								disabled = true;
							}
							else {
								disabled = false;
							}
							available_slots = slot.maximum_appointments - appointment_count;
							count = `${(available_slots > 0 ? available_slots : __('Full'))}`;
							count_class = `${(available_slots > 0 ? 'badge-success' : 'badge-danger')}`;
							return `<button class="btn btn-secondary" data-name=${start_str}
								data-service-unit="${slot_info.service_unit || ''}"
								data-day-appointment=${1}
								data-duration=${slot.duration}
								${disabled ? 'disabled="disabled"' : ""}>${slot.from_time} -
								${slot.to_time} ${slot.maximum_appointments ?
								`<br><span class='badge ${count_class}'>${count} </span>` : ''}</button>`
						} else {

						return `
							<button class="btn btn-secondary" data-name=${start_str}
								data-duration=${interval}
								data-service-unit="${slot_info.service_unit || ''}"
								data-tele-conf="${slot_info.tele_conf || 0}"
								data-overlap-appointments="${slot_info.service_unit_capacity || 0}"
								style="margin: 0 10px 10px 0; width: auto;" ${disabled ? 'disabled="disabled"' : ""}
								data-toggle="tooltip" title="${tool_tip || ''}">
								${start_str.substring(0, start_str.length - 3)}
								${slot_info.service_unit_capacity ? `<br><span class='badge ${count_class}'> ${count} </span>` : ''}
							</button>`;

				}
			}).join("");
		});
		return slot_html;
	}
};

let get_prescribed_procedure = function(frm) {
	if (frm.doc.patient) {
		frappe.call({
			method: 'healthcare.healthcare.doctype.patient_appointment.patient_appointment.get_procedure_prescribed',
			args: { patient: frm.doc.patient },
			callback: function(r) {
				if (r.message && r.message.length) {
					show_procedure_templates(frm, r.message);
				} else {
					frappe.msgprint({
						title: __('Not Found'),
						message: __('No Prescribed Procedures found for the selected Patient')
					});
				}
			}
		});
	} else {
		frappe.msgprint({
			title: __('Not Allowed'),
			message: __('Please select a Patient first')
		});
	}
};

let show_procedure_templates = function(frm, result) {
	let d = new frappe.ui.Dialog({
		title: __('Prescribed Procedures'),
		fields: [
			{
				fieldtype: 'HTML', fieldname: 'procedure_template'
			}
		]
	});
	let html_field = d.fields_dict.procedure_template.$wrapper;
	html_field.empty();
	$.each(result, function(x, y) {
		let row = $(repl('<div class="col-xs-12" style="padding-top:12px; text-align:center;" >\
		<div class="col-xs-5"> %(encounter)s <br> %(consulting_practitioner)s <br> %(encounter_date)s </div>\
		<div class="col-xs-5"> %(procedure_template)s <br>%(practitioner)s  <br> %(date)s</div>\
		<div class="col-xs-2">\
		<a data-name="%(name)s" data-procedure-template="%(procedure_template)s"\
		data-encounter="%(encounter)s" data-practitioner="%(practitioner)s"\
		data-date="%(date)s"  data-department="%(department)s">\
		<button class="btn btn-default btn-xs">Add\
		</button></a></div></div><div class="col-xs-12"><hr/><div/>', {
			name: y[0], procedure_template: y[1],
			encounter: y[2], consulting_practitioner: y[3], encounter_date: y[4],
			practitioner: y[5] ? y[5] : '', date: y[6] ? y[6] : '', department: y[7] ? y[7] : ''
		})).appendTo(html_field);
		row.find("a").click(function() {
			frm.doc.procedure_template = $(this).attr('data-procedure-template');
			frm.doc.procedure_prescription = $(this).attr('data-name');
			frm.doc.practitioner = $(this).attr('data-practitioner');
			frm.doc.appointment_date = $(this).attr('data-date');
			frm.doc.department = $(this).attr('data-department');
			refresh_field('procedure_template');
			refresh_field('procedure_prescription');
			refresh_field('appointment_date');
			refresh_field('practitioner');
			refresh_field('department');
			d.hide();
			return false;
		});
	});
	if (!result) {
		let msg = __('There are no procedure prescribed for ') + frm.doc.patient;
		$(repl('<div class="col-xs-12" style="padding-top:20px;" >%(msg)s</div></div>', { msg: msg })).appendTo(html_field);
	}
	d.show();
};

let show_therapy_types = function(frm, result) {
	var d = new frappe.ui.Dialog({
		title: __('Prescribed Therapies'),
		fields: [
			{
				fieldtype: 'HTML', 
				fieldname: 'therapy_type',
				label: __('Select Therapies')
			}
		],
		primary_action_label: __('Add Selected Therapies'),
		primary_action: function() {
			let selected_therapies = [];
			$(d.fields_dict.therapy_type.$wrapper).find(':checkbox:checked').each(function() {
				let therapy_type = $(this).val();
				let therapy_plan = $(this).data('therapy-plan');
				let therapy_name = $(this).data('therapy-name');
				
				// Check if therapy is already selected
				let exists = false;
				if (frm.doc.therapy_types) {
					frm.doc.therapy_types.forEach(function(t) {
						if (t.therapy_type === therapy_type) {
							exists = true;
						}
					});
				}
				
				if (!exists) {
					let therapy = frappe.model.add_child(frm.doc, 'Patient Appointment Therapy', 'therapy_types');
					therapy.therapy_type = therapy_type;
					therapy.therapy_name = therapy_name;
				}
			});
			
			frm.refresh_field('therapy_types');
			d.hide();
		}
	});
	
	var html_field = d.fields_dict.therapy_type.$wrapper;
	html_field.empty();
	
	// Add "Select All" checkbox
	var select_all = $(`<div class="select-all" style="margin-bottom: 10px; font-weight: bold;">
		<input type="checkbox" id="select_all_therapies" style="margin-right: 5px;">
		<label for="select_all_therapies">${__('Select All')}</label>
	</div>`);
	
	select_all.find('#select_all_therapies').on('change', function() {
		var checked = $(this).prop('checked');
		html_field.find('.therapy-checkbox').prop('checked', checked);
	});
	
	html_field.append(select_all);
	
	// Add therapy types with checkboxes
	var table = $(`<table class="table table-bordered">
		<thead>
			<tr>
				<th style="width: 30px;"></th>
				<th>${__('Encounter')}</th>
				<th>${__('Therapy Type')}</th>
				<th>${__('Therapy Plan')}</th>
			</tr>
		</thead>
		<tbody></tbody>
	</table>`);
	
	html_field.append(table);
	
	$.each(result, function(x, y) {
		var row = $(`<tr>
			<td>
				<input type="checkbox" class="therapy-checkbox" value="${y[0]}" 
				data-therapy-plan="${y[5]}" data-therapy-name="${y[0]}">
			</td>
			<td>${y[2]} <br> ${y[3]} <br> ${y[4]}</td>
			<td>${y[0]}</td>
			<td>${y[5]}</td>
		</tr>`);
		
		table.find('tbody').append(row);
	});
	
	d.show();
};

let create_vital_signs = function(frm) {
	if (!frm.doc.patient) {
		frappe.throw(__('Please select patient'));
	}
	frappe.route_options = {
		'patient': frm.doc.patient,
		'appointment': frm.doc.name,
		'company': frm.doc.company
	};
	frappe.new_doc('Vital Signs');
};

let update_status = function(frm, status) {
	let doc = frm.doc;
	let msg = "";
	
	if (status === 'Cancelled') {
		if (doc.appointment_type === 'Unavailable') {
			msg = __('Are you sure you want to cancel this unavailability record?');
		} else if (doc.appointment_type === 'Block Booking') {
			msg = __('Are you sure you want to cancel this time block appointment?');
		} else {
			msg = __('Are you sure you want to cancel this appointment?');
		}
	} else {
		msg = __('Set Status to') + " " + status;
	}
	
	frappe.confirm(msg,
		function() {
			frappe.call({
				method: 'healthcare.healthcare.doctype.patient_appointment.patient_appointment.update_status',
				args: { appointment_id: doc.name, status: status },
				callback: function(data) {
					if (!data.exc) {
						frm.reload_doc();
					}
				}
			});
		}
	);
};

let calculate_age = function(birth) {
	let ageMS = Date.parse(Date()) - Date.parse(birth);
	let age = new Date();
	age.setTime(ageMS);
	let years =  age.getFullYear() - 1970;
	return `${years} ${__('Years(s)')} ${age.getMonth()} ${__('Month(s)')} ${age.getDate()} ${__('Day(s)')}`;
};

let make_payment = function (frm, automate_invoicing) {
	if (automate_invoicing) {
		make_registration (frm, automate_invoicing);
	}

	function make_registration (frm, automate_invoicing) {
		if (automate_invoicing == true && !frm.doc.paid_amount) {
			frappe.throw({
				title: __("Not Allowed"),
				message: __("Please set the Paid Amount first"),
			});
		}

		let is_block_booking = frm.doc.appointment_type === "Block Booking";
		let charge_label = is_block_booking ? "Time Block Appointment Charge" : "Consultation Charge";

		let fields = [
			{
				label: "Patient",
				fieldname: "patient",
				fieldtype: "Data",
				read_only: true,
			},
			{
				label: "Mode of Payment",
				fieldname: "mode_of_payment",
				fieldtype: "Link",
				options: "Mode of Payment",
				reqd: 1,
			},
			{
				fieldtype: "Column Break",
			},
			{
				label: charge_label,
				fieldname: "consultation_charge",
				fieldtype: "Currency",
				read_only: true,
			},
			{
				label: "Total Payable",
				fieldname: "total_payable",
				fieldtype: "Currency",
				read_only: true,
			},
			{
				label: __("Additional Discount"),
				fieldtype:"Section Break",
				collapsible: 1,
			},
			{
				label: "Discount Percentage",
				fieldname: "discount_percentage",
				fieldtype: "Percent",
				default: 0,
			},
			{
				fieldtype: "Column Break",
			},
			{
				label: "Discount Amount",
				fieldname: "discount_amount",
				fieldtype: "Currency",
				default: 0,
			}
		];

		if (frm.doc.appointment_for == "Practitioner") {
			let pract_dict = {
				label: "Practitioner",
				fieldname: "practitioner",
				fieldtype: "Data",
				read_only: true,
			};
			fields.splice(3, 0, pract_dict);
		} else if (frm.doc.appointment_for == "Service Unit") {
			let su_dict = {
				label: "Service Unit",
				fieldname: "service_unit",
				fieldtype: "Data",
				read_only: true,
			};
			fields.splice(3, 0, su_dict);
		} else if (frm.doc.appointment_for == "Department") {
			let dept_dict = {
				label: "Department",
				fieldname: "department",
				fieldtype: "Data",
				read_only: true,
			};
			fields.splice(3, 0, dept_dict);
		}

		if (automate_invoicing) {
			show_payment_dialog(frm, fields);
		}
	}

	function show_payment_dialog(frm, fields) {
		let d = new frappe.ui.Dialog({
			title: "Enter Payment Details",
			fields: fields,
			primary_action_label: "Create Invoice",
			primary_action: async function(values) {
				if (frm.is_dirty()) {
					await frm.save();
				}
				frappe.call({
					method: "healthcare.healthcare.doctype.patient_appointment.patient_appointment.invoice_appointment",
					args: {
						"appointment_name": frm.doc.name,
						"discount_percentage": values.discount_percentage,
						"discount_amount": values.discount_amount
					},
					callback: async function (data) {
						if (!data.exc) {
							await frm.reload_doc();
							if (frm.doc.ref_sales_invoice) {
								d.get_field("mode_of_payment").$input.prop("disabled", true);
								d.get_field("discount_percentage").$input.prop("disabled", true);
								d.get_field("discount_amount").$input.prop("disabled", true);
								d.get_primary_btn().attr("disabled", true);
								d.get_secondary_btn().attr("disabled", false);
							}
						}
					}
				});
			},
			secondary_action_label: __(`<svg class="icon  icon-sm" style="">
				<use class="" href="#icon-printer"></use>
			</svg>`),
			secondary_action() {
				window.open("/app/print/Sales Invoice/" + frm.doc.ref_sales_invoice, "_blank");
				d.hide();
			}
		});
		d.fields_dict["mode_of_payment"].df.onchange = () => {
			if (d.get_value("mode_of_payment")) {
				frm.set_value("mode_of_payment", d.get_value("mode_of_payment"));
			}
		};
		d.get_secondary_btn().attr("disabled", true);
		d.set_values({
			"patient": frm.doc.patient_name,
			"consultation_charge": frm.doc.paid_amount,
			"total_payable": frm.doc.paid_amount,
		});

		if (frm.doc.appointment_for == "Practitioner") {
			d.set_value("practitioner", frm.doc.practitioner_name);
		} else if (frm.doc.appointment_for == "Service Unit") {
			d.set_value("service_unit", frm.doc.service_unit);
		} else if (frm.doc.appointment_for == "Department") {
			d.set_value("department", frm.doc.department);
		}

		if (frm.doc.mode_of_payment) {
			d.set_value("mode_of_payment", frm.doc.mode_of_payment);
		}
		d.show();

		d.fields_dict["discount_percentage"].df.onchange = () => validate_discount("discount_percentage");
		d.fields_dict["discount_amount"].df.onchange = () => validate_discount("discount_amount");

		function validate_discount(field) {
			let message = "";
			let discount_percentage = d.get_value("discount_percentage");
			let discount_amount = d.get_value("discount_amount");
			let consultation_charge = d.get_value("consultation_charge");

			if (field === "discount_percentage") {
				if (discount_percentage > 100 || discount_percentage < 0) {
					d.get_primary_btn().attr("disabled", true);
					message = "Invalid discount percentage";
				} else {
					d.get_primary_btn().attr("disabled", false);
					frm.via_discount_percentage = true;
					if (discount_percentage && discount_amount) {
						d.set_value("discount_amount", 0);
					}
					discount_amount = consultation_charge * (discount_percentage / 100);

					d.set_values({
						"discount_amount": discount_amount,
						"total_payable": consultation_charge - discount_amount,
					}).then(() => delete frm.via_discount_percentage);
				}
			} else if (field === "discount_amount") {
				if (consultation_charge < discount_amount || discount_amount < 0) {
					d.get_primary_btn().attr("disabled", true);
					message = "Discount amount should not be more than Consultation Charge";
				} else {
					d.get_primary_btn().attr("disabled", false);
					if (!frm.via_discount_percentage) {
						discount_percentage = (discount_amount / consultation_charge) * 100;
						d.set_values({
							"discount_percentage": discount_percentage,
							"total_payable": consultation_charge - discount_amount,
						});
					}
				}
			}
			show_message(d, message, field);
		}
	}
};

let show_message = function(d, message, field) {
	var field = d.get_field(field);
	field.df.description = `<div style="color:red;
		padding:5px 5px 5px 5px">${message}</div>`
	field.refresh();
};

let reschedule_appointment = function(frm) {
	let original_status = frm.doc.status;
	let is_block_booking = frm.doc.appointment_type === "Block Booking";
	
	check_and_set_availability(frm);
	
	let after_save_handler = function() {
		if (frm.doc.status === "Needs Rescheduling") {
			let today = frappe.datetime.get_today();
			let status = today === frm.doc.appointment_date ? "Open" : "Scheduled";
			
			frappe.db.set_value("Patient Appointment", frm.doc.name, "status", status)
				.then(() => {
					frappe.show_alert({
						message: __("Appointment {0} has been rescheduled", [frm.doc.name]),
						indicator: "green"
					});
					frm.reload_doc();
				});
		} else if (is_block_booking) {
			// For block bookings, show confirmation
			frappe.show_alert({
				message: __("Time block appointment has been rescheduled"),
				indicator: "green"
			}, 5);
			
			// Ensure document is reloaded to reflect changes
			frm.reload_doc();
		}
		
		frm.off("after_save", after_save_handler);
	};
	
	frm.on("after_save", after_save_handler);
};
