










 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 

 
 
 
 
 
 
 

 
 
 
 
 
 






Contents
Introduction	3
Objective	3
Story	3
Functional Requirements	4
Patient Management:	6
Invoicing:	6
Patient Encounter Management:	8
Medicine prescription	9
Therapy Plan Integration	9
Financial Management:	10
Reporting and Analytics:	10
Integration Requirements:	10
Patient Registration Fields:	10
Naming series of Patient ID	12
Naming series of Practitioner	13
Invoice Service: -   Invoice-Service.docx	16
Invoice Product: - Invoice- Product.docx	16
2. Features for Junior Doctor Role	22
3 . Features for Therapist Role	23
4. Features for Ayurveda Doctor Role	24
4.10 Patient Assessment form	27
4.11 Pharmacy Inventory Management	43











Introduction
This document outlines the business requirements for the implementation of the ERP Next system. The goal is to streamline the organization’s Ayurveda operations, including patient management, medical billing, human resources, inventory management, and financial reporting, by utilizing ERP Next. The system will provide real-time data, automation, and improved reporting capabilities to enhance operational efficiency and patient care.


Objective
Automate Healthcare Operations: Streamline administrative and operational processes, including patient admissions, billing, appointment scheduling, and inventory management.
Centralized Data Management: Create a single platform that integrates patient data, financial records, human resources, and inventory data for better visibility and reporting.
Enhanced Reporting & Decision Making: Improve reporting capabilities with real-time dashboards, allowing better decision-making for hospital administrators and healthcare providers.
Story
A patient walks into the Ayurvedic clinic for the first time and approaches the front desk. The receptionist warmly welcomes them and registers their basic details like name, contact number, and reason for visit. Based on availability, the receptionist then books an appointment for the patient with a doctor on a suitable date and time.
On the day of the appointment, the patient arrives at the clinic and meets the junior doctor. During this first consultation, the junior doctor listens to the patient's symptoms and health concerns, then fills out an “encounter form” in the system with all relevant information.
Once the junior doctor completes the entry, the patient is sent to consult the senior doctor. The senior doctor carefully reviews the junior doctor’s notes and may ask additional questions. After assessing the condition, the senior doctor prescribes a set of therapy sessions — this could include massages, herbal oil treatments, detox procedures, or other Ayurvedic practices tailored to the patient’s needs. The senior doctor finalizes and submits the complete encounter into the system.
The patient then returns to the front desk to schedule therapy sessions as per the doctor’s recommendation. Based on slot availability and the patient's preferences, appointments for each session are booked. The clinic’s policy requires the patient to pay upfront for all the prescribed therapy sessions. Once payment is made, the system generates a detailed invoice showing all therapies, dates, and total charges — including applicable taxes like GST.
As each therapy session is conducted by a trained therapist, they follow the prescribed treatment plan. After every session, the junior doctor logs the patient’s progress notes in the system to track improvements and adjust plans if needed.
Behind the scenes, every time a therapy session uses medicines or oils, the therapist or staff records the quantity used. These transactions are automatically reflected in the pharmacy’s inventory system in real time, ensuring accurate stock tracking.
This process ensures a smooth, professional experience for the patient, while keeping inventory usage transparent and up-to-date.



















Functional Requirements
Schematic work flow Ayurveda
	


3.1. Functional Requirements
Patient Management:
Patient Registration: The system should allow for the creation of patient profiles, including personal information (name, contact details, address
Appointment Scheduling: The system should allow healthcare providers to schedule, reschedule, and cancel appointments for consultation and therapy scheduling. 
Patient Records Management: The system should track patient visits, diagnoses, treatment history, prescriptions (medicines, investigations) and treatment plan and progress notes.
Patient notifications
Trigger
Content


Patient registration
TBD


Patient appointment scheduled
TBD


Patient appointment cancelled
TBD


Patient appointment rescheduled
TBD




Invoicing:
According to the process when the patient is coming for consulting the doctor and the patient has taken appointment. The invoice process will be initiated by the front desk user. According to the business rule before rendering any service to the patient there should be payment collection. 
Billing Business rules 
TBD


Billing: The ERPNext system should allow for billing of various clinical services, like doctor consultations, and therapies. The system should be able to create and track invoices for each patient. The Invoice print should be displaying 0 Value. The invoice needs to include company details and CIN. 

Sample Invoice print

Figure 1Sample Invoice (Consultation)

Figure 2 Sample Invoice (therapy)

Payment Processing:  The patient can opt for paying in various mode like cash, credit or debit card or UPI.
The system will need to be allowing multiple modes of payment like UPI, Cash, Razor Pay (Online payment using Razor pay). The patient /consumer would be able to use Razor pay where an sms will be sent to the patients mobile number with the payment link. Using the link the patient would be able to pay. Post successful completion of the payment the transactions id will be automatically copied in the respective sales invoice
Patient Encounter Management:
Encounter Creation: The system should allow healthcare providers to create an encounter for each patient and doctors meeting, where the clinician will be able to take the patients problems, history and examine the patient to conclude on a diagnosis. And accordingly plan the treatment. 
The process of consulation can broadly be divided into Preconsultation and Consultation. In the pre consultation phase the patient will be consulting with the Assisting doctor. The assisting doctor will enquire and log the complains history and physical examination findings and may be establish diagnosis. After this Consultation phase commences the primary consulting doctor meets the patient and reviews the complains, history and findings. Based on the information the primary consulting doctor will be creating a personalized treatment plan. 
Encounter Details: The encounter should capture important data such as: [TBD awaiting mail from Midhun]
Encounter Billing: The system should automatically link the patient encounter to billing, ensuring that all services rendered during the visit (consultation, treatments) are billed accurately.
Patient History in Encounter: When a new encounter is created, the system should automatically pull relevant Patient History data (e.g., previous diagnoses, allergies, medications) to help doctors create more accurate treatment plans. Healthcare providers should also be able to add to the patient’s history during an encounter (e.g., new diagnoses, treatments, changes in medical conditions).
Progress Tracking: The system should track the progress of ongoing medical conditions, treatments, and therapy plans over time, showing the evolution of the patient’s health.

Medicine prescription
The clinician should be able to prescribe for the ayurvedic medicines by selecting the name of the medicine. Should also be able to select the dosage and frequency of the medicine. The medicines when prescribed should automatically be landing in the Pharmacy module so that the pharmacy will be able dispense the medications. 
Therapy Plan Integration
A clinician should be able to plan the treatment of the patient. When prescribing the clinician should be able select from a list the available therapies. Should also be able to log quantity of the treatment. Post selection of the therapies the clinician should be able to view the default duration of each therapy. [Frequency and startdate of the treatment TBD post discussion with HH Ayurveda Team]
Type of Therapy: Specify the type of therapy being prescribed 
Frequency and Duration: Include the frequency (e.g., 3 times a week) and duration (e.g., 4 weeks) of therapy sessions.
Therapy Sessions: Log details of each therapy session, including notes on progress, changes in treatment plan, and any adjustments to the therapy goals.
Patient Progress: Track the patient’s progress during therapy, including assessment of improvements or setbacks, are documented at regular intervals (e.g., weekly). Need to have a provision to allow the clinicians to use progress note so that the clinician, the therapist and if same patient is consulted by any other clinician also can communicate
Follow-up Plan: Establish follow-up sessions for progress reviews. So that the clinician can review and adjust the therapy plan

Once the patient meeting with the patient is complete, the front desk should be able to give a print of the ‘Patient Report’ and ‘patient precription’. The above said reports should be printed on the Letter head of the clinic [TBD to be confirmed by Happiest Health team]
Patient notification event
The patient report and patient prescription will be sent to the patient’s whatapp number as an attachment. 
Encounters & Medical History: The system should link patient encounters to the broader medical history, showing a timeline of past visits, diagnoses, treatments, and ongoing care plans.

Financial Management:
Accounting: The ERP system should manage financial accounts, including revenue, expenses, and financial reporting.
Reporting and Analytics:
Dashboard: Provide a customizable dashboard for administrators to view key metrics such as patient volume, clinics, doctors and revenue.
TBD 
Need to have the data of therapist, clinic, referred practitioner, doctor for every invoice to analyze the data/bookings happening individually.
Integration Requirements:
Third-party System Integration: Integrate with external healthcare systems for ayurveda database.
Payment Gateway Integration: Integrate with payment gateways to allow patients to make payments online via credit card, debit card, or other payment methods. We also need to integrate with POS for offline payment collections.
Patient Registration Fields: 
Note: The following data fields need to be added:
• Current address/location of the patient.
• Customer attender details (for minors).
• Identification number (Aadhar/PAN card).
 
Field Names
Displayed in UI
Mandatory
First Name
Present
Yes
Gender
Present
yes
Middle Name (optional)
Present


Last Name
Present
 yes
Full Name
 
 yes
Blood Group
Present
 
Date of birth
Present
 yes
Image
 
 
Status
 
 yes
Referred by




PHR Address
 
 
ABHA Number
 
 
Aadhar/PAN.
Present
 
Inpatient Record
 
 
Inpatient Status
 
 
Report Preference
Present
 
Mobile
Present
 Yes
Phone
Present
 
Email
Present
 Yes
Invite as User
Present
 
User ID
 
 
Customer
 
 
Customer Group
 
 
Territory
 
 
Billing Currency
 
 
Default Price List
 
 Yes
Print Language
 
 
Patient Details
Present
 
ABHA Card
 
 
Consent For Aadhaar Use
 
 
Occupation
 
 
Marital Status
 


Allergies
 
 
Medication
 
 
Medical History
 
 
Surgical History
 
 
Tobacco Consumption (Past)
 
 
Tobacco Consumption (Present)
 
 
Alcohol Consumption (Past)
 
 
Alcohol Consumption (Present)
 
 
Occupational Hazards and Environmental Factors
 
 
Other Risk Factors
 
 
ID (Patient Relation)
 
 
Description (Patient Relation)
 
 
Patient (Patient Relation)
 
 
Relation (Patient Relation)
 
 


Referred by section should contain the options of self, social media, website, print advertisement, doctor others etc. options should be present. Others option should have a text box when selected on it. This is a optional field and should be filled in during the registration form by the front desk people. If the doctor option is selected, then there should be a text box to enter the doctor’s name.
If a patient does not have an email id, a default email id should be added, and the details should be shared to that email id.
First name, Last name, email, Mobile number, gender, dob, referred by should be main fields that should be shown to the front desk users while filling at the top.
Identification to be renamed to Aadhar/PAN which is an optional field.
Prevention of Duplicate records during registration Link
 Naming series of Patient ID
The Naming series should contain the details in the following way: -
  
Name
Format
Timestamp driven
HHYYMMDDHHmiss
Ex: HH250217121810

 
The HHYYMMDDHHmiss format is a structured and organized naming system designed for easy identification and sorting of files or data based on date and time. It can be broken down into several components, each with its specific meaning:
HH (Happiest Health):
The "HH" at the beginning of the naming convention stands for "Happiest Health". This prefix identifies that the file or data belongs to the "Happiest Health" series, ensuring that files related to this initiative are easily recognized and categorized.
YY (Year):
"YY" represents the two-digit year when the event or data point was recorded. For example, "25" would represent the year 2025. This helps in categorizing data by the year for time-based sorting or analysis.
MM (Month):
"MM" indicates the two-digit month of the year. For instance, "01" would represent January, "12" would represent December, and so on. This provides the necessary level of granularity to organize files or data monthly.
DD (Date):
"DD" specifies the day of the month when the event or data was recorded. For example, "15" would mean the 15th day of the month. This helps in pinpointing the exact date within the month.
HH (Hours):
"HH" stands for the two-digit hour when the event occurred or the data was recorded. It follows the 24-hour clock format. For example, "08" would represent 8 AM, and "20" would represent 8 PM.
MI (Minutes):
"MI" indicates the two-digit minute at which the event or data point was recorded. For example, "05" would represent 5 minutes past the hour.
SS (Seconds):
"SS" shows the two-digit seconds at which the event was recorded, such as "30" for 30 seconds. This provides an additional layer of precision for time-sensitive data.
Example:
Let's say you have a file created on March 15, 2025, at 2:30:45 PM. The naming convention would be structured as:
HHYYMMDDHHmiss
HH (Happiest Health) - "HH"
YY (Year) - "25" (for 2023)
MM (Month) - "03" (for March)
DD (Date) - "15" (the 15th of the month)
HH (Hour) - "14" (for 2 PM, in 24-hour format)
MI (Minutes) - "30" (30 minutes)
SS (Seconds) - "45" (45 seconds)
Thus, the complete name would be: HH250315143045.
Naming series of Practitioner
Practitioner ID Format:
The Practitioner ID should follow this format:
Prac-<Specialization Code>-<Unique Sequential Number>
Where:
Prac: A fixed prefix indicating that the ID is associated with a practitioner.
<Specialization Code>: A 2-3 character code representing the practitioner's specialty.
<Unique Sequential Number>: A 4-digit sequential number that increases with each new practitioner, irrespective of the specialty.
 
. Specialization Codes:
Each practitioner will be identified by a specialization code, which corresponds to the practitioner's field of expertise:
Specialization
Specialization Code
Physiotherapy
PT
Ear, Nose, and Throat (Otolaryngology)
ENT
Ayurveda
AY
Ophthalmology
OPT
General Dentistry
GD

PT: Physiotherapy practitioners will use the code PT.
ENT: Ear, Nose, and Throat practitioners will use ENT.
OPT: Ophthalmology practitioners will use OPT.
GD: General Dentistry practitioners will use GD.
AY: Ayurveda practitioners can use AY
Example IDs:
Prac-PT-0001: First practitioner registered (could be in Physiotherapy, ENT, Ophthalmology, or Dentistry).
Prac-ENT-0002: Second practitioner registered (could be from any specialty).
Prac-OPT-0003: Third practitioner registered.
Prac-GD-0004: Fourth practitioner registered.
 
3. Detailed Breakdown of the Practitioner ID Format:
Prefix (Prac):
"Prac" is a fixed prefix used for all practitioner IDs to indicate that the ID corresponds to a practitioner. The prefix will remain consistent across all IDs.
Specialization Code:
The specialization code is a 2-3 character string representing the practitioner’s field of expertise. It will be uppercase (e.g., PT, ENT, OPT, GD,AY).
The specialization code will remain consistent with the practitioner's specialty and will not change once assigned.
Unique Sequential Identifier:
The unique identifier is a 4-digit number that increments sequentially with each new practitioner, starting from 0001 and continuing without resetting.
The number is global and does not restart for each specialization. This means that if there are 10 practitioners across various specializations, the 10th practitioner will have the ID Prac-PT-0010 or any other specialization depending on registration order.
The 4-digit identifier will be padded with leading zeros (e.g., 0002, 0050, etc.).
 
4. System Requirements:
Sequential ID Generation:
The system should generate a unique sequential number for each new practitioner, regardless of the specialty. The number should start at 0001 and increment by one for each new practitioner added.
The sequence should increase continuously without resetting for each new specialty.
Unique Identifier Validation:
The system must ensure that the Practitioner ID is unique across the entire system. No two practitioners can have the same ID, regardless of their specialty.
ID Assignment:
When a new practitioner is registered, the system should automatically assign the next available ID. For example: 
The first practitioner (of any specialty) would receive Prac-PT-0001.
The second practitioner (could be from any specialty) would receive Prac-ENT-0002.
The third practitioner would receive Prac-OPT-0003, and so on.
 
Search and Sorting:
The system should allow searching and sorting of practitioners by their ID and specialization. Since the IDs are sequential, sorting them by ID will provide the correct order of practitioner registration.
Deleted Practitioners:
When a practitioner is deleted, their Practitioner ID is not reused. The system will retain the deleted practitioner's ID for historical purposes but will not assign it to new practitioners.
Deleted practitioner IDs will not be available for reuse, ensuring the sequence remains intact.
No Resetting of Numbering:
The 4-digit sequential numbering will not reset with the addition of each new specialization. IDs will continue incrementing regardless of the practitioner’s specialty.
 
5. Example Scenarios:
Scenario 1: Adding the First Practitioner
A new Physiotherapy practitioner is added. Their Practitioner ID is Prac-PT-0001.
Scenario 2: Adding the Second Practitioner
The next practitioner added is an ENT specialist. Their Practitioner ID is Prac-ENT-0002.
Scenario 3: Adding the Third Practitioner
A new Ophthalmology practitioner is registered. Their Practitioner ID is Prac-OPT-0003.
Scenario 4: Adding the Fourth Practitioner
A new General Dentistry practitioner is registered. Their Practitioner ID is Prac-GD-0004.
Scenario 5: Practitioner Deletion
If Prac-ENT-0002 is deleted, the next new practitioner (regardless of specialty) would receive the next sequential ID, which could be Prac-PT-0005. The ID Prac-ENT-0002 will not be reused.


Invoice Service: -   Invoice-Service.docx
Invoice Product: - Invoice- Product.docx
Note: - Referring to the Practitioner one will be a text field.

User Role and Privileges

1.Front Desk: -  

1.1 Patient Registration
1.1.1 Patient Information Collection
The front desk staff will collect the following information from the patient:
Personal Information: Full Name, Date of Birth, Gender, Contact Information (phone number, email address), referred by, etc. detailed fields are mentioned in Patient Registration section.
Insurance Information: Insurance provider, policy number, group number (if applicable).
1.1.2 Registration System Integration
The front desk staff will input the collected information into the patient registration system.
The system will automatically verify data and alert the front desk staff to any missing or incomplete information.
The system will generate a Patient ID which will be assigned to the patient and used for all future medical visits.
They will be able to modify patient details and also search for patient details.
1.1.3 Verification and Confirmation
Once the data is entered into the system, the front desk staff will review the information for completeness and accuracy.
The patient will receive a summary of their registration details (either verbally or in writing) and will confirm that the information is correct. 
The patient will also be receiving the notification via email, WhatsApp, SMS.
In case of any errors or discrepancies, the front desk staff will update the information in the system.
1.1.4 Privacy and Compliance
The system will ensure that the data is securely stored and only accessible to authorized personnel.

1.2 Appointment Scheduling (New. Reschedule, Cancel)
1.2.1 Appointment Creation
Front desk staff will access the clinic’s appointment scheduling system to create new patient appointments.
Steps to Schedule an Appointment:
Front desk staff collect basic patient information (if not already in the system).
Front desk staff selects the type of service (e.g., consultation, therapy) and preferred doctor.
The system will display the available time slots for the selected doctor based on their availability.
The system will also display available consultation rooms for the selected time slot.
Front desk staff will assign an available consultation room for the appointment.
Front desk staff will select an available slot and confirm the appointment with the patient.
Appointment details (date, time, provider, reason for visit, and assigned consultation room) will be entered into the system and saved to the patient’s record
1.2.2 Appointment Modification and Rescheduling
Steps for Modifying or Rescheduling:
Front desk staff will search for an existing appointment by patient name or appointment ID.
Once the appointment is located, the staff can modify details such as the appointment date and time.
The system will show the updated availability, and the front desk staff will select an available consultation room and slot.
The patient will be notified of the rescheduled time, and a confirmation message will be sent to the patient’s contact method (e.g., WhatsApp, email, SMS).
1.2.3 Appointment Cancellation
Steps for Cancellation:
The front desk staff will search for the patient’s scheduled appointment.
Upon selecting the appointment, staff will initiate the cancellation process.
The patient will be informed of the cancellation, and the appointment will be removed from the system.
If needed, the front desk staff will offer the patient an alternative appointment slot or suggest re-scheduling.1.2.4 Appointment Confirmation and Reminders
After scheduling an appointment, the system will automatically send a confirmation message to the patient (via WhatsApp, email, or SMS) containing the appointment details (date, time, provider, location).
Notifications will be sent to the user for patient registration, patient appointment confirmation, appointment reschedule and cancellation, reminder for appointment, patient prescription and report and patient invoice. 
Reminder Notifications: The system will also send appointment reminders to the patient at predefined intervals (e.g., 24 hours before the appointment) to reduce no-shows and ensure timely arrival.
1.2.5 Doctor Availability Management
Front desk staff will have the ability to view and manage the availability of healthcare doctors. This can include:
Checking a doctor's available time slots.
Scheduling appointments based on doctors' availability.
Blocking out times when a doctor is unavailable (e.g., vacations, holidays, breaks).

1.3 Access Patient List
The front desk staff will be able to access the patient list via the appointment scheduling. The list should be updated in real-time to reflect the latest patient data and appointments.
The front desk should be able to search and sort the patient list and also the appointment list.
Data Permissions: Front desk staff will have access to basic patient details but may have restricted access to sensitive information (e.g., diagnosis, medical history) based on role-based access controls and compliance with privacy laws (e.g., HIPAA).
1.4 Capture initial encounter data
The front desk staff will be able to access the patient encounter list. The front desk should be able to click on an encounter data go inside it and click on save only.
The front desk users will be able to print the patient report and prescription report so that print can be provided to patients.
1.5 Service Sales and Product Sales – Generate Invoices collect payments
1.5.1 Generating an Invoice
Process:
Accessing Patient Appointment Information: Front desk staff will access the patient's appointment or service details from the patient management system.
Service Selection: The staff will select the services rendered (e.g., consultation, therapy)
Invoice Creation: The system will automatically generate an invoice containing the following details: can follow the above invoice format 
Review and Confirmation: The front desk staff will review the invoice for accuracy before presenting it to the patient. Any errors will be corrected before proceeding.
1.5.2 Payment Collection
Process:
Front end user will be collecting the complete amount for consultation and the therapy sessions at one time. No partial payment is allowed.
Payment Method Selection: Front desk staff will present the available payment methods to the patient (e.g., credit/debit card, cash, razor pay link).
Processing Payment:
Cash Payment: The staff will collect the cash and issue a receipt to the patient for the amount paid.
Card Payment: The front desk staff will swipe or input the patient's card details, process the payment through a secure payment gateway, and receive confirmation of successful payment.
Razor pay : The front desk staff will be able to generate the Razor pay link, which in turn will be sent to the patient mobile number so that patient can complete the payment. 
POS – The front desk staff will be able collect the amount using the bank POS machines so that the patient can complete the payment. 
Payment Confirmation: Once the payment is processed successfully, the system will update the patient’s record with the payment details and send a invoice cum receipt to the patient (via WhatsApp, print, email, or SMS).
1.5.3 Payment Methods
Accepted Payment Methods: The system will support multiple payment methods:
Credit/Debit Cards (Visa, MasterCard, American Express, etc.)
Cash Payments
Digital Wallets or Mobile Payments (if applicable)
Razor pay: - Online Payment Portal (if the system supports online patient payment). User receives the payment link.
POS Integration: The system will integrate with physical Point of Sale (POS) terminals to process in-person payments. This allows front desk users to accept payments using credit/debit cards, mobile wallets, and other supported methods at the time of service.
Supported Devices: The POS system will work with standard card readers (magstripe, EMV, and NFC-enabled devices) to ensure a smooth and secure transaction process.
The transaction id is mandatory for Razor pay and POS payments in the sales invoice.

1.5.4 Generating Receipts
Receipt Details: After payment is processed, the system will generate a receipt based on the format mentioned above for product and services invoices.
Receipt Delivery: The front desk staff will provide the receipt to the patient in the preferred format (printed, email, WhatsApp or SMS).
1.5.5 Handling Refunds and Adjustments
Refund Process: In the event of an overpayment or cancellation of services, the front desk staff will initiate the refund process. This will involve:
Verifying the payment history for accuracy.
Determining the amount to be refunded.
Processing the refund through the same payment method (credit/debit card, cash, razorpay etc.).
Updating the patient’s record and generating a refund receipt for the patient.
Invoice Adjustments: If there is a need to adjust the invoice (e.g., billing error, discount application), the front desk staff will update the invoice and notify the patient of any changes.
1.6 Access Dashboard & reports related to Appointments, Sales

1.6.1 Appointments Data:
Appointment Overview: Total number of appointments scheduled, canceled, or completed within a specified period (e.g., daily, weekly, monthly).
Scheduled Appointments: Number of appointments for the current day or week.
Appointment Status: Breakdown of appointments by status (e.g., confirmed, checked-in, no-show, canceled).
Upcoming Appointments: List of scheduled appointments for the day or upcoming days, including patient name, time, and healthcare provider.
Appointment Type Breakdown: Categorization of appointments by type of service or provider (e.g., consultations, therapy).
1.6.2 Sales Data:
Total Sales: Total revenue generated for the day, week, or month.
Payment Method Breakdown: Overview of payments by method (e.g., credit card, cash, insurance).
Service Sales: Breakdown of revenue by specific services rendered (e.g., consultation fees, therapies).
Patient Payment Status: Overview of payments collected, outstanding balances, and pending invoices.
Refunds/Adjustments: Total amount of refunds or adjustments made during a specified period.
1.6.3 Report Generation
Customizable Reports: Front desk staff should be able to generate reports based on customizable criteria, such as:
Time Range: Generate reports for specific time periods (e.g., daily, weekly, monthly, custom date range).
Doctor:  the ability to filter reports by specific doctor.
Consultation rooms: the ability to filter reports by specific consultation rooms.
Service Type: View reports broken down by the type of service provided (e.g., consultation, therapy).
Appointment Status: Generate reports for specific appointment statuses (e.g., completed, canceled, no-shows).
Report Types:
Appointment Reports:
Number of appointments scheduled vs. completed.
Appointment no-show rates.
Cancellations and rescheduling trends.
Sales Reports:
Total revenue generated from appointments.
Breakdown of payments received by method (e.g., credit card, insurance, cash).
Trends in services sold or revenue generated by service category.
Consultation Room Occupancy Reports:
Room Utilization Rate: Percentage of time each consultation room is occupied during working hours.
Average Occupancy Duration: Average time each appointment occupies a specific consultation room.
Peak Usage Hours: Time periods with the highest consultation room usage.
Idle Time Analysis: Time periods when rooms are unoccupied or underutilized.
Room Conflict Reports: Identify any double-bookings or scheduling conflicts.
Usage by Service Type: Distribution of room use based on types of services provided (e.g., consultation, therapy).

Exporting Reports: Front desk staff should have the ability to export reports in common formats (e.g., PDF) for further analysis or distribution to management.
1.6.4 Data Filters and Sorting
Data Filters: Front desk staff can filter the data displayed on the dashboard or in reports based on the following criteria:
Time Period: Filter data by specific days, weeks, months, or custom date ranges.
Doctor: Filter by healthcare doctor to see their appointment and sales performance.
Consultation rooms: - Filter by consultation rooms to see their appointment and sales performance
Appointment Type: Filter by service or treatment type to see related data.
Sorting: The dashboard should allow front desk staff to sort the data based on:
Appointment date and time.
Sales value (from highest to lowest).
Payment method (e.g., cash, credit card).

2. Features for Assisting Doctors role
The assisting doctors should be able to perform following actions in the PMS application. 
1. Create and modify the patient encounter. The patient encounter document can be saved as draft. Print and view the patient report and patient prescription
2. Create vital records
3.  The junior doctors will be able to create and modify the therapy plan
In addition to the above the junior doctors will be able to perform all the actions that the front desk user would be able to do.
2. Features for Junior Doctor Role
The assisting doctors should be able to perform following actions in the PMS application. 
In addition to the above the junior doctors will be able to perform all the actions that the front desk user would be able to do.
Patient Vital Monitoring
The Junior Doctor will have access to vital monitoring tools (e.g., blood pressure cuffs, thermometers, oxygen monitors) to record and update patient vitals in real-time in the patient encounter.
Screenings and Assessments
The Junior Doctor will conduct routine Ayurvedic screenings and assessments to evaluate the patient's health from an Ayurvedic perspective. These screenings may include physical examinations, traditional Ayurvedic diagnostic methods, and assisting in basic Ayurvedic treatments, all under the supervision of more experienced Ayurvedic practitioners or doctors. The focus will be on understanding the patient's dosha (body constitution), prakriti (individual constitution), and identifying any imbalances in the body, mind, or spirit.
Documentation from these screenings will be recorded in the patient’s health record, including any abnormalities or issues identified to be updated in the patient encounter.
Collaboration with Senior Medical Team
The Junior Doctor will act as an assistant in consultations and procedures, ensuring that all medical instructions from senior doctors are followed correctly.
Documentation and Reporting
The Junior Doctor will ensure that all patient interactions and updates are documented accurately in the patient encounter.
Junior doctor will also assist the therapist during the therapy sessions and also record the progress in the progress notes.

3 . Features for Therapist Role
The therapist should be able to perform following actions in the PMS application except the encounter part. Therapist will also be able to manage the pharmacy inventory part. In addition, will be able to perform all the actions that the front desk user, junior doctor, pharmacy user would be able to do.

View Therapy Session Assigned to a Patient & Initial Assessment Details
Description:
Therapists can view the therapy session or treatment plan assigned to each patient and the details of the initial assessment that led to the development of the plan. The therapist will not able to be modify the therapy plans
Therapy Session Management
Description:
Therapists will be able to manage the therapy sessions with their assigned patients, ensuring that sessions are properly scheduled and tracked.
Functional Requirements:
Session Overview: A calendar view will allow therapists to easily see upcoming sessions, including the patient’s name, therapy type, and time.
Session notes:- Therapist will be able to see the notes added by junior doctor during the therapy sessions.
Access Dashboard & Reports Related to Appointments, Clinical (Limited to Patients Assigned)
Description:
Therapists will be able to access a personalized dashboard that provides key metrics and reports on appointments, patient progress, and clinical outcomes for the patients assigned to them.
Functional Requirements:
Dashboard Overview: The dashboard will display key information relevant to the therapist’s assigned patients, including:
Upcoming appointments
Patient attendance
Session progress (e.g., completed, rescheduled, missed)
Patient progress toward treatment goals
Appointment Reports: Therapists can generate reports for the appointments they’ve had with their patients, including session counts, attendance rates, and trends over time.
Clinical Reports: Therapists can generate clinical reports that focus on patient progress, effectiveness of therapies, and treatment outcomes for their assigned patients.
Filter and Sort Options: Therapists can filter the reports by date, therapy type, or patient condition, and sort them based on criteria like session date, attendance, or treatment progress.
Export Reports: Therapists will be able to export appointment and clinical reports in formats such as PDF or Excel for easy sharing or printing.

4. Features for Ayurveda Doctor Role
Doctor user role will be able to perform all the responsibilities of the Front desk and Therapist user role and also perform few additional things like adding patient encounter.
4.1 Access Patient List
Description:
The Ayurveda Doctor will have access to a comprehensive list of all patients under their care, which includes details such as patient demographics, medical history, previous therapies, and appointment history.
Functional Requirements:
View Patient List: Ayurveda doctors can access a list of all patients under their care, with key information such as patient name, age, contact details, and assigned therapist.
Search and Filter: The system will allow doctors to search for specific patients using filters such as name, therapy type, or treatment status.
Patient Overview: Selecting a patient will provide a quick overview of the patient’s medical history, current condition, and previous therapy sessions.

4.2 Initial Assessment
Description:
The Ayurveda Doctor will conduct an assessment of the patient to determine the condition, establish a diagnosis, and prescribe a Ayurveda treatment plan.
Functional Requirements:
Document Assessment: Ayurveda doctors will input the findings from the patient assessment, including symptoms, physical exam results, and medical history.
Create Diagnosis and Treatment Plan: Based on the assessment, the doctor will determine the diagnosis and create a personalized Ayurveda treatment plan, including goals and therapy types 
Referral to Therapist: If necessary, the Ayurveda doctor will assign the patient to a therapist who will carry out the prescribed therapies.
Collaboration with Other Specialists: If required, the Ayurveda doctor may refer the patient to other specialists for further evaluation and treatment.

4.3 Encounter Documentation
Description:
Ayurveda doctors will document the details of each patient encounter, including therapy progress, patient feedback, adjustments to the treatment plan, and any new findings or recommendations. The encounter will also contain a progress note to update it. continuously.
Functional Requirements:
Document Encounter Details: During each patient encounter, Ayurveda doctors will record relevant information such as treatment provided, patient responses, and any changes made to the therapy plan.
Attach Relevant Files: Doctors can attach imaging results, and other documents related to the patient’s treatment and progress.
Update Treatment Plan: If necessary, the doctor will modify the treatment plan to accommodate new findings or changes in the patient's condition.
4.4 Therapy Management
Description:
Ayurveda Doctors will manage and oversee the therapy treatments prescribed to patients, ensuring the treatments are appropriate, tracking progress, and adjusting therapy plans as needed. Doctors can also check the progress notes updated by the therapists.
Functional Requirements:
Monitor Therapy Progress: Doctors can access progress reports from therapists, track patient responses to treatments, and assess whether therapy goals are being met.
Modify Therapy Plan: If the patient is not responding well to the current therapy, the Ayurveda doctor can modify the plan to include alternative approaches, also modify the oils used,  intensify or reduce certain types of therapies, or change the frequency of therapy sessions.
Collaboration with Therapists: The system enables collaboration between the Ayurveda doctor and therapist, allowing the doctor to review session notes and make necessary adjustments to treatment plans.

4.5 View Consolidated Patient Record from All Therapies
Description:
Ayurveda doctors will have access to a consolidated record of all therapies and treatments provided to a patient, regardless of which healthcare provider administered them.
Functional Requirements:
Consolidated Record Access: The system will provide a single view of the patient’s complete medical history, including all therapy treatments, test results, diagnoses, and interventions.
Review of Cross-Therapy Data: The doctor will be able to see how therapies from different providers (e.g., other doctors, therapists, specialists) interact and influence the patient's progress.
Track Comprehensive Patient Progress: This consolidated record enables the Ayurveda doctor to track the effectiveness of the full treatment plan and ensure there are no gaps in care.

4.6 Reschedule Appointments
Description:
Ayurveda doctors can reschedule patient appointments if needed due to unforeseen circumstances such as changes in their schedule or the patient’s condition.
Functional Requirements:
Reschedule Appointments: Ayurveda doctors can modify patient appointment times and ensure the new schedule is updated in the system.
Availability Check: The system will check the availability of the doctor and the therapist (if assigned) to avoid scheduling conflicts.
Notify Patients: After rescheduling, the system will notify the patient of the new appointment time.
Track Appointment Changes: The doctor will be able to see a history of all rescheduled appointments to ensure proper follow-up.

4.8 Generate Patient Report / Prescription Order
Description:
Ayurveda doctors will be responsible for generating reports that summarize patient progress and issuing prescriptions for therapy and other treatments.
Functional Requirements:
Generate Patient Reports: Ayurveda doctors can generate detailed reports on a patient’s therapy progress, including the effectiveness of prescribed therapies and any changes to the treatment plan.
Prescription Orders: Doctors can prescribe necessary therapy sessions, medications, or other interventions. Prescriptions can include detailed instructions such as frequency and duration.
Review Past Prescriptions: The system will allow doctors to view past prescriptions to ensure continuity of care.
Track Prescription Fulfillment: Doctors can verify whether prescribed therapies or medications have been carried out, helping ensure the patient follows the prescribed treatment plan.

4.9 Access Dashboard & Reports Related to Appointments, Clinical, Financial
Description:
Ayurveda doctors will have access to dashboards and reports that provide insight into their appointments, patient clinical outcomes, and financial metrics.
Functional Requirements:
Appointment Dashboard: Doctors can view a visual representation of their scheduled appointments, cancellations, and upcoming patient visits.
Clinical Reports: Ayurveda doctors can access reports showing clinical data, including patient therapy progress, session attendance, and therapy effectiveness.
Financial Reports: Doctors will have access to financial reports that detail their earnings, billings, and the status of payments for their consultations and treatments.
Filter and Sort Reports: The system will allow doctors to filter and sort reports based on different criteria, such as appointment dates, patient progress, or financial performance.
4.10 Patient Assessment form 
V2Ayurveda Initial Assessment sheet
Section Name
Fields
Field type
Status
Attributes


Patient information
Name
Data
Available with patient unique id & full name
Read only




Age
Int
Available
Read only




Gender
Data
Available
Read only




Date (Encounter Date)
Date
Available
Auto filled if the appointment is converted to patient encounter
Consulting and Assisting doctors role can change it


Occupation
Data
Available
Free text field
Only consulting and assisting doctor will be able to add


Contact Number
Data
Available
Read only




Email 
Data
Available
Read only




Address
Link field
Not available




Other encounter related informations
Encounter time
Time


Auto prefilled based on the creation of the encounter




Healthcare Practitioner (Consulting Doctor)
Link
Available
If the encounter is created from the appointment; auto filled from appointment




Department
Link
Available
Auto prefilled based on the Healthcare practitioners medical department




Invoiced
Check box


If the encounter is invoiced. The check box will be ticked.


Chief complaints
Chief complains
Multi line Free text field
Available
The doctors can log the patient illness in the patient’s language




History of present illness
Multi select (SNOMED CT)
Available
The Doctors can log by selecting more than present illness terms




Onset
Drop Down field
Available
Options are 
Acute
Chronic




Associated symptoms
Free text field
New






Aggravating factors
Multi line free text field
Available






Relieving Factors
Multi line free text field
Available




History
Past illness
Multi line free text field
New


The information that is saved here will be saved in patient medical history.


Surgical History
Multi line free text field
Available






Allergies
Multi line free text field
Available






Medication Used (Medication history)
Multi line free text field
Available






Family History of Illness (Family Medical History)
Multi select (SNOMED CT)






Vitals
Weight/Height/BMI


Weight: Decimal
Height: Decimal
BMI: Read only (Auto calculated)
Available


BMI will be auto Calculated from weight and height




Blood Pressure:   
(Blood Pressure (systolic) (In mmHg))
(Blood Pressure (diastolic)(In mmHg))
(Blood Pressure (In mmHg)
Text field (unit: mmHg)
Available








Pulse rate: 
(Heart Rate / Pulse (In bpm))
Int
Available






Temperature: 
(Body Temperature (in °F))
Decimal
Available




General examination
(Physical Examinations)


Digestion
  
Multi select check box
New
selection options are
Normal
Bloating
Acidity
Constipation 
Loose motions    






Bowel Habits
       
Multi select check box
New
selection options are
Regular
Irregular 
Constipation Diarrhea   




Sleep
      
Multi select check box
New


selection options are
Sound 
Disturbed Insomnia   




Energy Levels
Multi select check box


New
selection options are
Good Moderate Low    


Diet & Lifestyle
Typical Daily Diet
Multi line free text field
New








Food Preferences
Multi select check box
New
selection options are
Veg
Non-veg  Mixed  






Food Intolerances
Multi line free text field
New






Exercise Routine
Multi line free text field
New






Investigation ordered:(Investigations)
Investigation
Row
Available


The row contains Observation (dropdown field), & Comment (Multi line textbox)


Diagnosis:
Diagnosis
Drop Down field
Available








Stage of Disease 
Check box
New


Options are
 Acute  Chronic


Treatment Plan
Internal medicines


New






B. External treatments  
Multi line Text Field
New




Follow-up Schedule:  
(Follow-Up Date)
Follow-up Schedule 
(Follow-Up Date)
Date picker
Available









The encounter form will have the following main sections:
4.10.1.1 Patient Information (Section 1) which will be taken from patient registration information.
4.10.1.2 Chief Complaints (Section 2)
This section will capture details related to the patient's primary health issues, providing the Ayurvedic doctor with essential information for diagnosis and treatment.
 Present Illness
Field Type: Text Field
Description: This is where the patient provides a brief description of the current illness they are experiencing.
Validation: Required.
Character Limit: 500 characters (if desired).
History of Present Illness
Field Type: Dropdown (Auto-populated from Drug Database)
Description: This field will auto-populate a list of possible conditions related to the presenting illness, drawn from a drug or medical database.
Validation: Required.
Onset
Field Type: Radio Button (Single Choice)
Options:
Sudden
Gradual
Validation: Required.
Description: This field determines whether the illness appeared suddenly or developed gradually.
Associated Symptoms
Field Type: Text Field
Description: A text input field where the patient or the doctor can describe other symptoms associated with the illness (e.g., fever, nausea, dizziness).
Validation: Optional.
Character Limit: 500 characters (if desired).
Aggravating Factors
Field Type: Text Field
Description: This field captures any factors that make the illness or symptoms worse (e.g., specific foods, stress, weather conditions).
Validation: Optional.
Character Limit: 500 characters (if desired).
Relieving Factors
Field Type: Text Field
Description: This field captures any factors that help reduce or relieve the symptoms (e.g., certain medications, resting, hydration).
Validation: Optional.
Character Limit: 500 characters (if desired).
3.10.1.3 Medical History
This section will gather the patient's past health information, including previous illnesses, surgeries, allergies, current medications, and any family history of illnesses.
Past Illnesses
Field Type: Dropdown (Auto-populated from Medical Database)
Description: A dropdown list that will pull information from a structured medical database, offering a selection of common past illnesses the patient may have experienced.
Validation: Required.
Surgeries
Field Type: Text Field
Description: This field allows the patient or doctor to enter details regarding any surgeries the patient has undergone.
Validation: Optional 
Character Limit: 500 characters (if desired).
Allergies
Field Type: Text Field
Description: A free-text field for listing any known allergies, including food, medication, environmental factors, etc.
Validation: Optional.
Character Limit: 500 characters (if desired).
Medications Used Currently (Allopathic/Ayurvedic/Homeopathy)
Field Type: Text Field
Description: This field allows the patient to provide information about any medications they are currently taking, including allopathic, Ayurvedic, and homeopathic treatments.
Validation: Optional.
Character Limit: 500 characters (if desired).
Family History of Illness
Field Type: Dropdown (Auto-populated from Family Medical History Database)
Description: This dropdown will pull information from a family medical history database and will allow the user to select relevant illnesses that may run in the patient’s family.
Validation: Required.
3.10.1.4 General Examination
This section collects important physical parameters and general health information related to the patient's vital signs, digestion, bowel habits, sleep, and energy levels. This data is crucial for assessing the overall health status of the patient.
Weight/Height/BMI
Field Type:
Weight: Number (with unit of measurement, kg)
Height: Number (with unit of measurement, cm)
BMI: Calculated field based on the weight and height.
Description: This section captures the patient's weight, height, and calculates their BMI (Body Mass Index) automatically.
Validation: Required for both weight and height. BMI will be auto calculated once the weight and height are entered.
Blood Pressure
Field Type: Text Field (with the option for two values: systolic/diastolic)
Description: Blood pressure reading is recorded here, with systolic over diastolic values (e.g., 120/80 mmHg).
Validation: Required, format should be validated (e.g., numbers only, followed by '/' for systolic and diastolic).
Pulse Rate
Field Type: Number Input (with unit of measurement, e.g., beats per minute)
Description: The patient's pulse rate is captured here.
Validation: Required, must be a positive integer.
Temperature
Field Type: Number Input (with unit of measurement, e.g., Celsius or Fahrenheit)
Description: The body temperature is recorded here.
Validation: Optional, format should be validated as a valid temperature range (e.g., 36.5°C, 98.6°F).
Digestion
Field Type: Checkbox (Multiple options)
Options:
Normal
Bloating
Acidity
Constipation
Loose motions
Description: This field assesses the patient's digestive function, with multiple symptoms they may be experiencing.
Validation: Required, at least one option should be selected.
Bowel Habits
Field Type: Checkbox (Multiple options)
Options:
Regular
Irregular
Constipation
Diarrhea
Description: This field gathers information on the patient's bowel habits.
Validation: Required, at least one option should be selected.
Sleep
Field Type: Checkbox (Multiple options)
Options:
Sound
Disturbed
Insomnia
Description: This field gathers information about the patient's sleep patterns and quality of rest.
Validation: Required, at least one option should be selected.
Energy Levels
Field Type: Checkbox (Single choice)
Options:
Good
Moderate
Low
Description: This field assesses the patient's energy levels throughout the day.
Validation: Required, one option must be selected.
3.10.1.5 Diet & Lifestyle
This section documents the patient’s dietary habits and lifestyle choices.
Typical Daily Diet (Text Area)
Field Type: Text (multi-line)
Validation: Optional, describe typical food intake.
Food Preferences (Checkbox)
Options: Veg, Non-veg, Mixed.
Validation: Required.
Food Intolerances (Text Area)
Field Type: Text (multi-line)
Validation: Optional, any specific food intolerances.
Exercise Routine (Text Area)
Field Type: Text (multi-line)
Validation: Optional.
4.10.1.6 Ayurvedic Assessment
This section evaluates the patient’s constitution (Prakriti), current imbalance (Vikriti), digestive fire (Agni), presence of toxins (Ama), and affected body channels (Srotas). It also includes the evaluation of major bodily systems like the nervous, cardiovascular, and respiratory systems.
Prakriti (Body Constitution)
Field Type: Checkbox (Multiple Options)
Options:
Vata
Pitta
Kapha
Dual (Vata-Pitta, Pitta-Kapha, Vata-Kapha)
Tridoshic (Combination of all three doshas)
Description: This field identifies the patient's natural constitution based on Ayurvedic principles. Prakriti reflects the predominant dosha(s) at the time of birth and determines their physical and mental characteristics.
Validation: Required, at least one option should be selected.

Vikriti (Current Imbalance)
Field Type: Checkbox (Multiple Options)
Options:
Vata
Pitta
Kapha
Description: This field identifies the dosha(s) that are currently imbalanced in the patient. Vikriti reflects the present state of health and may vary from the person's Prakriti.
Validation: Required, at least one option should be selected.
Symptoms Observed:
Field Type: Text Field
Description: This text field allows the doctor to note specific symptoms or signs associated with the current doshic imbalance observed in the patient.
Validation: Optional (but helpful for documentation).
Agni (Digestive Fire)
Field Type: Checkbox (Single Choice)
Options:
Sama (Balanced)
Manda (Weak)
Tikshna (Sharp)
Vishama (Irregular)
Description: Agni is the digestive fire in Ayurveda, crucial for proper digestion, absorption, and assimilation of food. The state of Agni reflects the digestive capacity and any imbalances in the digestive system.
Validation: Required, one option should be selected.
Ama (Toxins)
Field Type: Checkbox (Single Choice)
Options:
Present
Absent
Description: Ama refers to undigested food or toxins that accumulate in the body due to impaired digestion or Agni. The presence of Ama is often associated with disease and imbalances in the body.
Validation: Required, one option should be selected.
Signs if Present:
Field Type: Text Field
Description: This field allows the doctor to note the signs or symptoms if Ama is present (e.g., coating on the tongue, foul odor, fatigue, etc.).
Validation: Optional (if Ama is present).
Srotas Affected (Body Channels)
Field Type: Checkbox (Multiple Options)
Options:
Annavaha (Digestive)
Pranavaha (Respiratory)
Rasavaha (Circulatory)
Raktavaha (Blood)
Mamsavaha (Muscular)
Medovaha (Fat)
Asthivaha (Bone)
Majjavaha (Nerve)
Shukravaha (Reproductive)
Manovaha (Mind)
Description: Srotas are the channels or pathways in the body that carry vital fluids. The state of these channels is assessed to determine where the imbalance or blockages might be occurring.
Validation: Required, at least one option should be selected.
Central Nervous System
Field Type: Text Field
Description: This field allows the doctor to make observations about the state of the central nervous system (e.g., symptoms like anxiety, mental clarity, memory issues, etc.).
Validation: Optional (but helpful for comprehensive assessment).

Cardiovascular System
Field Type: Text Field
Description: This field captures any observations regarding the patient's cardiovascular health (e.g., pulse rate, blood pressure, any signs of imbalance like dizziness or shortness of breath).
Validation: Optional (important for checking systemic imbalances).

Respiratory System
Field Type: Text Field
Description: This field allows the doctor to assess the respiratory system's health, including symptoms such as coughing, breathlessness, wheezing, or congestion.
Validation: Optional (but useful for evaluating respiratory health in Ayurvedic terms).
4.10.1.7 Physical Examination / Asta Sthana Pareeksha (Optional)
This section will include a detailed physical examination based on Ayurvedic principles.
Pulse (Nadi Pariksha) (Radio Buttons)
Options: Manda, Sthira, Chapala, Katina, Vega.
Validation: Optional.
Urine (Mootra) (Radio Buttons)
Options: Peetavaranam, Apichilam, etc.
Validation: Optional.
Excretion (Mala) (Radio Buttons)
Options: Shushka, Bhinna, Sandra, Normal.
Validation: Optional.
Tongue (Jihwa) (Radio Buttons)
Options: Krishna, Peeta, Sweta, Patala.
Validation: Optional.
Skin (Sparsha) (Radio Buttons)
Options: Sheeta, Ushna, Ardra.
Validation: Optional.
Sound (Shabda)
Options: Spashtam, Aspashtam, Guru, Anunasika, Pralaapa
Validation: Optional.
Eyes (Drik)
Field Type: Dropdown (Multiple options)
Options:
Vata:
Dhumra
Aruna varna
Ruksha
Chanchal
Pitta:
Thikshna
Dahayukta
Raktavarna
Kapha:
Sweta
Snigdha
Sthira 
Description: The state of the eyes reflects the qualities of the doshas. This examination helps determine whether Vata, Pitta, or Kapha is predominant in the patient based on eye color, moisture, and movement patterns.
Validation: Required, at least one option should be selected for the appropriate dosha.
Body (Akriti) (Radio Buttons)
Options: Krisha, Madhyama, Sthula.
Validation: Optional.
Other Observations (Text field)
4.10.1.8 Diagnosis (Nidana)
This section documents the diagnosis based on Ayurvedic principles.
Dosha Involvement (Checkbox)
Options: Vata, Pitta, Kapha.
Validation: Required.
Dhatu/Affected Tissues (Text Area)
Validation: Required, describe affected tissues.
Mala/Excretory Imbalance (Text Area)
Validation: Required.
Agni Status (Text Area)
Validation: Required.
Ama Presence (Text Area)
Validation: Required.
Provisional Diagnosis (Text Area)
Validation: Required.
Final Diagnosis (Text Area)
Validation: Required.
Stage of Disease (Radio Buttons)
Options: Acute, Chronic.
Validation: Required.
4.10.1.9 Treatment Plan
This section captures the complete therapeutic plan for the patient, including both palliative and purificatory treatments, dietary/lifestyle guidance, integrative practices like yoga, and follow-up schedules.

Shamana (Palliative Treatment)
Field Type: Multi-line Text Field
Description: This field is used to list prescribed Ayurvedic medicines, herbal formulations, dietary adjustments, and any other palliative care advised to the patient.
Validation: Required. Should capture medicine names and dosage instructions where applicable.
Shodhana (Purificatory Therapy)
Poorva Karma
Field Type: Multi-line Text Field
Description: Record preparatory procedures before the main purification therapy, such as snehana (oleation), swedana (sudation), etc.
Validation: Optional.
Pradhana Karma
Field Type: Checkbox (Multiple options)
Options:
Vamana (Emesis therapy)
Virechana (Purgation therapy)
Basti (Enema therapy)
Nasya (Nasal administration)
Raktamokshana (Bloodletting therapy)
Description: These are the main purification therapies prescribed as part of Panchakarma. The doctor selects the appropriate therapy based on the patient’s condition.
Validation: Optional, at least one option can be selected if Shodhana is advised.
Details
Field Type: Multi-line Text Field
Description: Additional notes or instructions for administering the selected purificatory therapy, including duration, materials, and any precautions.
Validation: Optional (Recommended if any purification therapy is selected).
Pathya-Apathya (Recommended Do’s & Don’ts)
Dietary Advice
Field Type: Multi-line Text Field
Description: Specific foods to be consumed or avoided based on the patient's doshic imbalance and health condition.
Validation: Required if dietary changes are advised.
Lifestyle Advice
Field Type: Multi-line Text Field
Description: Lifestyle routines and behavioral suggestions (e.g., sleep patterns, stress management, daily routines) aligned with Ayurvedic principles.
Validation: Optional (Required if relevant to treatment).
Yoga & Meditation (If Prescribed)
Suggested asanas/pranayama:
Field Type: Multi-line Text Field
Description: Recommendations for yoga asanas, pranayama (breathing exercises), and meditation techniques to support treatment.
Validation: Optional (only if yoga/meditation is part of the therapy).
Follow-up Schedule
Field Type: Date Picker / Text Field
Description: Suggested date or time frame for the patient’s next consultation or follow-up. This helps in tracking the progress and making necessary treatment adjustments.
Validation: Required if a follow-up is scheduled.
Notes: Field Type: Text Field


4.11 Pharmacy Inventory Management
Purchase Request (PR)
A Purchase Request is initiated when stock falls below the minimum required quantity. It allows pharmacy staff or doctors to formally request restocking of specific medicines.
Fields include item name, required quantity, requester details, and optional notes.
PR moves through statuses: Draft → Submitted → Approved → Rejected.

Purchase Order (PO)
A PO is generated after PR approval or directly by inventory staff. It is an official document   	sent to vendors for supply.
Fields: PO Number, vendor info, item list, quantities, expected delivery, and payment terms.
PO Statuses: Open, Sent, Partially Received, Closed, Cancelled.

Goods Receipt Note (GRN) / Stock Entry
Upon receiving stock, the GRN confirms the delivery and updates inventory.
Linked to PO and includes batch numbers, expiry dates, and received quantities.
Stock is updated only after verification.

Purchase Invoice
An invoice is recorded once goods are verified.
Includes invoice number, supplier name, tax and discount info, and links to GRN/PO.
Connects to financial systems (if applicable).

 Inventory Management
Central to the system, this manages stock quantities across the lifecycle.
Tracks stock in real time at the batch and expiry level.
Supports transfers, adjustments, and notifications for expiring/low stock.

Billing Module
Handles retail sales and customer billing.
Supports multiple search modes and auto-selects earliest-expiry batches.
Accepts cash, card, or digital payment methods.
Produces a tax-compliant, printable invoice.
Supplier Management
Keeps a directory of medicine vendors.
Stores contact info, tax IDs, banking info.
Tracks past transactions and payments.

Reporting and Analytics
Provides data insights and logs.
Key reports: Stock Ledger, Expiry Report, GRN vs PO, Supplier purchases.
Exportable and schedulable.

Real-Time Tracking of Inventory Levels
The system must track the real-time stock levels of each Ayurvedic medicine in the pharmacy store, updating manually with each transaction.
Usage in therapy sessions (e.g., when a specific quantity is dispensed for patient treatment).
Sales to external customers (e.g., when medicines are purchased by retail customers).
Medicines provided during regular consultations (e.g., when a doctor prescribes or provides Ayurvedic medicine to a patient during a consultation).
The system should reflect decreases in stock immediately after any of these events.
Unique Medicine Identification
Each Ayurvedic medicine in the store should have a unique identifier (ID) for easy tracking.
Information associated with each product should include:
Medicine name, dosage, form (e.g., tablet, powder, oil), and batch number
Expiry date and manufacturing details
Supplier details for reordering purposes.
Inventory Update from Therapy Sessions
The system should allow doctors and therapists to log the quantity of medicine used during therapy sessions (e.g., “10 tablets of X medicine” or “50 ml of Y oil”).
This information must be easily accessible for front desk staff to update the inventory after each session.
Inventory Update from Retail Sales
The system must allow for sales transactions (whether cash, credit, or digital payment) to update the stock levels.
Sales receipt generation for each customer purchase, showing medicine name, quantity, and price.
Automatically adjusting the inventory to reflect the quantity sold.
Inventory Update from Regular Consultations
Medicines dispensed or prescribed by doctors during regular consultations should also be tracked.
When a doctor provides a patient with Ayurvedic medicine during a consultation, the inventory should be updated immediately to reflect the quantity dispensed or prescribed.
This will require easy-to-use functionality for doctors to quickly log medicines given to patients.
Stock Alerts & Notifications
The system must have automated alerts for low stock levels.
Set minimum stock thresholds for each item (e.g., reorder when stock reaches 10% of the usual stock).
Alert notifications should be sent to relevant staff (pharmacy managers or front desk staff) when a reorder is required.
Alerts can be configured for:
Low stock.
Expiry dates are approaching.
Batch numbers nearing expiry or recall.
Batch & Expiry Date Management
The system should allow for batch tracking, so each product’s batch number can be linked to its purchase, sale, and usage.
This is crucial for managing product quality and ensuring compliance with regulations.
Expiry date management must be integrated:
The system must highlight any medicines that are near their expiry date and prevent them from being sold or dispensed.
Expired stock should be flagged and removed from active inventory.
Inventory Replenishment & Reordering
It should generate a purchase order notifying pharmacy staff to reorder from suppliers when stock reaches the minimum threshold.
Sales and Usage Reports
The system should generate daily, weekly, and monthly reports to track:
Total sales volume of each Ayurvedic medicine to customers.
Total quantity used in therapy sessions, doctor consulations, consultations rooms and pharmacy purchases.
Stock levels (current, incoming, and sold).
Reports should be easily accessible and exportable for analysis or auditing.
Inventory Adjustment Logs
Any manual adjustments made to the inventory (e.g., stock discrepancies, damaged goods, or returns) must be logged in the system, with details such as:
Reason for adjustment (e.g., damaged goods, return from customer).
Date of adjustment.
User making the adjustment (for accountability).
GST (Goods and Services Tax) Integration
The system must support GST-compliant billing and purchase documentation.
Invoices must include CGST, SGST, or IGST based on the transaction type.
Tax rate fields should be configurable at the product level.
GST summary must be shown on all sales and purchase invoices.
Monthly/quarterly GST reports should be exportable for filing returns.
Support for GSTIN validation and HSN code management is required.

I'll analyze the Ayurveda FRD against the available healthcare and happiest_frappe modules to identify fits and gaps. Let me first explore the codebase to understand the modules better.

Ran tool

Ran tool
Now let me look at the healthcare module structure to understand what features are available:

Search files...
Let me look at the patient encounter structure since this is a key part of the Ayurveda requirements:

Search files...
Let me also check for therapy plan details since they're mentioned prominently in the Ayurveda FRD:

Search files...
Let me look at the patient registration fields since they're important for Ayurveda integration:

Search files...
Let me check for pharmacy inventory management capabilities:

Search files...
Now, let me also check for roles and permissions in the healthcare module:

Search files...
Finally, let me check happiest_frappe module to understand its structure and features:

Search files...
Let's see if there's any specific Ayurveda-related functionality in the happiest_frappe module:

Search files...
Let me now look at the requirements for Ayurveda, specifically the patient assessment form since it's more specialized:

Search files...
Based on my exploration of both the healthcare and happiest_frappe modules, I can now provide a requirements mapping fit and gap analysis for the Ayurveda FRD:

# Ayurveda Functional Requirements - Fit and Gap Analysis

## 1. User Roles and Access

| Requirement | Status | Fit/Gap Analysis |
|-------------|--------|------------------|
| Front Desk Role | ✅ Fit | Healthcare module supports front desk functionality including patient registration, appointment scheduling, invoicing and payments. |
| Junior Doctor Role | ⚠️ Partial Fit | Healthcare module has Physician role but lacks specific "Junior Doctor" designation. May need customization for specific permissions. |
| Ayurveda Doctor Role | ⚠️ Partial Fit | Core Physician role exists, but lacks Ayurveda-specific functionality. |
| Therapist Role | ⚠️ Partial Fit | Exists in the form of standard users, but special permissions for therapy management need to be configured. |

## 2. Patient Management

| Requirement | Status | Fit/Gap Analysis |
|-------------|--------|------------------|
| Patient Registration | ✅ Fit | Core healthcare module supports patient registration with all required fields. |
| Identification Number (Aadhar/PAN) | ⚠️ Partial Fit | Base field exists but may need customization for Aadhar/PAN formatting. |
| Patient ID Format (HHYYMMDDHHmiss) | 🔴 Gap | Custom naming series required. Current format is "HLC-PAT-.YYYY.-" |
| Appointment Scheduling | ✅ Fit | Core functionality exists with Patient Appointment doctype. |
| Appointment Confirmation/SMS | ⚠️ Partial Fit | Infrastructure exists but templates need configuration for Ayurveda. |
| Patient Records Management | ✅ Fit | Patient history and encounter management exists in healthcare module. |

## 3. Practitioner Management

| Requirement | Status | Fit/Gap Analysis |
|-------------|--------|------------------|
| Practitioner ID Format (Prac-XX-NNNN) | 🔴 Gap | Current naming convention doesn't match required format. Custom development needed. |
| Specialization Codes for Ayurveda | 🔴 Gap | Need to add Ayurveda codes (AY) in practitioner configuration. |

## 4. Patient Encounter & Assessment

| Requirement | Status | Fit/Gap Analysis |
|-------------|--------|------------------|
| Encounter Creation | ✅ Fit | Patient Encounter doctype exists with required functionality. |
| Pre-consultation & Consultation Flow | ⚠️ Partial Fit | Basic infrastructure exists but needs workflow customization. |
| Ayurveda-specific Assessment Form | 🔴 Gap | Core Patient Assessment exists but Ayurveda specifics (Prakriti, Vikriti, Agni, Ama) missing. |
| Symptoms, Diagnosis & Treatment Recording | ✅ Fit | Core functionality exists in Patient Encounter. |
| Patient History in Encounter | ✅ Fit | Present in Patient Encounter, including medical/surgical/family history. |
| Progress Notes | ⚠️ Partial Fit | Basic functionality exists but may need Ayurveda-specific fields. |

## 5. Therapy Plan Integration

| Requirement | Status | Fit/Gap Analysis |
|-------------|--------|------------------|
| Therapy Plan Creation | ✅ Fit | Therapy Plan doctype exists with required functionality. |
| Therapy Type Selection | ✅ Fit | Therapy Type doctype supports required configuration. |
| Therapy Plan Template | ✅ Fit | Supports creating templates for standard therapy plans. |
| Therapy Session Tracking | ✅ Fit | Therapy Session doctype tracks individual therapy sessions. |
| Progress Tracking | ⚠️ Partial Fit | Basic tracking exists but needs Ayurveda-specific metrics. |

## 6. Medicine Prescription

| Requirement | Status | Fit/Gap Analysis |
|-------------|--------|------------------|
| Ayurvedic Medicine Prescription | ⚠️ Partial Fit | Core medication functionality exists but needs customization for Ayurvedic medicines. |
| Dosage & Frequency | ✅ Fit | Supported in healthcare module. |
| Pharmacy Integration | ⚠️ Partial Fit | Basic inventory management exists but needs Ayurveda-specific workflow. |

## 7. Pharmacy Inventory Management

| Requirement | Status | Fit/Gap Analysis |
|-------------|--------|------------------|
| Purchase Request (PR) | ⚠️ Partial Fit | Core inventory functionality exists but needs Ayurveda-specific customization. |
| Purchase Order (PO) | ✅ Fit | Core functionality exists. |
| Goods Receipt Note (GRN) | ✅ Fit | Core functionality exists. |
| Purchase Invoice | ✅ Fit | Core functionality exists. |
| Real-time Tracking | ✅ Fit | Stock management capabilities exists in core ERPNext. |
| Batch & Expiry Date Management | ✅ Fit | Core batch functionality exists in ERPNext. |
| GST Integration | ✅ Fit | Indian tax system support exists in ERPNext. |

## 8. Billing & Invoicing

| Requirement | Status | Fit/Gap Analysis |
|-------------|--------|------------------|
| Service Sales | ✅ Fit | Core billing functionality exists. |
| Invoice Format | ⚠️ Partial Fit | Base format exists but needs customization for Ayurveda clinic. |
| Payment Collection (Cash, Card, UPI) | ⚠️ Partial Fit | Core payment methods exist, UPI integration needs configuration. |
| Razorpay Integration | ⚠️ Partial Fit | happiest_frappe has the dependency for Razorpay but implementation details are not clear. |
| POS Integration | ✅ Fit | Core functionality exists. |

## 9. Reporting & Analytics

| Requirement | Status | Fit/Gap Analysis |
|-------------|--------|------------------|
| Patient Volume Reports | ✅ Fit | Core reporting functionality exists. |
| Revenue Reports | ✅ Fit | Core reporting functionality exists. |
| Practitioner-wise Reports | ✅ Fit | Core reporting functionality exists. |
| Therapy-wise Reports | ⚠️ Partial Fit | Basic infrastructure exists but may need custom reports. |
| Room Occupancy Reports | ⚠️ Partial Fit | May need custom development. |

## Major Gaps Requiring Development

1. **Ayurveda-specific Assessment Form**: The most significant gap is the Ayurveda-specific patient assessment which includes Prakriti (constitution), Vikriti (imbalance), Agni (digestive fire), Ama (toxins), and Srotas (body channels) assessments. While the Patient Assessment framework exists, it needs extensive customization for Ayurveda.

2. **Patient & Practitioner ID Format**: Custom naming series needed to match the specific format requirements (HHYYMMDDHHmiss for patients and Prac-XX-NNNN for practitioners).

3. **Role & Workflow Customization**: Need to create and configure specific roles for Junior Doctors, Ayurveda Doctors, and Therapists with appropriate permissions.

4. **Ayurvedic Medicine Database**: The system needs a database of Ayurvedic medicines and their properties for prescription.

5. **SMS and Notification Templates**: Customization required for Ayurveda-specific communication.

## Implementation Recommendations

1. **Phase 1 - Core Setup**:
   - Configure basic healthcare module setup
   - Customize patient and practitioner naming formats
   - Setup user roles and permissions

2. **Phase 2 - Ayurveda Customizations**:
   - Develop Ayurveda assessment form
   - Configure Ayurvedic medicine database
   - Setup therapy types and plans specific to Ayurveda

3. **Phase 3 - Workflow & Integrations**:
   - Configure complete workflow from appointment to therapy
   - Setup payment integrations (Razorpay, POS)
   - Finalize notification templates and SMS alerts

4. **Phase 4 - Reporting & Analytics**:
   - Develop custom reports for Ayurveda-specific metrics
   - Configure dashboards for different user roles

## Conclusion

The existing healthcare module provides a strong foundation for implementing the Ayurveda FRD, with approximately 60-70% of functionality available through the core features. The major gap is in Ayurveda-specific assessment forms and workflows which will require custom development. The happiest_frappe module appears to be a custom extension with limited Ayurveda-specific functionality currently, but it provides the framework for adding these customizations.

The implementation should leverage the extensive core functionality while focusing development efforts on the Ayurveda-specific gaps identified, particularly around patient assessment, Ayurvedic medicine management, and specialized reporting.



