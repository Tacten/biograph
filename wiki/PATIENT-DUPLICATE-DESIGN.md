
# Proposed Design for Configurable Patient Duplicate Checking

## 1. Configuration in Healthcare Settings

We'll add a new section in the Healthcare Settings doctype:

```
Patient Duplicate Check Settings Section
├── Enable Patient Duplicate Check
├── Duplicate Check Configuration (Child Table)
│   ├── Field Name
│   ├── Field Label 
│   ├── Is Required
│   ├── Order
```

The Duplicate Check Configuration child table will allow administrators to select which fields to include in duplicate checking and their importance. The available fields would be:
- First Name
- Last Name
- Gender
- Date of Birth
- Mobile Number
- Email
- Any other relevant fields

## 2. Duplicate Check Rules Configuration

We'll add another child table to define the rules for duplicate checking:

```
Duplicate Check Rules (Child Table)
├── Rule Name
├── Fields (Link to multiple Duplicate Check Configuration entries)
├── Action (Allow, Warn, Disallow)
├── Message
├── Priority (Lower number = higher priority)
```

This allows administrators to define complex rules like those in the requirement document. For example:
- Rule 1: If First Name, Last Name, Gender, DOB, and Mobile all match exactly -> Disallow creation
- Rule 2: If First Name and Last Name match exactly -> Show warning

## 3. Backend Implementation

### 3.1 Patient Duplicate Checker Module

Create a new module that will handle the duplicate checking logic:

```python
# healthcare/healthcare/utils/patient_duplicate_checker.py

class PatientDuplicateChecker:
    def __init__(self, patient_doc):
        self.patient = patient_doc
        self.settings = frappe.get_doc("Healthcare Settings")
        self.duplicate_check_enabled = self.settings.get("enable_patient_duplicate_check", 0)
        
    def check_duplicates(self):
        """Check for duplicate patients based on configured rules"""
        if not self.duplicate_check_enabled:
            return {"status": "allow", "matches": []}
            
        # Get the configuration
        duplicate_check_rules = self.settings.get("duplicate_check_rules", [])
        
        if not duplicate_check_rules:
            return {"status": "allow", "matches": []}
            
        # Sort rules by priority
        duplicate_check_rules.sort(key=lambda x: x.priority)
        
        # Check each rule
        for rule in duplicate_check_rules:
            result = self._check_rule(rule)
            if result["status"] != "allow":
                return result
                
        return {"status": "allow", "matches": []}
    
    def _check_rule(self, rule):
        """Check a specific rule against existing patients"""
        filters = {}
        
        # Build filters based on rule fields
        for field_config in rule.fields:
            field_name = field_config.field_name
            if hasattr(self.patient, field_name) and self.patient.get(field_name):
                filters[field_name] = self.patient.get(field_name)
        
        if not filters:
            return {"status": "allow", "matches": []}
            
        # Add filter to exclude current patient if it exists
        if self.patient.name:
            filters["name"] = ["!=", self.patient.name]
            
        # Query for matching patients
        matches = frappe.get_all("Patient", 
                                filters=filters, 
                                fields=["name", "patient_name", "sex", "dob", "mobile", "email"])
        
        if matches:
            return {
                "status": rule.action.lower(),
                "message": rule.message,
                "matches": matches
            }
            
        return {"status": "allow", "matches": []}
```

### 3.2 Integration with Patient DocType

Modify the Patient doctype's `validate` method to include the duplicate check:

```python
def validate(self):
    self.set_full_name()
    self.flags.is_new_doc = self.is_new()
    self.flags.existing_customer = self.is_new() and bool(self.customer)
    
    # Check for duplicates
    from healthcare.healthcare.utils.patient_duplicate_checker import PatientDuplicateChecker
    
    checker = PatientDuplicateChecker(self)
    result = checker.check_duplicates()
    
    if result["status"] == "disallow":
        frappe.throw(
            _(result["message"] or "Duplicate patient record(s) found"),
            frappe.DuplicateEntryError,
            title=_("Duplicate Patient"),
            exc=frappe.DuplicateEntryError,
            is_minimizable=True,
            wide=True,
            data={"matches": result["matches"]}
        )
    elif result["status"] == "warn":
        self.flags.duplicate_check_warning = {
            "message": result["message"] or "Possible duplicate patient record(s) found",
            "matches": result["matches"]
        }
```

## 4. Frontend Implementation

### 4.1 Patient Form JS

Modify the Patient form JS to handle the duplicate warnings:

```javascript
frappe.ui.form.on('Patient', {
    refresh: function(frm) {
        // Other refresh code...
        
        // Check for duplicate warnings
        if (frm.doc.__unsaved && frm.doc.__duplicate_check_warning) {
            show_duplicate_warning(frm);
        }
    },
    
    validate: function(frm) {
        // Client-side validation to check for duplicates before saving
        return new Promise((resolve, reject) => {
            frappe.call({
                method: "healthcare.healthcare.utils.patient_duplicate_checker.check_patient_duplicates",
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
});

function show_duplicate_warning(frm, data, resolve, reject) {
    // Create a dialog showing potential duplicates
    let d = new frappe.ui.Dialog({
        title: __('Potential Duplicate Patient Records Found'),
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'duplicate_list',
                label: __('Matching Patients'),
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
                label: __('Matching Patients'),
                options: get_duplicate_html(data.matches)
            }
        ],
        primary_action_label: __('View Existing Patient'),
        primary_action: function() {
            if (data.matches && data.matches.length) {
                frappe.set_route('Form', 'Patient', data.matches[0].name);
            }
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
```

## 5. Patient Merge Functionality

As mentioned in the requirements, there should be a way to merge duplicate patient records:

```
Healthcare > Patient > Merge Patients
```

This will be a separate doctype/tool that allows:
1. Selecting multiple patient records
2. Comparing their data side by side
3. Choosing which data to keep from each record
4. Merging the records into a single patient record
5. Updating all related transactions to point to the merged patient

## Benefits of this Design

1. **Flexibility**: Administrators can configure which fields to use for duplicate checking and set up complex rules.
2. **User Experience**: Clear warnings and error messages with actionable information.
3. **Performance**: Efficient querying based only on the configured fields.
4. **Maintainability**: Clean separation of concerns with a dedicated module for duplicate checking logic.
5. **Future-proofing**: Easy to extend with additional fields or rule types.

## Implementation Plan

1. Create the Healthcare Settings changes to add configuration options
2. Implement the PatientDuplicateChecker module
3. Modify the Patient doctype to use the duplicate checker
4. Add the frontend dialogs for warnings and errors
5. Implement the Patient Merge functionality

Would you like me to elaborate on any specific aspect of this design before we proceed with implementation?
