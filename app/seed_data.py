from app.database import init_db, get_connection

SERVICES_SEED = [
    # BLOOD TESTS (PATHOLOGY)
    ("PATH_CBC", "BLOOD_TEST", "Complete Blood Count (CBC)", "cbc, hemogram, khoon ki jaanch, hemoglobin, hb test, platelets, wbc, rbc, rakta tapani", 250, 0, 0, 0, "No fasting required. Sample can be given any time.", "Same day within 4 hours", 1),
    ("PATH_FBS", "BLOOD_TEST", "Fasting Blood Sugar (FBS)", "fbs, fasting sugar, khali pet sugar, diabetes test, blood glucose fasting, sakhar tapani", 100, 1, 0, 0, "8 to 10 hours overnight fasting required. Only plain water is permitted.", "Same day within 3 hours", 1),
    ("PATH_PPBS", "BLOOD_TEST", "Post Prandial Blood Sugar (PPBS)", "ppbs, pp sugar, khane ke baad sugar, post lunch sugar, 2 hours after meal sugar", 100, 0, 0, 0, "Sample must be given exactly 2 hours after starting your meal.", "Same day within 3 hours", 1),
    ("PATH_HBA1C", "BLOOD_TEST", "HbA1c (3-Month Average Sugar)", "hba1c, glycosylated hemoglobin, 3 mahine ka sugar, three month average sugar", 450, 0, 0, 0, "No fasting required.", "Same day by 6:00 PM", 1),
    ("PATH_LIPID", "BLOOD_TEST", "Lipid Profile (Cholesterol)", "lipid profile, cholesterol test, charbi ki jaanch, triglycerides, hdl, ldl, heart blood test", 600, 1, 0, 0, "10 to 12 hours strict overnight fasting required. Plain water is allowed.", "Same day by 6:00 PM", 1),
    ("PATH_THYROID", "BLOOD_TEST", "Thyroid Profile Total (T3, T4, TSH)", "thyroid test, tsh, t3 t4, gala ka thyroid, wazan badhne ka test, hormonal thyroid", 500, 0, 0, 0, "Morning sample preferred. Fasting is not strictly mandatory unless advised by doctor.", "Same day by 6:00 PM", 1),
    ("PATH_LFT", "BLOOD_TEST", "Liver Function Test (LFT)", "lft, liver test, jigar ki jaanch, bilirubin, sgot, sgpt, jaundice test, piliya test", 650, 1, 0, 0, "8 to 10 hours fasting recommended for accurate bilirubin and enzyme levels.", "Same day by 6:00 PM", 1),
    ("PATH_KFT", "BLOOD_TEST", "Kidney Function Test (KFT / RFT)", "kft, rft, kidney test, creatinine, urea, uric acid, gurde ki jaanch, renal profile", 650, 0, 0, 0, "No fasting required.", "Same day by 6:00 PM", 1),
    ("PATH_VITD", "BLOOD_TEST", "Vitamin D (25-OH) & Vitamin B12 Combo", "vitamin d, vitamin b12, haddi kamzori test, naso ka dard vitamin, d3 b12", 1400, 0, 0, 0, "No fasting required.", "Next day by 12:00 PM", 1),
    ("PATH_FEVER", "BLOOD_TEST", "Mumbai Monsoon / Fever Profile (CBC, Malaria, Dengue NS1, Widal, Urine)", "fever profile, bukhar ka test, dengue test, malaria test, typhoid widal, barish bukhar panel", 1100, 0, 0, 0, "No fasting required. Collect clean mid-stream urine if Urine Routine is included.", "Same day within 5 hours", 1),

    # X-RAY (RADIOLOGY)
    ("XRAY_CHEST", "XRAY", "Digital X-Ray Chest (PA View)", "chest xray, chhati ka xray, lungs xray, khansi tb xray, chest pa view, digital xray chest", 350, 0, 0, 0, "Remove all metallic objects, chains, and innerwear hooks from the chest area. Inform technician if pregnant.", "Digital film in 20 minutes; Doctor report in 2 hours", 0),
    ("XRAY_SPINE", "XRAY", "Digital X-Ray Lumbosacral (L-S) Spine AP/Lat", "kamar ka xray, back pain xray, ls spine xray, reedh ki haddi ka xray, slip disc xray", 600, 0, 0, 0, "Avoid metallic belts or zippers. Inform technician if there is any chance of pregnancy.", "Digital film in 20 minutes; Doctor report in 2 hours", 0),
    ("XRAY_KNEE", "XRAY", "Digital X-Ray Knee Joint (AP/Lat)", "knee xray, ghutne ka xray, pair ka xray, fracture xray, bone xray, ortho xray", 500, 0, 0, 0, "No special preparation required.", "Digital film in 20 minutes; Doctor report in 2 hours", 0),

    # ULTRASONOGRAPHY (USG)
    ("USG_ABD", "USG", "USG Whole Abdomen (Sonography)", "abdomen sonography, pet ka scan, usg whole abdomen, liver gallbladder sonography, stomach scan, pet scan", 1000, 1, 1, 0, "1) 6 hours fasting required (no food/tea). 2) Drink 1 liter (4-5 glasses) of plain water 1 hour before scan and DO NOT urinate so bladder is full. Note: We provide Abdomen Sonography (Stomach Scan), not nuclear PET-CT scans.", "Report handed over within 30 minutes of scan", 0),
    ("USG_KUB", "USG", "USG KUB / Pelvis (Kidney, Ureter, Bladder / Lower Abdomen)", "kub sonography, kidney stone scan, pathri ka scan, pelvis sonography, prostate scan, uterus scan", 900, 0, 1, 0, "No fasting needed. Drink 1 liter of water 45-60 minutes prior to the scan and hold urine (Full Bladder mandatory).", "Report handed over within 30 minutes of scan", 0),
    ("USG_OBS", "USG", "Obstetric / Pregnancy Ultrasound (ANC / Growth / NT Scan)", "pregnancy sonography, anc scan, baby growth scan, nt scan, garbhvati sonography, Anomaly scan", 1300, 0, 0, 1, "MANDATORY BY LAW (PCPNDT Act): Patient MUST bring original Doctor Prescription showing Doctor Registration Number AND Patient's Original Government Photo ID (Aadhaar/Voter ID/PAN).", "Report handed over within 30 minutes of scan", 0),

    # PHYSIOTHERAPY
    ("PHYSIO_SESSION", "PHYSIO", "Physiotherapy Rehabilitation Session (IFT / TENS / Ultrasound / Manual Therapy)", "physiotherapy, kasrat, kamar dard therapy, knee pain exercise, frozen shoulder, slip disc physio, paralysis rehab, neck pain traction, physio, rehab, exercise", 400, 0, 0, 0, "Wear loose, comfortable clothing. Bring previous X-Ray or MRI reports if available. Both male and female physiotherapists available.", "45-minute guided clinical session", 1),
    ("PHYSIO_PKG", "PHYSIO", "10-Day Physiotherapy Pain & Ortho Rehab Package", "physio package, 10 days physiotherapy, monthly physio rate, stroke rehab package", 3500, 0, 0, 0, "Includes daily electrotherapy + manual mobilization + guided strengthening.", "10 sessions (45 mins each)", 1),

    # DOCTOR CONSULTATION (OPD)
    ("OPD_GP", "CONSULTATION", "General Physician & Family Medicine Consultation", "doctor consultation, opd, doctor ko dikhana hai, report dikhana hai, bukhar doctor, bp sugar checkup, dava lena hai", 300, 0, 0, 0, "Carry your previous prescriptions and recent blood/scan reports if any.", "Immediate OPD Consultation (Follow-up free within 5 days)", 0),
]

DOCTORS_SEED = [
    ("DOC_01", "Dr. Ahmed Khan", "General Consultation (OPD)", "MBBS, MD (Internal Medicine)", "Monday to Saturday", "10:00 AM - 2:00 PM & 6:00 PM - 9:30 PM", 300),
    ("DOC_02", "Dr. Sana Shaikh", "Radiology & Sonography (USG)", "MBBS, DMRD (Radiologist)", "Monday to Saturday", "11:00 AM - 3:00 PM & 5:30 PM - 8:00 PM", 0),
    ("DOC_03", "Dr. Farhan Qureshi & Dr. Neha Patil", "Physiotherapy & Ortho Rehab", "BPT, MPT (Ortho & Neuro)", "Monday to Saturday", "9:00 AM - 8:30 PM (By Slot)", 400),
]

def seed_database() -> None:
    init_db()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.executemany(
            """INSERT OR REPLACE INTO services 
            (service_id, category, canonical_name, search_aliases, price_inr, fasting_required, 
             full_bladder_required, prescription_mandatory, prep_instructions, report_tat, home_visit_available)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            SERVICES_SEED,
        )
        cur.executemany(
            """INSERT OR REPLACE INTO doctors
            (doctor_id, name, department, qualification, available_days, timings, fee_inr)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            DOCTORS_SEED,
        )
        conn.commit()
    finally:
        conn.close()

if __name__ == "__main__":
    seed_database()
    print("Database seeded successfully.")
