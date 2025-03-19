

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


## Extra Details


# Understanding the "Is Required" Field in Patient Duplicate Check

In the Patient Duplicate Check system, the "Is Required" field is part of the rule configuration but might be confusing. Let me explain how it works:

## What "Is Required" Actually Does

The "Is Required" checkbox in the Fields to Check child table serves as a **documentation/visual indicator** rather than a functional filter. Here's what you should know:

1. **It Does Not Filter Rules**: The system will check for duplicates based on all fields added to a rule, regardless of whether "Is Required" is checked or not.

2. **Matching Logic**: When checking for duplicates, ALL fields in a rule must match for the rule to be triggered. The "Is Required" flag doesn't change this behavior.

3. **Display Purpose**: The checkbox is primarily meant to help administrators visually identify which fields they consider essential for a particular rule.

## Common Misunderstandings

You might think "Is Required" means:
- Only required fields are used in matching (not true - all fields are used)
- The rule only applies if required fields have values (not true - the rule checks all fields that have values)

## How Duplicate Checking Actually Works

1. For each rule, the system looks at all fields added to that rule (first_name, last_name, gender, etc.)
2. It builds a filter where ALL these fields must match exactly
3. If a field in the rule has no value in the new patient record being created, that field is skipped in the filter
4. If any existing patient matches ALL the non-empty fields in the filter, the rule triggers

## Example for Clarity

If you have a rule with these fields:
- First Name (Is Required: Yes)
- Last Name (Is Required: Yes)
- Mobile (Is Required: No)

And a user creates a new patient with:
- First Name: "John"
- Last Name: "Doe"
- Mobile: "1234567890"

The system will check for existing patients where:
- First Name = "John" AND
- Last Name = "Doe" AND
- Mobile = "1234567890"

If the user didn't enter a mobile number, the system would only check for:
- First Name = "John" AND
- Last Name = "Doe"

The "Is Required" flags don't change this behavior. They're simply visual indicators for administrators.

## Recommendation

When configuring rules:
1. Use "Is Required" as a visual reminder of which fields you consider most important
2. Remember that ALL fields in a rule must match for the rule to trigger (if they have values)
3. Focus more on the rule's priority and action to control the duplicate checking behavior



## What "Is Required" Does

The "Is Required" flag determines whether a field must have a value for that field to be included in the duplicate check filter. Here's how it works in the actual code implementation:

1. For each field in a rule's configuration, the system checks if the patient being created has a value for that field
2. **If the patient has a value** for the field, it adds that field to the filter criteria
3. **If the patient doesn't have a value** for the field, it's not added to the filter

**Important:** Currently, the "Is Required" flag is stored in the configuration but isn't actively used in the filter logic. This is because the system automatically only includes fields that have values in the new patient record.

## How Filters Are Built and Used


### Example to Illustrate:

1. Let's say you have a rule checking First Name, Last Name, and Mobile
2. A new patient is being created with:
   - First Name: "John"
   - Last Name: "Smith"  
   - Mobile: (empty)

3. The system builds a filter like:
   ```
   {
     "first_name": "John",
     "last_name": "Smith"
   }
   ```

4. It then searches for existing patients with BOTH first_name="John" AND last_name="Smith"
5. If matches are found, the rule's action (Warn/Disallow) applies

## Key Points About Filtering Logic:

1. **All filters are combined with AND logic** - all conditions must match for a record to be considered a duplicate
2. Only fields with values in the new patient record are included in the filter
3. A rule with multiple fields will only find matches where ALL those fields match (with values)
4. Empty/null values in the new record are not used for matching

## How "Is Required" Could Be Enhanced

In a future enhancement, the "Is Required" flag could be used to:

1. Determine if the rule should even be evaluated when a required field is empty
2. Change the validation behavior to require certain fields before creating a patient
3. Create more sophisticated matching logic (for example, at least 3 of 5 fields must match)

## Practical Example:

**Rule configuration:**
- Fields: First Name (required), Last Name (required), Mobile (not required)
- Action: Warn
- Priority: 10

**Current behavior:**
- If a patient has all three fields filled, all three are used for matching
- If a patient has only First Name and Last Name filled, only those two are used
- The rule will only match if the specified fields with values all match

This means that the "Is Required" flag currently serves as documentation of which fields you consider essential for that rule, but in practice, the system includes all fields that have values in the filtering process.


