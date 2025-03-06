// Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Questionnaire Response', {
    refresh: function(frm) {
        if (frm.is_new()) {
            frm.set_value('authored_on', frappe.datetime.now_datetime());
            frm.set_value('author', frappe.session.user);
        }
        
        // Render the dynamic form based on the questionnaire template
        if (frm.doc.questionnaire) {
            render_dynamic_form(frm);
        }
        
        // Add button to mark as completed
        if (frm.doc.status === "in-progress" && !frm.is_new()) {
            frm.add_custom_button(__('Mark as Completed'), function() {
                frm.set_value('status', 'completed');
                frm.save();
            }).addClass('btn-primary');
        }
        
        // Add button to create from encounter
        if (frm.is_new()) {
            frm.add_custom_button(__('Create from Encounter'), function() {
                select_encounter(frm);
            });
        }
        
        // Add button to export as FHIR
        if (!frm.is_new()) {
            frm.add_custom_button(__('Export as FHIR'), function() {
                frappe.call({
                    method: "to_fhir",
                    doc: frm.doc,
                    callback: function(r) {
                        if (r.message) {
                            show_fhir_data(r.message);
                        }
                    }
                });
            });
        }
    },
    
    questionnaire: function(frm) {
        if (frm.doc.questionnaire) {
            // Clear existing items
            frm.clear_table('items');
            frm.refresh_field('items');
            
            // Fetch questions from the template and populate the items table
            frappe.call({
                method: 'healthcare.healthcare.doctype.questionnaire_response.questionnaire_response.get_questionnaire_items',
                args: {
                    questionnaire: frm.doc.questionnaire
                },
                callback: function(r) {
                    if (r.message) {
                        r.message.forEach(item => {
                            let row = frm.add_child('items');
                            row.question = item.name;
                            row.linkId = item.linkId;
                            row.text = item.text;
                            row.type = item.type;
                        });
                        frm.refresh_field('items');
                        render_dynamic_form(frm);
                    }
                }
            });
        }
    }
});

// Function to render the dynamic form
function render_dynamic_form(frm) {
    // Create a custom section for the questionnaire
    if (!frm.dynamic_form_area) {
        frm.dynamic_form_area = $('<div class="dynamic-form-area">').appendTo(frm.fields_dict.items.wrapper);
    }
    frm.dynamic_form_area.empty();
    
    // Create a map of questions with their conditional logic
    let conditional_questions = {};
    let all_questions = {};
    
    // First collect question details without making synchronous calls
    let promises = [];
    
    (frm.doc.items || []).forEach(item => {
        all_questions[item.question] = item;
        
        // Use async calls and collect promises
        let promise = new Promise((resolve) => {
            frappe.call({
                method: 'frappe.client.get',
                args: {
                    doctype: 'Questionnaire Item',
                    name: item.question
                },
                callback: function(r) {
                    if (r.message && r.message.has_condition) {
                        conditional_questions[item.question] = {
                            condition_question: r.message.condition_question,
                            condition_operator: r.message.condition_operator,
                            condition_value: r.message.condition_value
                        };
                    }
                    resolve();
                },
                error: function(err) {
                    console.error("Error fetching question details:", err);
                    // Resolve anyway to not block rendering
                    resolve();
                }
            });
        });
        
        promises.push(promise);
    });
    
    // Wait for all question details to be fetched
    Promise.all(promises).then(() => {
        // Create groups for organization
        let groups = {};
        let section = $('<div class="form-section">').appendTo(frm.dynamic_form_area);
        
        // Render each question
        (frm.doc.items || []).forEach(item => {
            try {
                // Skip items of type 'group' - they're used for organization
                if (item.type === 'group') {
                    if (groups[item.linkId]) {
                        section = groups[item.linkId];
                    } else {
                        // Create a new section for this group
                        let groupSection = $('<div class="form-section">')
                            .appendTo(frm.dynamic_form_area);
                        
                        $('<h4>').text(item.text).appendTo(groupSection);
                        groups[item.linkId] = groupSection;
                        section = groupSection;
                    }
                    return;
                }
                
                // Create a form field container
                let field_container = $('<div class="form-group frappe-control">').appendTo(section);
                
                // Check if this question is conditional
                if (conditional_questions[item.question]) {
                    field_container.attr('data-depends-on-question', conditional_questions[item.question].condition_question);
                    field_container.attr('data-depends-on-operator', conditional_questions[item.question].condition_operator);
                    field_container.attr('data-depends-on-value', conditional_questions[item.question].condition_value);
                    
                    // Initially hide the field
                    field_container.hide();
                }
                
                // Add label
                let required = item.required ? '<span class="text-danger">*</span>' : '';
                $('<div class="control-label">').html(`${item.text} ${required}`).appendTo(field_container);
                
                // Create input based on type
                let input;
                let answer_field;
                
                switch(item.type) {
                    case 'boolean':
                        input = $('<div class="checkbox"><label><input type="checkbox"> Yes</label></div>');
                        answer_field = 'answer_boolean';
                        // Set the value if it already exists
                        if (item[answer_field] !== undefined) {
                            input.find('input').prop('checked', item[answer_field]);
                        }
                        input.find('input').on('change', function() {
                            frm.doc.items.forEach(doc_item => {
                                if (doc_item.name === item.name) {
                                    frappe.model.set_value(doc_item.doctype, doc_item.name, answer_field, this.checked);
                                    
                                    // Check for dependent questions
                                    update_dependent_questions(frm, item.linkId, this.checked);
                                }
                            });
                        });
                        break;
                    
                    case 'choice':
                    case 'open-choice':
                        // For choices, use a simpler approach to avoid permission issues
                        input = $('<select class="form-control">');
                        answer_field = 'answer_choice';
                        
                        // Add blank option
                        $('<option value="">').text('').appendTo(input);
                        
                        // Check if we've cached the field_options
                        if (item.cached_field_options) {
                            renderChoiceOptions(input, item, answer_field, frm);
                        } else {
                            // Fetch options safely
                            frappe.call({
                                method: 'frappe.desk.reportview.get',
                                args: {
                                    doctype: 'Questionnaire Item',
                                    fields: ['field_options'],
                                    filters: [['name', '=', item.question]]
                                },
                                callback: function(r) {
                                    if (r.message && r.message.values && r.message.values.length) {
                                        let field_options = r.message.values[0][0];
                                        item.cached_field_options = field_options;
                                        renderChoiceOptions(input, item, answer_field, frm);
                                    }
                                }
                            });
                        }
                        break;
                    
                    case 'string':
                    case 'url':
                        input = $('<input type="text" class="form-control">');
                        answer_field = item.type === 'string' ? 'answer_string' : 'answer_url';
                        
                        // Set the value if it already exists
                        if (item[answer_field]) {
                            input.val(item[answer_field]);
                        }
                        
                        input.on('change', function() {
                            frm.doc.items.forEach(doc_item => {
                                if (doc_item.name === item.name) {
                                    frappe.model.set_value(doc_item.doctype, doc_item.name, answer_field, this.value);
                                    
                                    // Check for dependent questions
                                    update_dependent_questions(frm, item.linkId, this.value);
                                }
                            });
                        });
                        break;
                    
                    case 'text':
                        input = $('<textarea class="form-control" rows="3"></textarea>');
                        answer_field = 'answer_text';
                        
                        // Set the value if it already exists
                        if (item[answer_field]) {
                            input.val(item[answer_field]);
                        }
                        
                        input.on('change', function() {
                            frm.doc.items.forEach(doc_item => {
                                if (doc_item.name === item.name) {
                                    frappe.model.set_value(doc_item.doctype, doc_item.name, answer_field, this.value);
                                }
                            });
                        });
                        break;
                    
                    case 'integer':
                    case 'decimal':
                        input = $('<input type="number" class="form-control">');
                        if (item.type === 'decimal') {
                            input.attr('step', '0.01');
                        }
                        answer_field = item.type === 'integer' ? 'answer_integer' : 'answer_decimal';
                        
                        // Set the value if it already exists
                        if (item[answer_field] !== undefined) {
                            input.val(item[answer_field]);
                        }
                        
                        input.on('change', function() {
                            let value = item.type === 'integer' ? parseInt(this.value) : parseFloat(this.value);
                            frm.doc.items.forEach(doc_item => {
                                if (doc_item.name === item.name) {
                                    frappe.model.set_value(doc_item.doctype, doc_item.name, answer_field, value);
                                    
                                    // Check for dependent questions
                                    update_dependent_questions(frm, item.linkId, value);
                                }
                            });
                        });
                        break;
                    
                    case 'date':
                    case 'dateTime':
                        let field_class = item.type === 'date' ? 'datepicker' : 'datetimepicker';
                        input = $(`<div class="form-group frappe-control"><div class="control-input-wrapper"><div class="${field_class} date-picker"></div></div></div>`);
                        answer_field = item.type === 'date' ? 'answer_date' : 'answer_datetime';
                        
                        // Initialize datepicker after rendering
                        setTimeout(() => {
                            let datepicker = input.find(`.${field_class}`).datepicker({
                                dateFormat: item.type === 'date' ? 'yy-mm-dd' : 'yy-mm-dd HH:ii:ss',
                                onSelect: function(dateText) {
                                    frm.doc.items.forEach(doc_item => {
                                        if (doc_item.name === item.name) {
                                            frappe.model.set_value(doc_item.doctype, doc_item.name, answer_field, dateText);
                                            
                                            // Check for dependent questions
                                            update_dependent_questions(frm, item.linkId, dateText);
                                        }
                                    });
                                }
                            });
                            
                            // Set the value if it already exists
                            if (item[answer_field]) {
                                datepicker.datepicker('setDate', item[answer_field]);
                            }
                        }, 100);
                        break;
                    
                    case 'attachment':
                        // For simplicity, just provide a link to the regular attachment field
                        input = $('<div>').html(`<p>Please use the regular attachment field for question "${item.text}" in the table below.</p>`);
                        break;
                    
                    case 'display':
                        // Just display text, no input
                        input = $('<div class="form-display-text">').html(item.text);
                        break;
                    
                    default:
                        input = $('<input type="text" class="form-control" disabled>').val('Unsupported type: ' + item.type);
                }
                
                // Add input to container
                $('<div class="control-input-wrapper">').append(input).appendTo(field_container);
                
                // Add help text if available - use a safer approach
                fetchHelpText(item.question, field_container);
                
            } catch (error) {
                console.error("Error rendering question:", error, item);
                // Continue with other questions
            }
        });
        
        // After rendering all fields, check conditions for visibility
        update_all_conditional_fields(frm);
    });
}

// Helper function to render choice options
function renderChoiceOptions(input, item, answer_field, frm) {
    if (!item.cached_field_options) return;
    
    let options = item.cached_field_options.split('\n');
    
    // Add each option
    options.forEach(opt => {
        let value = opt;
        let text = opt;
        
        // If it's a coded option (code: text)
        if (opt.includes(':')) {
            let parts = opt.split(':');
            value = parts[0].trim();
            text = parts[1].trim();
        }
        
        $('<option>').attr('value', opt).text(text).appendTo(input);
    });
    
    // Set the value if it already exists
    if (item[answer_field]) {
        input.val(item[answer_field]);
    }
    
    input.on('change', function() {
        frm.doc.items.forEach(doc_item => {
            if (doc_item.name === item.name) {
                frappe.model.set_value(doc_item.doctype, doc_item.name, answer_field, this.value);
                
                // Check for dependent questions
                update_dependent_questions(frm, item.linkId, this.value);
            }
        });
    });
}

// Helper function to fetch help text safely
function fetchHelpText(question_name, container) {
    frappe.call({
        method: 'frappe.desk.reportview.get',
        args: {
            doctype: 'Questionnaire Item',
            fields: ['help_text'],
            filters: [['name', '=', question_name]]
        },
        callback: function(r) {
            if (r.message && r.message.values && r.message.values.length) {
                let help_text = r.message.values[0][0];
                if (help_text) {
                    $('<div class="help-box small text-muted">').text(help_text).appendTo(container);
                }
            }
        }
    });
}

// Function to update dependent questions based on answers
function update_dependent_questions(frm, question_linkId, value) {
    frm.dynamic_form_area.find(`[data-depends-on-question="${question_linkId}"]`).each(function() {
        let field = $(this);
        let operator = field.attr('data-depends-on-operator');
        let expected = field.attr('data-depends-on-value');
        
        let show = false;
        
        // Evaluate condition
        switch(operator) {
            case 'exists':
                show = value !== null && value !== undefined && value !== '';
                break;
            case 'equals':
                show = value == expected; // Intentionally using == for loose comparison
                break;
            case 'not-equals':
                show = value != expected; // Intentionally using != for loose comparison
                break;
            case 'greater-than':
                show = parseFloat(value) > parseFloat(expected);
                break;
            case 'less-than':
                show = parseFloat(value) < parseFloat(expected);
                break;
            default:
                show = false;
        }
        
        // Show or hide based on condition
        if (show) {
            field.show();
        } else {
            field.hide();
        }
    });
}

// Update all conditional fields at once
function update_all_conditional_fields(frm) {
    (frm.doc.items || []).forEach(item => {
        if (item.answer_boolean !== undefined) {
            update_dependent_questions(frm, item.linkId, item.answer_boolean);
        } else if (item.answer_string) {
            update_dependent_questions(frm, item.linkId, item.answer_string);
        } else if (item.answer_choice) {
            update_dependent_questions(frm, item.linkId, item.answer_choice);
        } else if (item.answer_integer !== undefined) {
            update_dependent_questions(frm, item.linkId, item.answer_integer);
        } else if (item.answer_decimal !== undefined) {
            update_dependent_questions(frm, item.linkId, item.answer_decimal);
        } else if (item.answer_date) {
            update_dependent_questions(frm, item.linkId, item.answer_date);
        } else if (item.answer_datetime) {
            update_dependent_questions(frm, item.linkId, item.answer_datetime);
        }
    });
}

// Function to select a patient encounter
function select_encounter(frm) {
    frappe.prompt([
        {
            label: __('Patient Encounter'),
            fieldname: 'encounter',
            fieldtype: 'Link',
            options: 'Patient Encounter',
            reqd: 1,
            get_query: () => {
                return {
                    filters: {
                        docstatus: ['<', 2]
                    }
                };
            }
        },
        {
            label: __('Questionnaire Template'),
            fieldname: 'questionnaire',
            fieldtype: 'Link',
            options: 'Healthcare Questionnaire Template',
            reqd: 1
        }
    ], function(values) {
        frappe.call({
            method: 'healthcare.healthcare.doctype.questionnaire_response.questionnaire_response.create_from_encounter',
            args: {
                encounter: values.encounter,
                questionnaire: values.questionnaire
            },
            callback: function(r) {
                if (r.message) {
                    var doc = frappe.model.sync(r.message)[0];
                    frappe.set_route("Form", doc.doctype, doc.name);
                }
            }
        });
    }, __('Select Encounter and Questionnaire'), __('Create'));
}

// Show FHIR data in a dialog
function show_fhir_data(data) {
    let d = new frappe.ui.Dialog({
        title: __('FHIR QuestionnaireResponse'),
        fields: [
            {
                fieldname: 'fhir_json',
                fieldtype: 'Code',
                options: 'JSON',
                label: __('FHIR JSON'),
                read_only: 1
            }
        ],
        primary_action_label: __('Copy to Clipboard'),
        primary_action: function() {
            frappe.utils.copy_to_clipboard(JSON.stringify(data, null, 2));
            frappe.show_alert({
                message: __('Copied to clipboard'),
                indicator: 'green'
            });
        }
    });
    
    d.set_value('fhir_json', JSON.stringify(data, null, 2));
    d.show();
} 