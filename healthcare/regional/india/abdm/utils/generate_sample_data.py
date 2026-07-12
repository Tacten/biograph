"""
Sample data generator for Frappe Healthcare.
Generates realistic Indian patient/practitioner data suitable for ABDM M1 sandbox testing.

Run via:
    bench execute healthcare.regional.india.abdm.utils.generate_sample_data.generate --args "[]"

Or from bench console:
    import healthcare.regional.india.abdm.utils.generate_sample_data as g; g.generate()
"""

import random
from datetime import date, timedelta, time

import frappe
from frappe.utils import today, now_datetime


# ---------------------------------------------------------------------------
# Master data
# ---------------------------------------------------------------------------

DEPARTMENTS = [
    "General Medicine",
    "Cardiology",
    "Orthopaedics",
    "Obstetrics and Gynaecology",
    "Paediatrics",
    "Dermatology",
    "Ophthalmology",
    "ENT",
]

PRACTITIONERS = [
    {"first_name": "Arvind",   "last_name": "Sharma",    "department": "General Medicine",               "gender": "Male"},
    {"first_name": "Priya",    "last_name": "Nair",      "department": "Obstetrics and Gynaecology",     "gender": "Female"},
    {"first_name": "Ramesh",   "last_name": "Iyer",      "department": "Cardiology",                     "gender": "Male"},
    {"first_name": "Sunita",   "last_name": "Kulkarni",  "department": "Paediatrics",                    "gender": "Female"},
    {"first_name": "Vikram",   "last_name": "Mehta",     "department": "Orthopaedics",                   "gender": "Male"},
    {"first_name": "Ananya",   "last_name": "Reddy",     "department": "Dermatology",                    "gender": "Female"},
    {"first_name": "Suresh",   "last_name": "Patel",     "department": "Ophthalmology",                  "gender": "Male"},
    {"first_name": "Kavitha",  "last_name": "Menon",     "department": "ENT",                            "gender": "Female"},
]

PATIENTS = [
    {"first_name": "Rajesh",    "last_name": "Kumar",      "sex": "Male",   "dob": "1985-03-12", "mobile": "9876543210", "blood_group": "B Positive"},
    {"first_name": "Sunita",    "last_name": "Devi",       "sex": "Female", "dob": "1990-07-22", "mobile": "9823456789", "blood_group": "O Positive"},
    {"first_name": "Amit",      "last_name": "Verma",      "sex": "Male",   "dob": "1978-11-05", "mobile": "9912345678", "blood_group": "A Positive"},
    {"first_name": "Priyanka",  "last_name": "Singh",      "sex": "Female", "dob": "1995-01-30", "mobile": "9834567890", "blood_group": "AB Positive"},
    {"first_name": "Mohammed",  "last_name": "Ali",        "sex": "Male",   "dob": "1982-09-14", "mobile": "9765432109", "blood_group": "O Negative"},
    {"first_name": "Lakshmi",   "last_name": "Nair",       "sex": "Female", "dob": "1970-04-18", "mobile": "9756341230", "blood_group": "B Negative"},
    {"first_name": "Arjun",     "last_name": "Pillai",     "sex": "Male",   "dob": "2000-06-25", "mobile": "9667890123", "blood_group": "A Negative"},
    {"first_name": "Meena",     "last_name": "Iyer",       "sex": "Female", "dob": "1965-12-01", "mobile": "9890123456", "blood_group": "B Positive"},
    {"first_name": "Ravi",      "last_name": "Shankar",    "sex": "Male",   "dob": "1993-08-08", "mobile": "9078901234", "blood_group": "O Positive"},
    {"first_name": "Deepa",     "last_name": "Menon",      "sex": "Female", "dob": "1988-02-14", "mobile": "9345678901", "blood_group": "A Positive"},
    {"first_name": "Suresh",    "last_name": "Babu",       "sex": "Male",   "dob": "1975-05-20", "mobile": "9234567890", "blood_group": "AB Negative"},
    {"first_name": "Anita",     "last_name": "Rao",        "sex": "Female", "dob": "1998-10-03", "mobile": "9123456780", "blood_group": "O Positive"},
    {"first_name": "Karthik",   "last_name": "Murugan",    "sex": "Male",   "dob": "1987-07-07", "mobile": "9011234567", "blood_group": "B Positive"},
    {"first_name": "Pooja",     "last_name": "Sharma",     "sex": "Female", "dob": "1992-03-25", "mobile": "8987654321", "blood_group": "A Positive"},
    {"first_name": "Dinesh",    "last_name": "Chandra",    "sex": "Male",   "dob": "1960-11-11", "mobile": "8876543219", "blood_group": "O Positive"},
]

DIAGNOSES = [
    "Essential (primary) hypertension",
    "Type 2 diabetes mellitus without complications",
    "Acute upper respiratory infection",
    "Low back pain",
    "Allergic rhinitis due to pollen",
    "Iron deficiency anaemia",
    "Hypothyroidism",
    "Osteoarthritis of knee",
    "Migraine without aura",
    "Gastro-oesophageal reflux disease",
    "Anxiety disorder",
    "Vitamin D deficiency",
]

DRUG_PRESCRIPTIONS = [
    {"drug_code": "Metformin 500mg", "dosage": "1 Tablet(s)", "period": "4 Months"},
    {"drug_code": "Amlodipine 5mg",  "dosage": "1 Tablet(s)", "period": "2 Months"},
    {"drug_code": "Paracetamol 500mg","dosage": "2 Tablet(s)","period": "5 Days"},
    {"drug_code": "Atorvastatin 10mg","dosage": "1 Tablet(s)","period": "3 Months"},
    {"drug_code": "Pantoprazole 40mg","dosage": "1 Tablet(s)","period": "1 Month"},
    {"drug_code": "Cetirizine 10mg",  "dosage": "1 Tablet(s)","period": "2 Weeks"},
    {"drug_code": "Vitamin D3 60000IU","dosage":"1 Capsule(s)","period":"8 Weeks"},
]

APPOINTMENT_STATUSES = ["Scheduled", "Open", "Closed"]
COMPANY = "Test Hospital"


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def generate():
    """Generate all sample data. Run via bench execute."""
    frappe.set_user("Administrator")
    print("\n=== ABDM Sample Data Generator ===\n")

    _ensure_company()
    dept_map = _create_departments()
    prac_map = _create_practitioners(dept_map)
    patient_map = _create_patients()
    _create_appointments(patient_map, prac_map, dept_map)
    _create_encounters_and_vitals(patient_map, prac_map, dept_map)

    frappe.db.commit()
    print(f"\n✅ Sample data generation complete.")
    print(f"   {len(patient_map)} patients | {len(prac_map)} practitioners | {len(dept_map)} departments")


# ---------------------------------------------------------------------------
# Company
# ---------------------------------------------------------------------------

def _ensure_company():
    if not frappe.db.exists("Company", COMPANY):
        print(f"  Creating company: {COMPANY}")
        company = frappe.get_doc({
            "doctype": "Company",
            "company_name": COMPANY,
            "abbr": "TH",
            "default_currency": "INR",
            "country": "India",
        })
        company.insert(ignore_permissions=True)
    else:
        print(f"  Company '{COMPANY}' already exists — skipping")


def _get_customer_group() -> str:
    """Return a valid non-group Customer Group for Patient → Customer auto-creation."""
    # Try the Selling Settings default first
    default_cg = frappe.db.get_single_value("Selling Settings", "customer_group")
    if default_cg:
        is_group = frappe.db.get_value("Customer Group", default_cg, "is_group")
        if not is_group:
            return default_cg

    # Otherwise find any non-group Customer Group
    cg = frappe.db.get_value(
        "Customer Group",
        {"is_group": 0},
        "name",
        order_by="creation asc",
    )
    if cg:
        return cg

    # Last resort: create a leaf group
    if not frappe.db.exists("Customer Group", "Patient"):
        frappe.get_doc({
            "doctype": "Customer Group",
            "customer_group_name": "Patient",
            "parent_customer_group": "All Customer Groups",
            "is_group": 0,
        }).insert(ignore_permissions=True)
    return "Patient"


def _get_territory() -> str:
    """Return a valid non-group Territory."""
    default_t = frappe.db.get_single_value("Selling Settings", "territory")
    if default_t:
        is_group = frappe.db.get_value("Territory", default_t, "is_group")
        if not is_group:
            return default_t

    t = frappe.db.get_value(
        "Territory",
        {"is_group": 0},
        "name",
        order_by="creation asc",
    )
    if t:
        return t

    if not frappe.db.exists("Territory", "India"):
        frappe.get_doc({
            "doctype": "Territory",
            "territory_name": "India",
            "parent_territory": "All Territories",
            "is_group": 0,
        }).insert(ignore_permissions=True)
    return "India"


# ---------------------------------------------------------------------------
# Medical Departments
# ---------------------------------------------------------------------------

def _create_departments() -> dict:
    dept_map = {}
    print("\n[1/5] Medical Departments")
    for dept_name in DEPARTMENTS:
        if frappe.db.exists("Medical Department", dept_name):
            print(f"  ↳ {dept_name} (exists)")
            dept_map[dept_name] = dept_name
            continue
        dept = frappe.get_doc({
            "doctype": "Medical Department",
            "department": dept_name,
        })
        dept.insert(ignore_permissions=True)
        dept_map[dept_name] = dept.name
        print(f"  ✓ {dept_name}")
    return dept_map


# ---------------------------------------------------------------------------
# Healthcare Practitioners
# ---------------------------------------------------------------------------

def _create_practitioners(dept_map: dict) -> dict:
    prac_map = {}
    print("\n[2/5] Healthcare Practitioners")
    for p in PRACTITIONERS:
        full_name = f"Dr. {p['first_name']} {p['last_name']}"
        existing = frappe.db.get_value(
            "Healthcare Practitioner", {"practitioner_name": full_name}, "name"
        )
        if existing:
            print(f"  ↳ {full_name} (exists)")
            prac_map[p["department"]] = existing
            continue

        prac = frappe.get_doc({
            "doctype": "Healthcare Practitioner",
            "first_name": p["first_name"],
            "last_name": p["last_name"],
            "gender": p["gender"],
            "department": dept_map.get(p["department"]),
            "status": "Active",
        })
        prac.insert(ignore_permissions=True)
        prac_map[p["department"]] = prac.name
        print(f"  ✓ {full_name} ({p['department']})")
    return prac_map


# ---------------------------------------------------------------------------
# Patients
# ---------------------------------------------------------------------------

def _create_patients() -> dict:
    patient_map = {}
    print("\n[3/5] Patients")
    customer_group = _get_customer_group()
    territory = _get_territory()
    print(f"  Using Customer Group: {customer_group!r} | Territory: {territory!r}")

    for p in PATIENTS:
        full_name = f"{p['first_name']} {p['last_name']}"
        existing = frappe.db.get_value(
            "Patient", {"patient_name": full_name}, "name"
        )
        if existing:
            print(f"  ↳ {full_name} (exists)")
            patient_map[full_name] = existing
            continue

        patient = frappe.get_doc({
            "doctype": "Patient",
            "first_name": p["first_name"],
            "last_name": p["last_name"],
            "sex": p["sex"],
            "dob": p["dob"],
            "mobile": p["mobile"],
            "blood_group": p["blood_group"],
            "status": "Active",
            "customer_group": customer_group,
            "territory": territory,
        })
        patient.insert(ignore_permissions=True)
        patient_map[full_name] = patient.name
        print(f"  ✓ {full_name} | DOB: {p['dob']} | Mobile: {p['mobile']}")
    return patient_map


# ---------------------------------------------------------------------------
# Patient Appointments
# ---------------------------------------------------------------------------

def _create_appointments(patient_map: dict, prac_map: dict, dept_map: dict):
    print("\n[4/5] Patient Appointments")
    today_date = date.today()
    created = 0

    practitioners = list(prac_map.values())
    patients = list(patient_map.values())

    for i, patient_name in enumerate(patients):
        # 1–2 appointments per patient spread over last 30 days
        for j in range(random.randint(1, 2)):
            appt_date = today_date - timedelta(days=random.randint(0, 30))
            appt_time = time(
                hour=random.randint(9, 17),
                minute=random.choice([0, 15, 30, 45]),
            )
            practitioner = practitioners[i % len(practitioners)]
            dept_name = DEPARTMENTS[i % len(DEPARTMENTS)]
            dept = dept_map.get(dept_name)

            try:
                appt = frappe.get_doc({
                    "doctype": "Patient Appointment",
                    "patient": patient_name,
                    "practitioner": practitioner,
                    "department": dept,
                    "appointment_date": str(appt_date),
                    "appointment_time": str(appt_time),
                    "company": COMPANY,
                    "status": "Closed" if appt_date < today_date else "Scheduled",
                    "duration": 15,
                })
                appt.insert(ignore_permissions=True)
                created += 1
            except Exception as e:
                print(f"  ⚠ Appointment for {patient_name}: {e}")

    print(f"  ✓ {created} appointments created")


# ---------------------------------------------------------------------------
# Patient Encounters + Vital Signs
# ---------------------------------------------------------------------------

def _create_encounters_and_vitals(patient_map: dict, prac_map: dict, dept_map: dict):
    print("\n[5/5] Patient Encounters + Vital Signs")
    today_date = date.today()
    enc_created = 0
    vitals_created = 0

    practitioners = list(prac_map.values())
    patients = list(patient_map.values())

    for i, patient_name in enumerate(patients):
        practitioner = practitioners[i % len(practitioners)]
        dept_name = DEPARTMENTS[i % len(DEPARTMENTS)]
        enc_date = today_date - timedelta(days=random.randint(1, 25))
        enc_time = f"{random.randint(9, 17):02d}:{random.choice(['00','15','30','45'])}"

        # Pick 1–2 diagnoses
        chosen_diagnoses = random.sample(DIAGNOSES, k=random.randint(1, 2))
        # Pick 1 drug
        drug = random.choice(DRUG_PRESCRIPTIONS)

        try:
            enc = frappe.get_doc({
                "doctype": "Patient Encounter",
                "patient": patient_name,
                "practitioner": practitioner,
                "encounter_date": str(enc_date),
                "encounter_time": enc_time,
                "company": COMPANY,
                "medical_department": dept_map.get(dept_name),
                "diagnosis": [
                    {"diagnosis": d, "code": ""}
                    for d in chosen_diagnoses
                ],
                "drug_prescription": [
                    {
                        "drug_code": drug["drug_code"],
                        "dosage": drug["dosage"],
                        "period": drug["period"],
                    }
                ],
                "encounter_comment": _random_soap_note(chosen_diagnoses),
            })
            enc.insert(ignore_permissions=True)
            enc_created += 1

            # Vital signs for the same encounter
            vitals = frappe.get_doc({
                "doctype": "Vital Signs",
                "patient": patient_name,
                "encounter": enc.name,
                "signs_date": str(enc_date),
                "signs_time": enc_time,
                "company": COMPANY,
                "temperature": round(random.uniform(36.5, 37.5), 1),
                "pulse": random.randint(62, 95),
                "respiratory_rate": random.randint(14, 20),
                "bp_systolic": random.randint(110, 145),
                "bp_diastolic": random.randint(70, 95),
                "height": round(random.uniform(150, 185), 1),
                "weight": round(random.uniform(50, 95), 1),
            })
            vitals.insert(ignore_permissions=True)
            vitals_created += 1

        except Exception as e:
            print(f"  ⚠ Encounter for {patient_name}: {e}")

    print(f"  ✓ {enc_created} encounters | {vitals_created} vital sign records")


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _random_soap_note(diagnoses: list) -> str:
    diag_str = ", ".join(diagnoses)
    templates = [
        f"Patient presents with complaints consistent with {diag_str}. Advised medication and follow-up in 2 weeks.",
        f"Reviewed investigations. Diagnosis: {diag_str}. Treatment plan initiated. Patient counselled on lifestyle modifications.",
        f"Follow-up visit. {diag_str} — condition stable. Continuing current medication. Next review in 1 month.",
        f"Patient reports improvement. {diag_str} — responding to treatment. Dose adjusted as per latest labs.",
    ]
    return random.choice(templates)
