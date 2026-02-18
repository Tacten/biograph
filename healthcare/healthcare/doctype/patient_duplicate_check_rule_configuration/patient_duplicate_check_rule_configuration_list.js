frappe.listview_settings['Patient Duplicate Check Rule Configuration'] = {
    add_fields: ["rule_name", "action", "priority"],
    get_indicator: function(doc) {
        if(doc.action === "Disallow") {
            return [__("Disallow"), "red", "action,=,Disallow"];
        } else if(doc.action === "Warn") {
            return [__("Warn"), "orange", "action,=,Warn"];
        } else {
            return [__("Allow"), "green", "action,=,Allow"];
        }
    }
}; 