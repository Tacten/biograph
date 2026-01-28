// Copyright (c) 2016, ESS LLP and contributors
// For license information, please see license.txt
{% include 'healthcare/regional/india/abdm/js/patient.js' %}

frappe.ui.form.on('Patient', {
	refresh: function (frm) {
		frm.set_query('patient', 'patient_relation', function () {
			return {
				filters: [
					['Patient', 'name', '!=', frm.doc.name]
				]
			};
		});
		frm.set_query('customer_group', {'is_group': 0});
		frm.set_query('default_price_list', { 'selling': 1});

		if (frappe.defaults.get_default('patient_name_by') != 'Naming Series') {
			frm.toggle_display('naming_series', false);
		} else {
			erpnext.toggle_naming_series();
		}

		if (frappe.defaults.get_default('collect_registration_fee') && frm.doc.status == 'Disabled') {
			frm.add_custom_button(__('Invoice Patient Registration'), function () {
				invoice_registration(frm);
			});
		}

		if (frm.doc.patient_name && frappe.user.has_role('Physician')) {
			frm.add_custom_button(__('Patient Progress'), function() {
				frappe.route_options = {'patient': frm.doc.name};
				frappe.set_route('patient-progress');
			}, __('View'));

			frm.add_custom_button(__('Patient History'), function() {
				frappe.route_options = {'patient': frm.doc.name};
				frappe.set_route('patient_history');
			}, __('View'));
		}

		frappe.dynamic_link = {doc: frm.doc, fieldname: 'name', doctype: 'Patient'};
		frm.toggle_display(['address_html', 'contact_html'], !frm.is_new());

		if (!frm.is_new()) {
			if ((frappe.user.has_role('Nursing User') || frappe.user.has_role('Physician'))) {
				frm.add_custom_button(__('Medical Record'), function () {
					create_medical_record(frm);
				}, __('Create'));
				frm.toggle_enable(['customer'], 0);
			}
			frappe.contacts.render_address_and_contact(frm);
			erpnext.utils.set_party_dashboard_indicators(frm);
		} else {
			frappe.contacts.clear_address_and_contact(frm);
		}
	},

	onload: function (frm) {
		if (frm.doc.dob) {
			$(frm.fields_dict['age_html'].wrapper).html(`${__('AGE')} : ${get_age(frm.doc.dob)}`);
		} else {
			$(frm.fields_dict['age_html'].wrapper).html('');
		}
	},
	validate:(frm)=>{
		if(frm.is_dirty()){
			let missing = []
			cur_frm.fields.forEach(r=>{ 
				if(r.df.reqd && !frm.doc[r.df.fieldname] && !r.df.hidden){
					missing.push(r.df.label)
				}
			})
			message = __("Mandatory fields required in {0}", [__(frm.doc.doctype)]);

			message = message + "<br><br><ul><li>" + missing.join("</li><li>") + "</ul>";
			console.log(missing)
			if (missing.length){
				frappe.throw({
					message: message,
					indicator: "red",
					title: __("Missing Fields"),
				});
			}
		}
	},
	before_save: function(frm) {
		// Client-side validation to check for duplicates before saving
		if (frm.is_new()) {
			return new Promise((resolve, reject) => {
				frappe.call({
					method: "healthcare.healthcare.utils.check_patient_duplicates",
					args: {
						patient: frm.doc
					},
					callback: function(r) {
						if (r.message && r.message.status === "warn") {
							show_duplicate_warning(frm, r.message, resolve, reject);
						} else if (r.message && r.message.status === "disallow") {
							show_duplicate_error(frm, r.message);
							reject();
						} else {
							resolve();
						}
					}
				});
			});
		}
	},
	
	mobile : function (frm) {
		let field_value = frm.doc.mobile;
        if (field_value && /[a-zA-Z]/.test(field_value)) {
            frappe.throw(__('Only numbers are allowed in the Mobile No field.'));
        }
	},
	phone : function (frm) {
		let field_value = frm.doc.phone;
        if (field_value && /[a-zA-Z]/.test(field_value)) {
            frappe.throw(__('Only numbers are allowed in the Phone No field.'));
        }
	},

	first_name: function (frm) {
        if (frm.doc.first_name) {
            frm.set_value('first_name', capitalizeWords(frm.doc.first_name));
        }
    },

	last_name: function (frm) {
        if (frm.doc.last_name) {
            frm.set_value('last_name', capitalizeWords(frm.doc.last_name));
        }
    },
});

function capitalizeWords(name) {
    return name.charAt(0).toUpperCase() + name.slice(1).toLowerCase();
}

frappe.ui.form.on('Patient', 'dob', function(frm) {
	if (frm.doc.dob) {
		let today = new Date();
		let birthDate = new Date(frm.doc.dob);
		if (today < birthDate) {
			frappe.msgprint(__('Please select a valid Date'));
			frappe.model.set_value(frm.doctype,frm.docname, 'dob', '');
		} else {
			let age_str = get_age(frm.doc.dob);
			$(frm.fields_dict['age_html'].wrapper).html(`${__('AGE')} : ${age_str}`);
		}
	} else {
		$(frm.fields_dict['age_html'].wrapper).html('');
	}
});

frappe.ui.form.on('Patient Relation', {
	patient_relation_add: function(frm){
		frm.fields_dict['patient_relation'].grid.get_field('patient').get_query = function(doc){
			let patient_list = [];
			if(!doc.__islocal) patient_list.push(doc.name);
			$.each(doc.patient_relation, function(idx, val){
				if (val.patient) patient_list.push(val.patient);
			});
			return { filters: [['Patient', 'name', 'not in', patient_list]] };
		};
	}
});

let create_medical_record = function (frm) {
	frappe.route_options = {
		'patient': frm.doc.name,
		'status': 'Open',
		'reference_doctype': 'Patient Medical Record',
		'reference_owner': frm.doc.owner
	};
	frappe.new_doc('Patient Medical Record');
};

let get_age = function (birth) {
	let birth_moment = moment(birth);
	let current_moment = moment(Date());
	let diff = moment.duration(current_moment.diff(birth_moment));
	return `${diff.years()} ${__('Year(s)')} ${diff.months()} ${__('Month(s)')} ${diff.days()} ${__('Day(s)')}`
};

let create_vital_signs = function (frm) {
	if (!frm.doc.name) {
		frappe.throw(__('Please save the patient first'));
	}
	frappe.route_options = {
		'patient': frm.doc.name,
	};
	frappe.new_doc('Vital Signs');
};

let create_encounter = function (frm) {
	if (!frm.doc.name) {
		frappe.throw(__('Please save the patient first'));
	}
	frappe.route_options = {
		'patient': frm.doc.name,
	};
	frappe.new_doc('Patient Encounter');
};

let invoice_registration = function (frm) {
	frappe.call({
		doc: frm.doc,
		method: 'invoice_patient_registration',
		callback: function(data) {
			if (!data.exc) {
				if (data.message) {
					var doc = frappe.model.sync(data.message);
					frappe.set_route("Form", doc[0].doctype, doc[0].name);
				}
			}
		}
	});
};

// Functions for handling duplicate patients
function show_duplicate_warning(frm, data, resolve, reject) {
	// Create a dialog showing potential duplicates
	let d = new frappe.ui.Dialog({
		title: __('Potential Duplicate Patient Records Found'),
		fields: [
			{
				fieldtype: 'HTML',
				fieldname: 'duplicate_list',
				options: get_duplicate_html(data.matches)
			}
		],
		primary_action_label: __('Create New Patient Anyway'),
		primary_action: function() {
			d.hide();
			if (resolve) resolve();
		},
		secondary_action_label: __('Cancel'),
		secondary_action: function() {
			d.hide();
			if (reject) reject();
		}
	});
	
	d.show();
}

function show_duplicate_error(frm, data) {
	// Create a dialog showing duplicates that prevent creation
	let d = new frappe.ui.Dialog({
		title: __('Duplicate Patient Records Found'),
		fields: [
			{
				fieldtype: 'HTML',
				fieldname: 'duplicate_list',
				options: get_duplicate_html(data.matches)
			}
		],
		primary_action_label: __('View Existing Patient'),
		primary_action: function() {
			if (data.matches && data.matches.length) {
				frappe.set_route('Form', 'Patient', data.matches[0].name);
			}
			d.hide();
		},
		secondary_action_label: __('OK'),
		secondary_action: function() {
			d.hide();
		}
	});
	
	d.show();
}

function get_duplicate_html(matches) {
	// Generate HTML table of matches
	let html = `<div class="results">
		<table class="table table-bordered" style="margin-top: 15px;">
			<thead>
				<tr>
					<th style="width: 20%">${__('Patient ID')}</th>
					<th style="width: 30%">${__('Patient Name')}</th>
					<th style="width: 15%">${__('Gender')}</th>
					<th style="width: 15%">${__('Date of Birth')}</th>
					<th style="width: 20%">${__('Mobile')}</th>
				</tr>
			</thead>
			<tbody>`;
	
	matches.forEach(function(match) {
		html += `<tr>
			<td><a href="#Form/Patient/${match.name}">${match.name}</a></td>
			<td>${match.patient_name || ''}</td>
			<td>${match.sex || ''}</td>
			<td>${match.dob ? frappe.datetime.str_to_user(match.dob) : ''}</td>
			<td>${match.mobile || ''}</td>
		</tr>`;
	});
	
	html += `</tbody></table></div>`;
	return html;
}
