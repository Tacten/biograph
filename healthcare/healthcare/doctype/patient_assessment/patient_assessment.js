// Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Patient Assessment', {
	refresh: function(frm) {
		if (frm.doc.assessment_template) {
			frm.trigger('set_score_range');
		}

		if (!frm.doc.__islocal) {
			frm.trigger('show_patient_progress');
		}
		
		// Ensure field visibility is updated based on question types
		frm.refresh_field('assessment_sheet');
	},

	assessment_template: function(frm) {
		if (frm.doc.assessment_template) {
			// First clear existing items if any
			frm.clear_table("assessment_sheet");
			frm.refresh_field("assessment_sheet");
			
			// Get the template details
			frappe.call({
				method: 'frappe.client.get',
				args: {
					doctype: 'Patient Assessment Template',
					name: frm.doc.assessment_template
				},
				callback: function(data) {
					if (!data.message || !data.message.parameters || !data.message.parameters.length) {
						frappe.msgprint(__("Selected template has no parameters defined."));
						return;
					}

					// Set template related fields first
					frm.set_value('scale_min', data.message.scale_min);
					frm.set_value('scale_max', data.message.scale_max);
					frm.set_value('assessment_description', data.message.assessment_description);
					
					console.log("Template parameters:", data.message.parameters.length);
					
					// Add parameters to assessment sheet
					$.each(data.message.parameters, function(i, param) {
						let row = frm.add_child('assessment_sheet');
						row.parameter = param.assessment_parameter;
						
						// Pre-fetch question type if possible to avoid extra calls
						if (param.question_type) {
							row.question_type = param.question_type;
						}
					});
					
					frm.refresh_field('assessment_sheet');
					
					// Load parameter details from server to fill in question types and other data
					frm.call({
						method: 'load_parameter_details',
						doc: frm.doc,
						freeze: true,
						freeze_message: __("Loading assessment parameters..."),
						callback: function(r) {
							if (!r || r.exc) {
								console.error("Error loading parameter details:", r ? r.exc : "No response");
								frappe.msgprint(__("Error loading assessment parameters. Check console for details."));
								return;
							}
							
							console.log("Parameters loaded successfully");
							frm.refresh_field('assessment_sheet');
							frm.trigger('set_score_range');
							frm.trigger('customize_assessment_sheet');
							frm.trigger('setup_parameters_ui');
							frm.trigger('calculate_total_score');
						}
					});
				}
			});
		}
	},
	
	customize_assessment_sheet: function(frm) {
		// Make the grid more suitable for different question types
		setTimeout(function() {
			// Force the grid to render fully expanded rows for better input
			if (frm.fields_dict.assessment_sheet.grid.grid_rows) {
				frm.fields_dict.assessment_sheet.grid.grid_rows.forEach(row => {
					row.doc._collapsed = false;
					row.refresh();
				});
				
				// Add custom styling to make different input types more visible
				frm.fields_dict.assessment_sheet.grid.wrapper.find('.grid-body').css({
					'max-height': '500px',
					'overflow-y': 'auto'
				});
				
				frm.refresh_field('assessment_sheet');
			}
		}, 500);
	},
	
	setup_parameters_ui: function(frm) {
		// For each parameter in the sheet, set up field queries for options
		if (!frm.doc.assessment_sheet || !frm.doc.assessment_sheet.length) return;
		
		frm.doc.assessment_sheet.forEach((sheet_item, idx) => {
			// Set up options for single-select fields
			if (sheet_item.question_type === 'Single Select') {
				frm.fields_dict.assessment_sheet.grid.update_docfield_property(
					'selected_option', 'get_query', function() {
						return {
							filters: {
								'parent_parameter': sheet_item.parameter
							}
						};
					}
				);
			}
			
			// For multi-select fields, setup custom UI
			if (sheet_item.question_type === 'Multi Select') {
				// We'll handle multi-select manually with custom dialogs since we're using Small Text
				frm.fields_dict.assessment_sheet.grid.add_custom_button(
					__('Select Options'), 
					function() {
						// Only proceed if a row is selected
						if (!frm.fields_dict.assessment_sheet.grid.get_selected().length) {
							frappe.msgprint(__("Please select a row first"));
							return;
						}
						
						// Get the selected row
						const grid_row = frm.fields_dict.assessment_sheet.grid.get_selected()[0];
						const row = locals[grid_row.doctype][grid_row.name];
						
						// Only proceed if this is a multi-select question
						if (row.question_type !== 'Multi Select') {
							frappe.msgprint(__("This option is only for Multi Select questions"));
							return;
						}
						
						// Fetch options for this parameter
						frappe.call({
							method: 'healthcare.healthcare.doctype.patient_assessment_parameter.patient_assessment_parameter.get_parameter_options',
							args: {
								parameter: row.parameter
							},
							callback: function(r) {
								if (!r.message || !r.message.length) {
									frappe.msgprint(__("No options defined for this parameter"));
									return;
								}
								
								// Parse current selections from JSON string
								let selectedOptions = [];
								try {
									if (row.selected_options) {
										selectedOptions = JSON.parse(row.selected_options);
									}
								} catch (e) {
									console.error("Error parsing selected options:", e);
									selectedOptions = [];
								}
								
								// Build multiselect dialog
								let fields = [];
								r.message.forEach(option => {
									fields.push({
										label: option.option_text + " (Score: " + (option.score || 0) + ")",
										fieldname: option.name,
										fieldtype: 'Check',
										default: selectedOptions.includes(option.name)
									});
								});
								
								let d = new frappe.ui.Dialog({
									title: __('Select Options for {0}', [row.parameter]),
									fields: fields,
									primary_action_label: __('Save'),
									primary_action(values) {
										// Convert selected options to array
										let selected = [];
										Object.keys(values).forEach(key => {
											if (values[key]) {
												selected.push(key);
											}
										});
										
										// Update the row with JSON string of selections
										frappe.model.set_value(
											row.doctype, 
											row.name, 
											'selected_options', 
											JSON.stringify(selected)
										);
										
										frm.refresh_field('assessment_sheet');
										frm.trigger('calculate_total_score');
										d.hide();
									}
								});
								
								d.show();
							}
						});
					}
				);
			}
		});
	},

	set_score_range: function(frm) {
		let options = [''];
		for(let i = frm.doc.scale_min || 0; i <= (frm.doc.scale_max || 5); i++) {
			options.push(i);
		}
		frm.fields_dict.assessment_sheet.grid.update_docfield_property(
			'score', 'options', options
		);
	},

	calculate_total_score: function(frm) {
		let total_score = 0;
		let max_possible_score = 0;
		
		$.each(frm.doc.assessment_sheet || [], function(_i, item) {
			if (item.question_type === 'Numeric Scale' && item.score) {
				total_score += parseInt(item.score);
				// Get max score for this parameter
				max_possible_score += parseInt(item.max_score || 5); // Default to 5 if not specified
			} else if (item.question_type === 'Single Select' && item.selected_option) {
				// Get score for the selected option
				frappe.db.get_value('Patient Assessment Option', item.selected_option, 'score')
					.then(r => {
						if (r.message && r.message.score) {
							total_score += parseInt(r.message.score);
							frm.set_value('total_score_obtained', total_score);
						}
					});
				max_possible_score += 5; // Assuming max option score is 5
			} else if (item.question_type === 'Multi Select' && item.selected_options) {
				// Parse JSON and sum scores from multiple selected options
				try {
					let selected = JSON.parse(item.selected_options || '[]');
					if (selected.length) {
						selected.forEach(option_name => {
							frappe.db.get_value('Patient Assessment Option', option_name, 'score')
								.then(r => {
									if (r.message && r.message.score) {
										total_score += parseInt(r.message.score);
										frm.set_value('total_score_obtained', total_score);
									}
								});
						});
					}
				} catch (e) {
					console.error("Error parsing selected options:", e);
				}
				max_possible_score += 10; // Assuming max for multi-select is 10
			} else if (item.question_type === 'Yes/No' && item.is_yes) {
				total_score += 1;
				max_possible_score += 1;
			}
		});

		frm.set_value('total_score_obtained', total_score);
		frm.set_value('total_score', max_possible_score);
	},

	show_patient_progress: function(frm) {
		let bars = [];
		let message = '';
		let added_min = false;

		let title = __('{0} out of {1}', [frm.doc.total_score_obtained, frm.doc.total_score]);

		bars.push({
			'title': title,
			'width': (frm.doc.total_score_obtained / frm.doc.total_score * 100) + '%',
			'progress_class': 'progress-bar-success'
		});
		if (bars[0].width == '0%') {
			bars[0].width = '0.5%';
			added_min = 0.5;
		}
		message = title;
		frm.dashboard.add_progress(__('Status'), bars, message);
	},
});

frappe.ui.form.on('Patient Assessment Sheet', {
	score: function(frm, cdt, cdn) {
		frm.events.calculate_total_score(frm);
	},
	
	selected_option: function(frm, cdt, cdn) {
		frm.events.calculate_total_score(frm);
	},
	
	selected_options: function(frm, cdt, cdn) {
		frm.events.calculate_total_score(frm);
	},
	
	answer_text: function(frm, cdt, cdn) {
		// Text answers don't affect score
	},
	
	is_yes: function(frm, cdt, cdn) {
		frm.events.calculate_total_score(frm);
	},
	
	parameter: function(frm, cdt, cdn) {
		// When parameter is changed, update the question type
		let row = locals[cdt][cdn];
		if (row.parameter) {
			frappe.db.get_value('Patient Assessment Parameter', row.parameter, 
				['question_type', 'max_score'], function(r) {
					if (r.message) {
						frappe.model.set_value(cdt, cdn, 'question_type', r.message.question_type);
						
						// For numeric scale, set max score
						if (r.message.question_type === 'Numeric Scale') {
							frappe.model.set_value(cdt, cdn, 'max_score', r.message.max_score || 5);
						}
						
						// Clear any previously selected options when parameter changes
						if (r.message.question_type === 'Multi Select') {
							frappe.model.set_value(cdt, cdn, 'selected_options', '[]');
						} else if (r.message.question_type === 'Single Select') {
							frappe.model.set_value(cdt, cdn, 'selected_option', '');
						}
						
						frm.refresh_field('assessment_sheet');
					}
				});
		}
	}
});
