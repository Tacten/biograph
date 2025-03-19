

# Patient Duplicate Check: End-to-End Documentation

## Table of Contents
1. Overview
2. Configuration
3. Understanding Rule Configuration
4. User Experience
5. Examples and Best Practices

## 1. Overview

The Patient Duplicate Check functionality helps prevent the creation of duplicate patient records by comparing new patient information against existing records. The system can be configured to:
- Allow creation without warning
- Warn about potential duplicates but allow creation
- Disallow creation when exact matches are found

## 2. Configuration

### 2.1 Enabling Patient Duplicate Check

1. Navigate to **Healthcare → Setup → Healthcare Settings**
2. Go to the **Patient Duplicate Check** tab
3. Check the box for **Enable Patient Duplicate Check**
4. Save the changes

### 2.2 Adding Duplicate Check Rules

1. Still in Healthcare Settings, scroll down to the **Rules** section
2. Click "Add Row" to add a new rule
3. Select an existing rule configuration or create a new one by clicking the + button next to the "Rule Configuration" field

### 2.3 Creating a New Rule Configuration

1. When clicking the + button, a new form opens for "Patient Duplicate Check Rule Configuration"
2. Fill in the following fields:
   - **Rule Name**: A descriptive name (e.g., "First Name and Mobile Match")
   - **Action**: Select "Allow", "Warn", or "Disallow"
   - **Message**: Custom message to show users when this rule matches
   - **Priority**: Lower numbers have higher priority (e.g., 1 is checked before 10)
3. In the **Fields** section, add the fields to check for matches:
   - Add rows for each field you want to check (First Name, Last Name, Gender, Date of Birth, Mobile)
   - Set "Is Required" if the field must have a value for the rule to apply
4. Save the rule configuration

## 3. Understanding Rule Configuration

### 3.1 Rule Fields Explained

- **Rule Name**: Identifies the rule in the system
- **Action**:
  - **Allow**: Does nothing (patient creation proceeds normally)
  - **Warn**: Shows a warning but lets users continue if they choose
  - **Disallow**: Prevents patient creation entirely
- **Message**: Custom text shown to users when the rule matches
- **Priority**: Determines the order of rule processing

### 3.2 How Priority Works

Rules are processed in priority order (lowest number first). When a rule matches:
1. If the rule's action is "Allow" - processing continues to the next rule
2. If the rule's action is "Warn" or "Disallow" - rule processing stops and the action is applied

**Example**: If you have these rules:
- Rule A: Priority 5, checks First Name, action "Warn"
- Rule B: Priority 10, checks Mobile, action "Warn"
- Rule C: Priority 1, checks First Name + Last Name + Gender + DOB + Mobile, action "Disallow"

The system will:
1. Check Rule C first (highest priority) - if it matches, immediately disallow creation
2. Then check Rule A - if it matches, show a warning
3. Finally check Rule B - if it matches, show a warning

### 3.3 Fields to Check

Each rule can check one or more fields:
- **First Name**: Patient's first name
- **Last Name**: Patient's last name
- **Gender**: Patient's gender/sex
- **Date of Birth**: Patient's DOB
- **Mobile**: Patient's mobile number

A rule matches when ALL fields in the rule match an existing patient record. For example, if a rule checks First Name and Mobile, both must match for the rule to trigger.

## 4. User Experience

### 4.1 Creating a New Patient

When a user creates a new patient:
1. They fill out the patient information form
2. Upon saving, the system runs duplicate checks against existing patients
3. Depending on the matching rules, one of three things happens:

### 4.2 No Match or "Allow" Match

If no rules match, or only rules with "Allow" action match, the patient is created normally without interruption.

### 4.3 "Warn" Match

If a rule with "Warn" action matches:
1. A dialog appears titled "Potential Duplicate Patient Records Found"
2. The dialog shows a table of matching patients with their details
3. The user has two options:
   - "Create New Patient Anyway": Proceeds with creation
   - "Cancel": Cancels the creation process

### 4.4 "Disallow" Match

If a rule with "Disallow" action matches:
1. A dialog appears titled "Duplicate Patient Records Found"
2. The dialog shows a table of matching patients with their details
3. The user has two options:
   - "View Existing Patient": Opens the first matching patient record
   - "OK": Closes the dialog without creating the patient

## 5. Examples and Best Practices

### 5.1 Recommended Rule Setup

Based on the 25 scenarios described in the requirements, we recommend implementing rules in this priority order:

1. **Disallow Rules** (Priority 1-6):
   - All fields exact match
   - First Name + Last Name + Gender + DOB match
   - First Name + Last Name + Gender + Mobile match
   - First Name + Last Name + DOB + Mobile match
   - First Name + Gender + DOB + Mobile match
   - Last Name + Gender + DOB + Mobile match

2. **Warning Rules** (Priority 7-23):
   - First Name + Last Name match
   - First Name + Gender match
   - First Name + DOB match
   - First Name + Mobile match
   - And other combinations

### 5.2 Best Practices

1. **Use priority effectively**: Make stricter rules (with more fields) have higher priority (lower numbers)
2. **Custom messages**: Use descriptive messages to explain why a match was found
3. **Regular maintenance**: Periodically review and update rules based on user feedback
4. **Balance strictness**: Too strict may frustrate users, too lenient may allow duplicates
5. **Train users**: Ensure front desk staff understand the importance of checking existing records

### 5.3 Implementation Example

To implement the scenario where First Name, Last Name, and Mobile all match (warning rule):

1. Create a new rule configuration:
   - **Rule Name**: "First Last Name and Mobile Match"
   - **Action**: "Warn"
   - **Message**: "Potential duplicate patient found with matching name and mobile number."
   - **Priority**: 17
2. Add fields:
   - First Name (required)
   - Last Name (required)
   - Mobile (required)
3. Save the rule and add it to Healthcare Settings

This rule will warn users when they try to create a patient whose first name, last name, and mobile number all match an existing patient.

---

By following this documentation, healthcare administrators can efficiently configure patient duplicate checking, and front desk staff can understand the system's behavior when creating new patients. This helps maintain clean patient data while providing flexibility for legitimate patient record creation.
