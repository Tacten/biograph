frappe.ui.form.on('Healthcare Practitioner', {
    residence_phone : (frm)=>{
        let field_value = frm.doc.residence_phone;
        if (field_value && /[a-zA-Z]/.test(field_value)) {
            frappe.throw(__('Only numbers are allowed in the phone number type field.'));
        }
    },
    mobile_phone : (frm) =>{
        let field_value = frm.doc.mobile_phone;
        if (field_value && /[a-zA-Z]/.test(field_value)) {
            frappe.throw(__('Only numbers are allowed in the phone number type field.'));
        }
    },
    office_phone : (frm) =>{
        let field_value = frm.doc.office_phone;
        if (field_value && /[a-zA-Z]/.test(field_value)) {
            frappe.throw(__('Only numbers are allowed in the phone number type field.'));
        }
    }
})