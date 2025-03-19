# Patient Duplication Check

Tag: HappiestHealth

**Problem statement**

When a patient record is getting created, it is quite possible for the front desk/website user to create redundant patient record.

The creation of duplicate patient records can lead to:

- **Medical Errors:** Incorrect or incomplete patient histories, medication discrepancies, and inaccurate patient treatment.
- **Operational Inefficiencies:** Increased administrative burden, wasted resources, and delayed patient care.
- **Data Integrity Issues:** Compromised data accuracy, hindering effective analysis and reporting.
- **Compliance Risks:** Potential violations of data privacy and security regulations

**Proposed Solution**

1. Implement a SOP with for creating a new patient where the Front desk user should always check if the patient record exists. By searching the patient record with mobile number. If there is no patient information found then it would be advisable to create a new patient record

2. The PMS (ERP Next) should be able to validate if exact matched records are available

To do this according to the EHR Standards 2013  Govt of India guidelines we should be checking the following data elements (Note the guidelines suggest many other data elements, we are suggesting based on the business requirements)

1. First Name

2. Last Name

3. Gender

4. Date of Birth

4. Mobile Number

[](https://lh7-rt.googleusercontent.com/docsz/AD_4nXe-KcTSL1mHXAH54dEHJId54GWWZ5yIjPU25IQ2SDBvICPzc1PTGpZTlhwCLrWVHZSlwTATdJxH9MOneMebE9VZhfI4-fjw-bBIfLdRYyTlENyd6sXW7odhes8fYqJiR-TZeuxTB_3fAph75obnWGk?key=GVmUO6NgQZ5fCRVi0PwvCLhc)

**Scenarios and expected application behavior**

**Please refer below**

| Scenario | First Name | Last Name | Gender | Age | Mobile Number | Action |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Exact Match | No Match | No Match | No Match | No Match | Allow creation without warning |
| 2 | Exact Match | Exact Match | Exact Match | Exact Match | Exact Match | Disallow creation; display matched records in a modal; allow navigation |
| 3 | Exact Match | Exact Match | Exact Match | Exact Match | No Match | Disallow creation; display matched records in a modal; allow navigation |
| 4 | Exact Match | Exact Match | Exact Match | No Match | Exact Match | Disallow creation; display matched records in a modal; allow navigation |
| 5 | Exact Match | Exact Match | No Match | Exact Match | Exact Match | Disallow creation; display matched records in a modal; allow navigation |
| 6 | Exact Match | No Match | Exact Match | Exact Match | Exact Match | Disallow creation; display matched records in a modal; allow navigation |
| 7 | No Match | Exact Match | Exact Match | Exact Match | Exact Match | Disallow creation; display matched records in a modal; allow navigation |
| 8 | Exact Match | Exact Match | No Match | No Match | No Match | Display a warning; prompt user to review potential matches; allow creation with confirmation |
| 9 | Exact Match | No Match | Exact Match | No Match | No Match | Display a warning; prompt user to review potential matches; allow creation with confirmation |
| 10 | Exact Match | No Match | No Match | Exact Match | No Match | Display a warning; prompt user to review potential matches; allow creation with confirmation |
| 11 | Exact Match | No Match | No Match | No Match | Exact Match | Display a warning; prompt user to review potential matches; allow creation with confirmation |
| 12 | No Match | Exact Match | Exact Match | No Match | No Match | Display a warning; prompt user to review potential matches; allow creation with confirmation |
| 13 | No Match | Exact Match | No Match | Exact Match | No Match | Display a warning; prompt user to review potential matches; allow creation with confirmation |
| 14 | No Match | Exact Match | No Match | No Match | Exact Match | Display a warning; prompt user to review potential matches; allow creation with confirmation |
| 15 | No Match | No Match | Exact Match | Exact Match | No Match | Display a warning; prompt user to review potential matches; allow creation with confirmation |
| 16 | No Match | No Match | Exact Match | No Match | Exact Match | Display a warning; prompt user to review potential matches; allow creation with confirmation |
| 17 | No Match | No Match | No Match | Exact Match | Exact Match | Display a warning; prompt user to review potential matches; allow creation with confirmation |
| 18 | Exact Match | Exact Match | No Match | No Match | Exact Match | Display a warning; prompt user to review potential matches; allow creation with confirmation |
| 19 | Exact Match | Exact Match | No Match | Exact Match | No Match | Display a warning; prompt user to review potential matches; allow creation with confirmation |
| 20 | Exact Match | No Match | Exact Match | Exact Match | No Match | Display a warning; prompt user to review potential matches; allow creation with confirmation |
| 21 | Exact Match | No Match | Exact Match | No Match | Exact Match | Display a warning; prompt user to review potential matches; allow creation with confirmation |
| 22 | No Match | Exact Match | Exact Match | Exact Match | No Match | Display a warning; prompt user to review potential matches; allow creation with confirmation |
| 23 | No Match | Exact Match | Exact Match | No Match | Exact Match | Display a warning; prompt user to review potential matches; allow creation with confirmation |
| 24 | No Match | No Match | Exact Match | Exact Match | Exact Match | Display a warning; prompt user to review potential matches; allow creation with confirmation |
| 25 | No Match | No Match | No Match | No Match | No Match | Allow creation without warning |

**Proposed Solution(Continued)**

**3.** Implement merge patient records

With the above solution there can be scenarios where a redundant patient record might be created. to manage this we will be implementing a merging of the two or more patient records to one.