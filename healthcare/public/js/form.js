const FrappeForm = frappe.ui.form.Form

FrappeForm.prototype.savesubmit = function (btn, callback, on_error) {
    var me = this;
    return new Promise((resolve) => {
        this.validate_form_action("Submit");
        confirmation_message = __("Permanently Submit {0}?", [this.docname])
        if (["Sales Invoice", "Patient Encounter", "Therapy Session", "Vital Signs"].includes(this.doc.doctype)) {
            confirmation_message = __(`Permanently Submit ${this.docname}?<br><br><b>${this.doc.title}</b>`);
        }
        if (["Therapy Session", "Patient Assessment", "Medication Request", "Service Request"].includes(this.doc.doctype)) {
            confirmation_message = __(`Permanently Submit ${this.docname}?<br><br><b>${this.doc.patient_name}</b>`);
        }        
        frappe.confirm(
            __(confirmation_message),
            function () {
                frappe.validated = true;
                me.script_manager.trigger("before_submit").then(function () {
                    if (!frappe.validated) {
                        return me.handle_save_fail(btn, on_error);
                    }

                    me.save(
                        "Submit",
                        function (r) {
                            if (r.exc) {
                                me.handle_save_fail(btn, on_error);
                            } else {
                                frappe.utils.play_sound("submit");
                                callback && callback();
                                me.script_manager
                                    .trigger("on_submit")
                                    .then(() => resolve(me))
                                    .then(() => {
                                        if (frappe.route_hooks.after_submit) {
                                            let route_callback =
                                                frappe.route_hooks.after_submit;
                                            delete frappe.route_hooks.after_submit;
                                            route_callback(me);
                                        }
                                    });
                            }
                        },
                        btn,
                        () => me.handle_save_fail(btn, on_error),
                        resolve
                    );
                });
            },
            () => me.handle_save_fail(btn, on_error)
        );
    });
};