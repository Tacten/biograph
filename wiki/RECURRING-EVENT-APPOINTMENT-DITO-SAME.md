# Patient Appointment Recurring Design - Event Doctype Pattern

## Overview
Extend Patient Appointment to mirror the exact recurring functionality of Frappe's Event doctype, using virtual instances for display without creating physical appointment records. Enhanced with flexible interval patterns (every N periods) and maximum occurrence limits.

## 1. Database Schema Design

### Patient Appointment DocType Extensions

**Core Recurring Fields (Mirror Event Doctype):**
- `repeat_this_appointment` (Check) - Enable recurring (mirrors `repeat_this_event`)
- `repeat_on` (Select) - Daily/Weekly/Monthly/Yearly (mirrors Event options)
- `repeat_till` (Date) - End date for recurrence (mirrors Event field)

**Weekly Recurrence Fields (Mirror Event Doctype):**
- `monday` (Check) - Monday occurrence
- `tuesday` (Check) - Tuesday occurrence  
- `wednesday` (Check) - Wednesday occurrence
- `thursday` (Check) - Thursday occurrence
- `friday` (Check) - Friday occurrence
- `saturday` (Check) - Saturday occurrence
- `sunday` (Check) - Sunday occurrence

**Enhanced Interval Fields (Extension):**
- `repeat_interval` (Int) - Every N periods (default: 1)
- `repeat_unit` (Select) - days/weeks/months/years (derived from repeat_on)
- `max_occurrences` (Int) - Maximum number of appointments
- `end_condition` (Select) - "Until Date" / "After N Occurrences"

**No Additional DocTypes Required** - Pure virtual pattern like Event

## 2. Architecture Pattern - Event Doctype Mirror

### Virtual Instance Generation (Exact Event Pattern)

**Core Philosophy:**
- Single master appointment record (like Event)
- No physical instances created (like Event)
- Virtual instances generated on-demand for display (like Event)
- Calendar integration through virtual object generation (like Event)

**Generation Logic (Mirror Event get_events):**
```
Patient Appointment Virtual Generator:
├─ Query master appointments with recurring enabled
├─ For each master in date range:
│  ├─ Calculate occurrence dates based on pattern
│  ├─ Apply weekday filters (for weekly)
│  ├─ Apply interval multipliers (every N periods)
│  ├─ Apply max occurrence limits
│  └─ Generate virtual appointment objects
└─ Return virtual instances for calendar/list display
```

### Enhanced Recurrence Patterns

**Flexible Interval Support:**
- Every N days (1-365 days)
- Every N weeks (1-52 weeks) 
- Every N months (1-24 months)
- Every N years (1-10 years)

**Occurrence Limit Support:**
- Maximum occurrences: 1-999
- End date override capability
- Smart defaults based on appointment type

## 3. User Interface Design

### Form Layout Enhancement

**Recurring Settings Section (Mirror Event UI):**
```
┌─ Recurring Appointment Settings ────────────────────────────┐
│ ☐ Repeat this Appointment                                   │
│                                                              │
│ Repeats every: [2] [weeks ▼]                               │
│                                                              │
│ End Condition:                                               │
│ ○ Until date: [Date Field]                                  │
│ ○ After: [12] occurrences                                   │
│                                                              │
│ Weekly Options (when weeks selected):                       │
│ ☐ Mon ☐ Tue ☐ Wed ☐ Thu ☐ Fri ☐ Sat ☐ Sun                │
│                                                              │
│ Preview: Next 5 appointments will be created on:            │
│ • 2024-01-15 (Monday)                                       │
│ • 2024-01-29 (Monday) - 2 weeks later                      │
│ • 2024-02-12 (Monday) - 2 weeks later                      │
│ • 2024-02-26 (Monday) - 2 weeks later                      │
│ • 2024-03-11 (Monday) - 2 weeks later                      │
└──────────────────────────────────────────────────────────────┘
```

**No Instance Management UI Required** - Pure virtual pattern

### Calendar Integration (Mirror Event Behavior)

**Virtual Display Logic:**
- Calendar queries master appointments
- Generates virtual instances for display period
- Shows recurring appointments as individual calendar entries
- No distinction between master and virtual instances in UI

**Interaction Model:**
- Click virtual instance → Show appointment details (read-only)
- Edit virtual instance → Edit master appointment (affects all future)
- Cancel virtual instance → Cancel master appointment (affects all future)

## 4. Enhanced get_appointments Function

### Mirror Event's get_events Pattern

**Core Function Structure:**
```
get_appointments(start, end, filters):
├─ Query regular appointments (non-recurring)
├─ Query recurring master appointments
├─ For each recurring master:
│  ├─ Generate virtual instances in date range
│  ├─ Apply interval calculations (every N periods)
│  ├─ Apply occurrence limits
│  ├─ Apply weekday filters (weekly)
│  └─ Add to results
└─ Return combined appointment list
```

**Virtual Instance Object Structure:**
```
Virtual Appointment Object:
├─ All master appointment fields
├─ Calculated appointment_date (virtual date)
├─ Calculated appointment_datetime (virtual datetime)
├─ is_virtual_instance: true (flag)
├─ master_appointment_id (reference)
└─ occurrence_number (sequence in series)
```

## 5. Conflict Detection & Warning System

### Non-Blocking Conflict Detection

**Conflict Check Integration:**
- Run conflict detection during virtual instance generation
- Show warnings in calendar/list views
- Allow booking despite conflicts (warning only)
- Maintain existing conflict resolution for regular appointments

**Conflict Warning Display:**
```
Calendar View Enhancements:
├─ Virtual instances with conflicts: Orange border/icon
├─ Tooltip: "Conflict detected - Dr. Smith unavailable"
├─ Click for details: Show conflict information
└─ Proceed anyway: No blocking, just awareness
```

**Conflict Types for Virtual Instances:**
- Practitioner double-booking warnings
- Service unit capacity warnings  
- Unavailability period warnings
- Holiday/leave period warnings
- Patient existing appointment warnings

### Integration with Existing Features

**Slot Booking Compatibility:**
- Virtual instances respect practitioner schedules
- Show availability warnings for recurring slots
- Maintain existing slot validation logic
- Support recurring availability patterns

**Block Booking Compatibility:**
- Support recurring block appointments
- Virtual block instances in calendar
- Conflict warnings for overlapping blocks
- Maintain existing block booking validation

## 6. Enhanced Recurrence Calculation Logic

### Flexible Interval Calculation

**Daily Recurrence (Enhanced):**
```
Every N Days Pattern:
├─ Start Date: Master appointment date
├─ Interval: N days (1-365)
├─ Calculation: start_date + (occurrence_number * N days)
├─ Max Occurrences: Apply limit if set
└─ End Date: Respect repeat_till if set
```

**Weekly Recurrence (Enhanced):**
```
Every N Weeks Pattern:
├─ Start Date: Master appointment date
├─ Interval: N weeks (1-52)
├─ Weekday Filter: Apply selected days
├─ Calculation: start_date + (week_number * N weeks)
├─ Day Validation: Only create on selected weekdays
└─ Occurrence Counting: Count actual created instances
```

**Monthly Recurrence (Enhanced):**
```
Every N Months Pattern:
├─ Start Date: Master appointment date
├─ Interval: N months (1-24)
├─ Date Preservation: Same day of month
├─ Month-end Handling: Adjust for shorter months
└─ Calculation: add_months(start_date, occurrence * N)
```

**Yearly Recurrence (Enhanced):**
```
Every N Years Pattern:
├─ Start Date: Master appointment date
├─ Interval: N years (1-10)
├─ Date Preservation: Same month and day
├─ Leap Year Handling: Feb 29 adjustments
└─ Calculation: add_years(start_date, occurrence * N)
```

### Occurrence Limit Logic

**Maximum Occurrence Enforcement:**
```
Occurrence Counting:
├─ Track virtual instances generated
├─ Stop generation at max_occurrences
├─ Override with end_date if earlier
├─ Display progress in UI (8 of 12 completed)
└─ Handle edge cases (skipped dates)
```

## 7. Calendar and List View Integration

### Enhanced Calendar Display

**Virtual Instance Rendering:**
```
Calendar Event Properties:
├─ title: Patient name + Practitioner
├─ start: Virtual appointment datetime
├─ end: Virtual appointment end time
├─ color: Appointment type color
├─ recurring_indicator: Visual series marker
├─ conflict_warning: Conflict status icon
└─ master_id: Reference to master appointment
```

**Series Visual Grouping:**
- Subtle visual connection between series instances
- Recurring icon indicator on calendar events
- Series color coding for easy identification
- Hover effects showing series information

### Enhanced List View

**Virtual Instance Display:**
```
List View Enhancements:
├─ Show virtual instances in appointment lists
├─ Series grouping option (collapse/expand)
├─ Occurrence number display (1 of 12)
├─ Master appointment reference link
├─ Conflict warning indicators
└─ Bulk operations on series level
```

## 8. Integration with Existing Patient Appointment Features

### Fee Validity Integration

**Virtual Instance Fee Handling:**
- Virtual instances inherit fee validity from master
- Fee validity checks during virtual generation
- Display fee status in virtual instance details
- Maintain existing fee validity logic

### Therapy Session Integration

**Recurring Therapy Support:**
- Support recurring therapy appointments
- Virtual therapy session instances
- Progress tracking across virtual instances
- Integration with therapy plan management

### Billing Integration

**Virtual Instance Billing:**
- Billing triggers only for attended appointments
- Virtual instances don't generate invoices
- Master appointment holds billing configuration
- Individual session billing on completion

### Reminder System Integration

**Recurring Reminder Logic:**
- Send reminders for upcoming virtual instances
- Use master appointment reminder settings
- Calculate reminder timing for each virtual occurrence
- Maintain existing reminder infrastructure

## 9. Performance Optimization

### Efficient Virtual Generation

**Optimized Query Strategy:**
```
Performance Optimizations:
├─ Index on repeat_this_appointment field
├─ Efficient date range filtering
├─ Limit virtual generation to display period
├─ Cache frequently accessed patterns
└─ Batch process multiple masters
```

**Memory Management:**
- Generate virtual instances only for requested date ranges
- Implement pagination for long recurring series
- Cache virtual instances for active sessions
- Optimize calculation algorithms

### Scalability Considerations

**Large Series Handling:**
- Limit maximum occurrences (999)
- Implement lazy loading for very long series
- Provide series summary instead of full generation
- Background processing for complex calculations

## 10. Migration and Compatibility

### Existing Data Preservation

**Backward Compatibility:**
- All existing Patient Appointment functionality preserved
- No changes to existing appointment records
- Gradual rollout of recurring features
- Maintain existing API compatibility

**Feature Flag Support:**
- Enable/disable recurring features per installation
- Gradual user adoption
- A/B testing capability
- Rollback safety

### Integration Testing

**Comprehensive Test Coverage:**
- Virtual instance generation accuracy
- Conflict detection reliability
- Calendar integration functionality
- Performance under load
- Edge case handling

This design provides the exact recurring functionality of Frappe's Event doctype applied to Patient Appointments, with enhanced interval and occurrence limit features, while maintaining full compatibility with existing appointment management features and providing non-blocking conflict warnings.
