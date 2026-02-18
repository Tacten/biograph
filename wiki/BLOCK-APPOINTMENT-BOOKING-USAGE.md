# Block-Based Appointment Booking - User Guide

## Introduction

The Block-Based Appointment System provides flexible scheduling options for healthcare appointments. Unlike traditional fixed-slot booking, this feature allows you to book appointments using custom time ranges, giving you greater control over appointment durations and scheduling.

This guide covers:
- How to book appointments using block time
- Managing practitioner unavailability
- Therapy session management
- Conflict resolution

---

## Quick Start

### Booking Methods Available

| Method | Description | Best For |
|--------|-------------|----------|
| **Slot-Based** | Select from predefined time slots | Routine appointments with standard durations |
| **Block-Time** | Define custom start and end times | Complex procedures, therapy sessions, variable-length appointments |

---

## Booking an Appointment

### Step 1: Create New Appointment

1. Navigate to **Healthcare > Patient Appointment**
2. Click **+ Add Patient Appointment** or use the calendar view
3. Fill in the required fields:
   - **Patient**: Select the patient
   - **Appointment Type**: Choose the type (determines booking mode)
   - **Company**: Select your healthcare facility

### Step 2: Select Practitioner/Department/Service Unit

Based on your appointment type configuration:

- **Practitioner-based**: Select a healthcare practitioner
- **Department-based**: Select a medical department
- **Service Unit-based**: Select a healthcare service unit

### Step 3: Check Availability

1. Click the **Check Availability** button
2. The availability dialog opens showing:
   - Available time slots (slot-based mode)
   - OR time range selector (block-time mode)
3. Toggle between modes using the **Block Time** switch if available

### Step 4: Select Time (Block-Time Mode)

1. Choose the **Appointment Date**
2. Enter the **From Time** (start time)
3. Enter the **To Time** (end time)
4. Click **Check Availability** to validate

### Step 5: Review and Book

- **Green indicator**: Time range is available - proceed with booking
- **Red indicator**: Conflicts detected - resolve before booking

Click **Book** to confirm the appointment.

---

## Managing Practitioner Unavailability

The system supports two methods for managing unavailability:

### Method 1: Practitioner Availability Records

Use this for planned, recurring unavailability (vacations, training, regular breaks).

1. Navigate to **Healthcare > Practitioner Availability**
2. Click **+ Add Practitioner Availability**
3. Configure:
   - **Type**: Select "Unavailable"
   - **Scope Type**: Healthcare Practitioner, Department, or Service Unit
   - **Scope**: Select the specific entity
   - **Start Date / End Date**: Date range
   - **Start Time / End Time**: Daily time range
   - **Reason**: Time Off, Break, Training, Travel, or Emergency
   - **Repeat**: Never, Daily, Weekly, or Monthly

### Method 2: Unavailability Appointments

Use this for ad-hoc blocking directly from the calendar.

1. From the appointment calendar, select the time block
2. Create an appointment with **Appointment Type**: "Unavailable"
3. The time block appears on the calendar as blocked

### Conflict Checking

When booking appointments, the system automatically checks for conflicts with:
- Existing patient appointments
- Practitioner unavailability records
- Other blocked time slots

---

## Therapy Session Management

### Associating Multiple Therapies

When booking a therapy appointment with a Therapy Plan:

1. Select the **Therapy Plan** in the appointment form
2. Click **Get Therapy Types** to load available therapies
3. Select one or more therapy types to associate with the appointment
4. Each therapy type can have its own duration

### Creating Therapy Sessions

After booking a therapy appointment:

1. Open the saved appointment
2. Click the **Create Therapy Sessions** button
3. Select which therapy types to create sessions for
4. The system creates individual Therapy Session documents

### Tracking Therapy Progress

Each therapy in the appointment shows:
- **Therapy Type**: Name of the therapy
- **Duration**: Time allocated
- **Session Created**: Whether a session document exists
- **Therapy Session**: Link to the created session

---

## Rescheduling Appointments

### For Practitioner-Based Appointments

1. Open the appointment
2. Click **Reschedule**
3. Use the availability dialog to select a new time
4. Confirm the change

### For Department/Service Unit Appointments

1. Open the appointment
2. Click **Reschedule**
3. Select a new department/service unit and date
4. Click **Book** to confirm

---

## Cancelling Appointments

1. Open the appointment
2. Click the **Cancel** button
3. Confirm the cancellation

**Note**: Cancelling an appointment:
- Updates the appointment status to "Cancelled"
- Cancels associated calendar events
- Updates any linked insurance coverage
- Releases the time slot for other bookings

---

## Conflict Resolution

When conflicts are detected during booking:

### Viewing Conflicts

The system displays:
- List of conflicting appointments
- Patient names and times
- Appointment types

### Resolving Conflicts

**Option 1**: Choose a different time
- Adjust your From Time and To Time
- Re-check availability

**Option 2**: Cancel conflicting appointments
- Navigate to the conflicting appointment
- Cancel it if appropriate
- Return and complete your booking

**Important**: The system does not allow automatic override of existing appointments. This protects patient schedules and prevents accidental double-booking.

---

## Appointment Statuses

| Status | Description |
|--------|-------------|
| **Scheduled** | Future appointment confirmed |
| **Confirmed** | Appointment for today, confirmed |
| **Checked In** | Patient has arrived |
| **Checked Out** | Appointment completed |
| **Closed** | Appointment finalized |
| **Cancelled** | Appointment cancelled |
| **No Show** | Patient did not attend |
| **Needs Rescheduling** | Appointment requires rescheduling |
| **Unavailable** | Time blocked (not a patient appointment) |

---

## Calendar View

The appointment calendar displays:

- **Regular appointments**: Colored by appointment type
- **Unavailability blocks**: Displayed in red
- **Duration**: Visual representation of appointment length

### Calendar Features

- Click on empty time to create new appointment
- Click on existing appointment to view/edit
- Drag to reschedule (if supported)
- Filter by practitioner, department, or service unit

---

## Tips and Best Practices

### For Efficient Scheduling

1. **Use block-time for complex procedures**: When appointment duration varies, use block-time mode for precise scheduling
2. **Check conflicts early**: Always validate availability before finalizing details
3. **Set up recurring unavailability**: Use Practitioner Availability for regular breaks and time off

### For Therapy Practices

1. **Associate all therapies upfront**: Link all planned therapy types when creating the appointment
2. **Create sessions before the appointment**: Generate therapy session documents ahead of time for proper documentation
3. **Use therapy plans**: Link appointments to therapy plans for better tracking

### For Conflict Prevention

1. **Review daily schedules**: Check the calendar view before booking
2. **Communicate with staff**: Coordinate on shared resource scheduling
3. **Block personal time**: Use unavailability records for meetings, breaks, etc.

---

## Troubleshooting

### "Appointment conflicts with Practitioner Availability"

**Cause**: The selected time overlaps with a blocked period.

**Solution**: 
1. Check Practitioner Availability records
2. Choose a different time, or
3. Modify/cancel the availability record if appropriate

### "Patient already has an appointment booked"

**Cause**: The patient has another appointment at the same time or day (depending on settings).

**Solution**:
1. Review the patient's existing appointments
2. Choose a different time or date
3. Cancel the existing appointment if it's a duplicate

### "Not allowed, cannot overlap appointment"

**Cause**: The time range overlaps with an existing appointment for the same practitioner.

**Solution**:
1. View the conflicting appointment details
2. Adjust your time range to avoid overlap
3. Cancel the conflicting appointment if appropriate

---

## Related Features

- **[Patient Duplicate Checker](PATIENT-DUPLICATE-CHECKER-USAGE-DOC.md)**: Prevent duplicate patient records
- **Therapy Plan**: Manage patient therapy programs
- **Healthcare Service Unit**: Configure rooms and equipment
- **Practitioner Schedule**: Set up practitioner working hours

---

## Version Information

- **Feature Version**: Healthcare 16.0
- **Required Frappe Version**: 16.x
- **Last Updated**: February 2026
