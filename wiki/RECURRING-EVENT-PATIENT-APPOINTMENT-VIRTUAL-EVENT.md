# Hybrid Virtual-Instance Recurring Patient Appointment Design

## Overview
An optimized design that extends Patient Appointment with recurring capabilities using a hybrid approach: virtual instances for display/calendar with on-demand materialization for modifications, leveraging Frappe Event's recurring pattern without core modifications.

## 1. Enhanced Database Schema Design

### Patient Appointment DocType Enhancements

**Core Recurring Fields:**
- `repeat_this_appointment` (Check) - Enable recurring functionality
- `repeat_on` (Select) - Daily/Weekly/Monthly/Yearly
- `repeat_till` (Date) - End date for recurrence series
- `repeat_interval` (Int) - Every N periods (e.g., every 2 weeks)
- `max_occurrences` (Int) - Maximum number of appointments
- `occurrence_count` (Int) - Current count (read-only)

**Weekly Recurrence Fields:**
- `monday`, `tuesday`, `wednesday`, `thursday`, `friday`, `saturday`, `sunday` (Check)

**Instance Management Fields:**
- `is_recurring_master` (Check) - Flag for master appointment
- `is_materialized_instance` (Check) - Flag for real instances
- `parent_recurring_appointment` (Link) - Reference to master
- `virtual_instance_date` (Date) - Original virtual date for materialized instances

### Patient Appointment Exception DocType (New)
```
Doctype: Patient Appointment Exception
Fields:
- master_appointment (Link to Patient Appointment) - Required
- exception_date (Date) - Required
- exception_type (Select: Cancelled/Modified/Rescheduled/Additional) - Required
- exception_data (JSON/Long Text) - Store modification details
- materialized_appointment (Link to Patient Appointment) - Optional
- reason (Text) - User explanation
- created_by_user (Link to User) - Audit trail
- exception_status (Select: Active/Resolved/Superseded) - Management
```

## 2. Hybrid Architecture Pattern

### Three-Tier System

**Tier 1: Master Appointments**
- Store recurring pattern and rules
- No calendar events created
- Single source of truth for series
- Handle bulk operations and pattern changes

**Tier 2: Virtual Instances**
- Generated on-demand for display
- Exist only in memory/cache
- Used for calendar views and list displays
- Apply exception rules during generation

**Tier 3: Materialized Instances**
- Created only when user interaction requires persistence
- Full Patient Appointment records
- Have associated calendar events
- Linked to master via exception records

### Virtual Instance Generation Engine

**Core Generator Function:**
```
Virtual Instance Generator:
Input: Master Appointment + Date Range + Exception Rules
Process: 
1. Calculate occurrence dates based on pattern
2. Apply exception filters (skip cancelled, modify changed)
3. Generate virtual appointment objects
4. Merge with materialized instances
Output: Unified appointment list for display
```

**Caching Strategy:**
- Cache virtual instances for active date ranges
- Invalidate on master changes or new exceptions
- Use memory cache for real-time calendar performance
- Implement smart cache warming for frequently accessed ranges

## 3. User Interface Design Philosophy

### Seamless User Experience

**Unified View Principle:**
- Users see no distinction between virtual and materialized instances
- All appointments appear identical in lists and calendars
- Actions trigger materialization transparently
- Consistent behavior across all appointment types

**Progressive Disclosure:**
- Simple recurring setup for basic users
- Advanced options for power users
- Exception management for administrators
- Bulk operations for series management

### Enhanced Form Layout

**Master Appointment Form:**
```
┌─ Recurring Appointment Settings ────────────────────────────┐
│ ☐ Repeat this Appointment                                   │
│                                                              │
│ Pattern: Every [1] [weeks ▼] for [12] occurrences          │
│ End Date: [Optional override date]                          │
│                                                              │
│ Weekly Schedule (when applicable):                           │
│ ☐ Mon ☐ Tue ☐ Wed ☐ Thu ☐ Fri ☐ Sat ☐ Sun                │
│                                                              │
│ Series Preview: [Show Next 10] [Show All] [Check Conflicts] │
│                                                              │
│ Status: 8 of 12 appointments completed                       │
│ Exceptions: 2 cancelled, 1 rescheduled                      │
└──────────────────────────────────────────────────────────────┘
```

**Virtual Instance Interaction:**
```
Calendar View → Click Virtual Instance → Context Menu:
├─ View Details (read-only virtual data)
├─ Edit This Occurrence (materializes instance)
├─ Cancel This Occurrence (creates exception)
├─ Reschedule This Occurrence (materializes + reschedules)
└─ View Entire Series (navigate to master)
```

## 4. Materialization Trigger System

### Automatic Materialization Events

**User-Initiated Actions:**
- Edit specific occurrence details
- Cancel individual appointment
- Reschedule specific date
- Add notes to specific occurrence
- Check-in patient for specific date
- Generate invoice for specific appointment

**System-Initiated Actions:**
- Billing cycle processing
- Insurance claim generation
- External system integration requirements
- Audit trail requirements
- Compliance reporting needs

**Materialization Process:**
1. **Trigger Detection**: System identifies need for real instance
2. **Virtual Instance Lookup**: Generate virtual data for target date
3. **Conflict Validation**: Check for real-time conflicts
4. **Instance Creation**: Create full Patient Appointment record
5. **Exception Recording**: Link master to materialized instance
6. **Calendar Event**: Create associated Event record
7. **Cache Invalidation**: Update virtual generation cache

## 5. Enhanced Calendar Integration

### Hybrid Event Generation

**Modified get_events Function Logic:**
```
Calendar Request (start_date, end_date) →
├─ Query Regular Appointments (non-recurring)
├─ Query Materialized Recurring Instances
├─ Query Master Recurring Appointments
├─ Generate Virtual Instances for Masters
├─ Apply Exception Filters
├─ Merge All Sources
└─ Return Unified Event List
```

**Event Object Enhancement:**
- Add `is_virtual` flag for virtual instances
- Include `master_appointment_id` for series identification
- Provide `materialization_url` for on-demand creation
- Support series-level operations in calendar context menu

### Visual Differentiation

**Calendar Display Strategy:**
- Virtual instances: Subtle styling (lighter colors, dotted borders)
- Materialized instances: Standard styling
- Exception indicators: Icons for cancelled/modified
- Series grouping: Visual connection between related appointments

## 6. Exception Management System

### Exception Types & Handling

**Cancellation Exceptions:**
```
Type: Cancelled
Data: {reason: "Patient unavailable", cancelled_by: "user_id"}
Effect: Virtual generator skips this date
Materialization: Not required (lightweight operation)
```

**Modification Exceptions:**
```
Type: Modified
Data: {original_time: "10:00", new_time: "14:00", field_changes: {...}}
Effect: Virtual generator applies modifications
Materialization: Required for persistence
```

**Rescheduling Exceptions:**
```
Type: Rescheduled
Data: {original_date: "2024-01-15", new_date: "2024-01-16", reason: "..."}
Effect: Virtual generator moves occurrence
Materialization: Required for new date
```

**Additional Exceptions:**
```
Type: Additional
Data: {extra_date: "2024-01-20", reason: "Makeup session"}
Effect: Virtual generator adds extra occurrence
Materialization: Required for persistence
```

### Exception Resolution Hierarchy

**Priority Order:**
1. **Materialized Instances** (highest priority - real data)
2. **Active Exceptions** (modifications to virtual instances)
3. **Master Pattern** (default recurring behavior)
4. **System Defaults** (fallback values)

## 7. Conflict Detection & Management

### Real-Time Conflict Checking

**Virtual Instance Conflicts:**
- Check during calendar display generation
- Validate against existing appointments
- Show warnings without blocking display
- Provide conflict resolution suggestions

**Materialization Conflicts:**
- Strict validation during instance creation
- Block creation if hard conflicts exist
- Offer alternative time slots
- Support override for authorized users

### Conflict Types & Responses

**Practitioner Conflicts:**
- **Detection**: Check practitioner availability for virtual dates
- **Response**: Highlight conflicts, suggest alternatives
- **Resolution**: Reschedule or change practitioner

**Resource Conflicts:**
- **Detection**: Validate service unit capacity
- **Response**: Show capacity warnings
- **Resolution**: Queue management or resource reallocation

**Patient Conflicts:**
- **Detection**: Check patient's existing appointments
- **Response**: Prevent double-booking
- **Resolution**: Automatic rescheduling suggestions

## 8. Performance Optimization Strategy

### Efficient Query Patterns

**Master Appointment Queries:**
```sql
-- Optimized master lookup for date range
SELECT * FROM `tabPatient Appointment` 
WHERE repeat_this_appointment = 1 
AND is_recurring_master = 1
AND appointment_date <= @end_date
AND (repeat_till IS NULL OR repeat_till >= @start_date)
AND status != 'Cancelled'
```

**Exception Batch Loading:**
```sql
-- Load all exceptions for masters in one query
SELECT * FROM `tabPatient Appointment Exception`
WHERE master_appointment IN (@master_ids)
AND exception_date BETWEEN @start_date AND @end_date
AND exception_status = 'Active'
```

### Caching Architecture

**Multi-Level Caching:**
- **L1 Cache**: In-memory virtual instances for current session
- **L2 Cache**: Redis cache for frequently accessed date ranges
- **L3 Cache**: Database-level query result caching
- **Smart Invalidation**: Targeted cache clearing on changes

**Cache Warming Strategy:**
- Pre-generate virtual instances for next 30 days
- Background processing for long-term series
- User-specific cache optimization
- Peak-time cache preparation

## 9. Bulk Operations Design

### Series-Level Operations

**Update All Future:**
- Modify master appointment pattern
- Invalidate virtual instance cache
- Update materialized instances if needed
- Create bulk exception records for changes

**Cancel Remaining:**
- Create bulk cancellation exceptions
- Update master appointment status
- Preserve completed appointments
- Handle billing implications

**Reschedule Series:**
- Calculate new occurrence dates
- Check bulk conflicts
- Create rescheduling exceptions
- Update calendar events for materialized instances

### Mixed Instance Operations

**Bulk Selection Handling:**
- Support selection across virtual and materialized instances
- Materialize virtual instances before bulk operations
- Maintain transaction consistency
- Provide operation preview before execution

## 10. Integration & Compatibility

### Healthcare Module Integration

**Fee Validity Management:**
- Virtual instances inherit fee validity from master
- Materialized instances can have individual fee validity
- Exception handling for payment modifications

**Therapy Session Planning:**
- Support recurring therapy appointments
- Track session completion across virtual/real instances
- Handle therapy plan progression

**Clinical Procedure Scheduling:**
- Recurring procedure appointments
- Equipment and resource allocation
- Compliance tracking across series

### External System Integration

**Google Calendar Sync:**
- Sync only materialized instances
- Provide series-level calendar entries
- Handle exception synchronization

**Billing System Integration:**
- Generate invoices for materialized instances
- Support series-level billing setup
- Handle exception-based adjustments

## 11. Migration & Rollout Strategy

### Existing Data Handling

**Current Recurring Appointments:**
- Identify existing recurring patterns
- Convert to master appointment format
- Preserve existing instances as materialized
- Create exception records for modifications

**Gradual Feature Rollout:**
- Phase 1: Basic virtual instance display
- Phase 2: Materialization and exceptions
- Phase 3: Advanced bulk operations
- Phase 4: Full integration and optimization

### Backward Compatibility

**Legacy Support:**
- Maintain existing appointment functionality
- Support mixed environments (virtual + traditional)
- Provide migration tools for existing data
- Ensure API compatibility

This hybrid design provides optimal performance through virtual instances while maintaining full functionality through selective materialization, creating a scalable and efficient recurring appointment system that leverages Frappe's existing Event patterns without requiring core modifications.
