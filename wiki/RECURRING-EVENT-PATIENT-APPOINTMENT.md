# Recurring Patient Appointment Design

## Overview
A comprehensive design to add recurring appointment functionality to the Patient Appointment doctype, leveraging the existing Event recurring pattern without modifying the core Frappe Event module.

## 1. Database Schema Design

### Patient Appointment DocType Enhancements

**New Section: "Recurring Appointment Settings"**
- `repeat_this_appointment` (Check) - Enable recurring
- `repeat_on` (Select) - Daily/Weekly/Monthly/Yearly
- `repeat_till` (Date) - End date for recurrence
- Weekday checkboxes (Monday-Sunday) for weekly recurrence
- `parent_recurring_appointment` (Link) - Reference to master appointment
- `is_recurring_instance` (Check) - Flag for generated instances
- `original_appointment_date` (Date) - Original date for instances

### Appointment Exception DocType (New)
```
- parent_appointment (Link to Patient Appointment)
- exception_date (Date)
- exception_type (Select: Cancelled/Modified/Moved)
- modified_appointment (Link to Patient Appointment)
- reason (Text)
```

## 2. Architecture Pattern

### Master-Instance Pattern
- **Master Appointment**: Original appointment with recurring settings
- **Instance Appointments**: Auto-generated appointments for each occurrence
- **Exception Handling**: Track modifications to individual instances

### Conflict Management Strategy
- **Detection**: Check overlaps during creation
- **Warning System**: Alert users but allow creation
- **Logging**: Record conflicts for review
- **Resolution**: Manual intervention required

## 3. User Interface Design

### Form Layout Enhancements

**Recurring Settings Section** (Collapsible)
```
┌─ Recurring Appointment Settings ────────────────┐
│ ☐ Repeat this Appointment                       │
│                                                  │
│ Repeat On: [Dropdown: Daily/Weekly/Monthly...]  │
│ Repeat Till: [Date Field]                       │
│                                                  │
│ Weekly Days (when Weekly selected):              │
│ ☐ Mon ☐ Tue ☐ Wed ☐ Thu ☐ Fri ☐ Sat ☐ Sun     │
└──────────────────────────────────────────────────┘
```

**Action Buttons for Recurring Appointments**
- Master Appointment:
  - "View Recurring Series"
  - "Update All Future"
  - "Cancel All Future"
  - "Recreate Series"

- Instance Appointment:
  - "View Parent Appointment"
  - "Update This & Future"
  - "Cancel This Instance"

### Conflict Warning Dialog
```
┌─ Recurring Appointment Conflicts ───────────────┐
│ ⚠️ The following dates have conflicts:           │
│                                                  │
│ 📅 2024-01-15: Dr. Smith (PA-001) - Scheduled  │
│ 📅 2024-01-22: Dr. Smith (PA-002) - Confirmed  │
│ 📅 2024-01-29: Service unavailable              │
│                                                  │
│ [Proceed Anyway] [Review Conflicts] [Cancel]    │
└──────────────────────────────────────────────────┘
```

## 4. Functional Design

### Recurring Appointment Creation Flow
1. User enables "Repeat this Appointment"
2. System validates recurring settings
3. On save, system generates future instances
4. Conflict detection runs in background
5. Warnings displayed for conflicts
6. Calendar events created for each instance

### Conflict Detection Logic
**Types of Conflicts:**
- Practitioner double-booking
- Service unit capacity exceeded
- Unavailability periods
- Holiday conflicts
- Leave periods

**Conflict Resolution:**
- **Soft Conflicts**: Warn but allow (capacity issues)
- **Hard Conflicts**: Block creation (unavailability)
- **Override Option**: Admin can force creation

### Exception Handling
**Individual Instance Modifications:**
- Cancel single instance → Create exception record
- Reschedule single instance → Create new appointment + exception
- Modify single instance → Create modified appointment + exception

## 5. Calendar Integration Design

### Enhanced Calendar View
- Display both master and instance appointments
- Visual indicators for recurring series
- Conflict highlighting
- Bulk operations support

### Calendar Event Synchronization
- Each appointment instance creates separate Event
- Events linked to appointment instances
- Master appointment doesn't create calendar event
- Exception handling for modified instances

## 6. Appointment Type Support

### Regular Appointments
- Standard patient appointments
- Practitioner consultations
- Follow-up appointments

### Practitioner Availability Slots
- Recurring availability windows
- Block booking support
- Capacity management

### Unavailability Periods
- Recurring leave patterns
- Holiday schedules
- Maintenance windows

### Block Appointments
- Time block reservations
- Resource allocation
- Capacity planning

## 7. Validation & Business Rules

### Recurring Validation Rules
- End date must be after start date
- Weekly recurrence requires day selection
- Maximum recurrence period (e.g., 2 years)
- Minimum interval between occurrences

### Conflict Resolution Rules
- Patient cannot have overlapping appointments
- Practitioner availability respected
- Service unit capacity enforced
- Holiday/leave periods honored

## 8. Reporting & Analytics

### Recurring Appointment Reports
- Series overview dashboard
- Conflict analysis report
- Utilization statistics
- Exception tracking

### Performance Metrics
- Appointment completion rates
- No-show patterns
- Resource utilization
- Conflict frequency

## 9. Integration Points

### Healthcare Module Integration
- Fee validity management
- Therapy session planning
- Clinical procedure scheduling
- Inpatient care coordination

### External System Integration
- Google Calendar sync (individual events)
- SMS/Email reminders
- Payment processing
- Insurance verification

## 10. Implementation Phases

### Phase 1: Core Functionality
- Basic recurring appointment creation
- Simple conflict detection
- Master-instance relationship

### Phase 2: Advanced Features
- Exception handling
- Bulk operations
- Enhanced conflict resolution

### Phase 3: Integration & Optimization
- Calendar synchronization
- Reporting dashboard
- Performance optimization

## 11. Security & Permissions

### Access Control
- Recurring creation permissions
- Instance modification rights
- Exception handling access
- Bulk operation permissions

### Data Integrity
- Referential integrity between master/instances
- Exception record consistency
- Calendar event synchronization
- Audit trail maintenance

## 12. Benefits

### For Healthcare Providers
- Streamlined recurring appointment management
- Reduced administrative overhead
- Better resource utilization
- Improved patient care continuity

### For Patients
- Consistent appointment scheduling
- Reduced booking friction
- Better treatment adherence
- Improved care experience

### For System Administrators
- Centralized recurring management
- Comprehensive conflict detection
- Detailed audit trails
- Flexible configuration options

This design provides a robust, scalable solution for recurring appointments while maintaining compatibility with existing Healthcare module functionality and avoiding modifications to the core Frappe Event system.


