# MASTER SYSTEM SPECIFICATION: DAR UL SHIFA DIAGNOSTIC CENTER CHATBOT (MUMBAI)

## 1. ROLE & EXECUTION DIRECTIVE FOR ANTIGRAVITY AGENT
You are building a production-ready, zero-cost, minimal-hardware (<180MB RAM, CPU-only) clinical front-desk & triage chatbot for **Dar ul Shifa Diagnostic Center** located in Mumbai, India.
The clinic provides exactly 5 core services:
1. **Blood Tests (Pathology)**
2. **Doctor Consultation (OPD)**
3. **X-Ray (Radiology)**
4. **Ultrasonography (USG / Sonography)**
5. **Physiotherapy**

You must create every file defined in the **Target File Tree** below, populate the SQLite database using the seed script, verify the hybrid semantic router, and run `pytest` via the terminal until 100% of unit and safety tests pass.

---

## 2. STANDING ARCHITECTURAL RULES (`AGENTS.md`)
Create `AGENTS.md` in the root directory with these strict project constraints:
- **Zero-Cost & Minimal-Hardware Constraint**:
  - NEVER install `torch`, `tensorflow`, `transformers`, `sentence-transformers`, `langchain`, or `chromadb`. They exceed the 200MB RAM budget.
  - Use a pure-Python + `scikit-learn` (TF-IDF character/word n-grams) + `rank_bm25` + `difflib` hybrid lexical-semantic scoring engine on top of standard library `sqlite3` (WAL mode). Total RAM footprint must stay under 120MB.
  - Use the official `google-genai` SDK (`from google import genai`) calling `gemini-2.5-flash` (Free Tier) with `temperature=0.0`.
  - Include a deterministic offline fallback formatter so the chatbot still functions with 100% accuracy even if `GEMINI_API_KEY` is missing or rate-limited (HTTP 429).
- **Clinical & Statutory Safety Gate (Zero Tolerance)**:
  - Layer 1 (`app/guardrails.py`) MUST execute BEFORE any database search or LLM call.
  - Any query matching PCPNDT Act (fetal sex/gender determination) keywords in English, Hinglish, Marathi, or Roman Urdu must immediately return the statutory legal refusal and NEVER invoke the LLM.
  - Any query matching acute medical emergencies (chest pain, stroke, severe breathlessness, heavy bleeding, unconsciousness) must immediately trigger an emergency casualty redirect (108 / nearest 24x7 hospital) and bypass appointment booking.
  - Any query asking for report interpretation, diagnosis, or medicine prescription must be refused and redirected to book an OPD Consultation.
- **Zero-Hallucination Grounding**:
  - The LLM is strictly forbidden from inventing prices, timings, doctor names, or test preparations. It may only synthesize facts passed inside `<CLINIC_CONTEXT>` XML tags.

---

## 3. TARGET FILE TREE
Create the following exact directory and file structure:

```text
dar-ul-shifa-bot/
├── AGENTS.md
├── requirements.txt
├── .env.example
├── app/
│   ├── __init__.py
│   ├── config.py
│   ├── database.py
│   ├── seed_data.py
│   ├── guardrails.py
│   ├── semantics.py
│   ├── session_manager.py
│   ├── llm_client.py
│   ├── main.py
│   └── static/
│       └── index.html
└── tests/
    ├── __init__.py
    └── test_system.py
```

---

## 4. COMPLETE FILE IMPLEMENTATIONS

### 4.1 `requirements.txt`
```text
fastapi==0.115.0
uvicorn[standard]==0.30.6
pydantic==2.9.2
scikit-learn==1.5.2
rank-bm25==0.2.2
google-genai>=1.0.0
python-dotenv==1.0.1
httpx==0.27.2
pytest==8.3.3
```

### 4.2 `.env.example`
```ini
GEMINI_API_KEY=your_free_google_ai_studio_key_here
CLINIC_NAME="Dar ul Shifa Diagnostic Center"
CLINIC_PHONE="+91-22-23456789"
CLINIC_WHATSAPP="+91-9876543210"
CLINIC_ADDRESS="Ground Floor, Dar ul Shifa Clinic, Mumbai, Maharashtra"
CLINIC_TIMINGS="Monday to Saturday: 7:30 AM – 9:00 PM | Sunday: 8:00 AM – 2:00 PM"
TELEGRAM_BOT_TOKEN=""
TELEGRAM_RECEPTION_CHAT_ID=""
```

### 4.3 `app/config.py`
```python
import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    CLINIC_NAME: str = os.getenv("CLINIC_NAME", "Dar ul Shifa Diagnostic Center")
    CLINIC_PHONE: str = os.getenv("CLINIC_PHONE", "+91-22-23456789")
    CLINIC_WHATSAPP: str = os.getenv("CLINIC_WHATSAPP", "+91-9876543210")
    CLINIC_ADDRESS: str = os.getenv("CLINIC_ADDRESS", "Dar ul Shifa Clinic, Mumbai, Maharashtra")
    CLINIC_TIMINGS: str = os.getenv("CLINIC_TIMINGS", "Mon-Sat: 7:30 AM - 9:00 PM | Sun: 8:00 AM - 2:00 PM")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    DB_PATH: str = os.getenv("DB_PATH", "darulshifa.db")
    HIGH_CONFIDENCE_THRESHOLD: float = 0.42
    CLARIFICATION_THRESHOLD: float = 0.22

settings = Settings()
```

### 4.4 `app/database.py`
```python
import sqlite3
from typing import List, Dict, Any, Optional
from app.config import settings

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn

def init_db() -> None:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS services (
        service_id TEXT PRIMARY KEY,
        category TEXT NOT NULL,
        canonical_name TEXT NOT NULL,
        search_aliases TEXT NOT NULL,
        price_inr INTEGER NOT NULL,
        fasting_required INTEGER DEFAULT 0,
        full_bladder_required INTEGER DEFAULT 0,
        prescription_mandatory INTEGER DEFAULT 0,
        prep_instructions TEXT NOT NULL,
        report_tat TEXT NOT NULL,
        home_visit_available INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS doctors (
        doctor_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        department TEXT NOT NULL,
        qualification TEXT NOT NULL,
        available_days TEXT NOT NULL,
        timings TEXT NOT NULL,
        fee_inr INTEGER NOT NULL
    );

    CREATE TABLE IF NOT EXISTS appointments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        patient_name TEXT NOT NULL,
        phone TEXT NOT NULL,
        service_requested TEXT NOT NULL,
        preferred_slot TEXT NOT NULL,
        status TEXT DEFAULT 'PENDING_RECEPTION_CALL',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS clinic_status (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    """)
    cursor.execute(
        "INSERT OR IGNORE INTO clinic_status (key, value) VALUES ('operational_notice', 'OPEN_NORMAL')"
    )
    conn.commit()
    conn.close()

def fetch_all_services() -> List[Dict[str, Any]]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM services").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def fetch_all_doctors() -> List[Dict[str, Any]]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM doctors").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def create_appointment(session_id: str, name: str, phone: str, service: str, slot: str) -> int:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO appointments (session_id, patient_name, phone, service_requested, preferred_slot) VALUES (?, ?, ?, ?, ?)",
        (session_id, name, phone, service, slot),
    )
    appt_id = cur.lastrowid
    conn.commit()
    conn.close()
    return appt_id

def get_operational_notice() -> Optional[str]:
    conn = get_connection()
    row = conn.execute("SELECT value FROM clinic_status WHERE key='operational_notice'").fetchone()
    conn.close()
    if row and row["value"] != "OPEN_NORMAL":
        return row["value"]
    return None
```

### 4.5 `app/seed_data.py`
```python
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
    ("USG_ABD", "USG", "USG Whole Abdomen (Sonography)", "abdomen sonography, pet ka scan, usg whole abdomen, liver gallbladder sonography, stomach scan", 1000, 1, 1, 0, "1) 6 hours fasting required (no food/tea). 2) Drink 1 liter (4-5 glasses) of plain water 1 hour before scan and DO NOT urinate so bladder is full.", "Report handed over within 30 minutes of scan", 0),
    ("USG_KUB", "USG", "USG KUB / Pelvis (Kidney, Ureter, Bladder / Lower Abdomen)", "kub sonography, kidney stone scan, pathri ka scan, pelvis sonography, prostate scan, uterus scan", 900, 0, 1, 0, "No fasting needed. Drink 1 liter of water 45-60 minutes prior to the scan and hold urine (Full Bladder mandatory).", "Report handed over within 30 minutes of scan", 0),
    ("USG_OBS", "USG", "Obstetric / Pregnancy Ultrasound (ANC / Growth / NT Scan)", "pregnancy sonography, anc scan, baby growth scan, nt scan, garbhvati sonography, Anomaly scan", 1300, 0, 0, 1, "MANDATORY BY LAW (PCPNDT Act): Patient MUST bring original Doctor Prescription showing Doctor Registration Number AND Patient's Original Government Photo ID (Aadhaar/Voter ID/PAN).", "Report handed over within 30 minutes of scan", 0),

    # PHYSIOTHERAPY
    ("PHYSIO_SESSION", "PHYSIO", "Physiotherapy Rehabilitation Session (IFT / TENS / Ultrasound / Manual Therapy)", "physiotherapy, kasrat, kamar dard therapy, knee pain exercise, frozen shoulder, slip disc physio, paralysis rehab, neck pain traction", 400, 0, 0, 0, "Wear loose, comfortable clothing. Bring previous X-Ray or MRI reports if available. Both male and female physiotherapists available.", "45-minute guided clinical session", 1),
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
    conn.close()

if __name__ == "__main__":
    seed_database()
    print("Database seeded successfully.")
```

### 4.6 `app/guardrails.py`
```python
import re
from typing import Optional, Dict, Any
from app.config import settings

# 1. Statutory PCPNDT Act Interceptor (Strict Indian Medical Law Compliance)
PCPNDT_PATTERNS = [
    r"\b(gender|sex)\s*(test|check|determination|scan|detect|identify|know|pata)\b",
    r"\b(ladka|ladki|boy|girl|beta|beti|mulga|mulgi)\b.*\b(hai|hoga|pata|check|sonography|scan|usg|test)\b",
    r"\b(sonography|scan|usg|ultrasound)\b.*\b(ladka|ladki|boy|girl|beta|beti|mulga|mulgi|gender|sex)\b",
    r"\b(baby|fetus|foetus|garbh)\s*(ka|ki|ache)?\s*(gender|sex|ling)\b",
]

# 2. Acute Emergency Triage Interceptor
EMERGENCY_PATTERNS = [
    r"\b(chest\s*pain|chhati\s*mein\s*dard|seene\s*mein\s*dard|heart\s*attack)\b",
    r"\b(breathing\s*problem|saans\s*nahi|saans\s*lene\s*mein\s*takleef|breathless|shortness\s*of\s*breath)\b",
    r"\b(unconscious|behosh|fainted|stroke|paralysis\s*attack|lakwa\s*attack)\b",
    r"\b(heavy\s*bleeding|khoon\s*band\s*nahi|vomiting\s*blood|khoon\s*ki\s*ulti)\b",
    r"\b(suicid|self\s*harm|poison|zeher)\b",
]

# 3. Clinical Diagnosis / Report Interpretation / Prescription Refusal Interceptor
DIAGNOSIS_PATTERNS = [
    r"\b(konsi\s*dawa|kaunsi\s*medicine|which\s*medicine|prescribe\s*medicine|tablet\s*batao|treatment\s*batao)\b",
    r"\b(mera\s*creatinine|mera\s*hemoglobin|meri\s*report\s*normal\s*hai\s*kya|interpret\s*my\s*report|read\s*my\s*xray)\b",
]

# 4. Out-of-Scope Services Interceptor
OUT_OF_SCOPE_PATTERNS = [
    r"\b(mri|ct\s*scan|pet\s*scan|mammography|endoscopy|colonoscopy|dialysis|icu|admission|surgery|operation)\b"
]

def evaluate_guardrails(user_query: str) -> Optional[Dict[str, Any]]:
    """
    Deterministic, zero-latency CPU safety filter. Executes BEFORE any RAG or LLM call.
    """
    text = user_query.lower().strip()

    for pat in PCPNDT_PATTERNS:
        if re.search(pat, text):
            return {
                "status": "BLOCKED_PCPNDT",
                "confidence": 1.0,
                "reply": (
                    "⚠️ **Statutory Legal Notice (PCPNDT Act):** Under the Pre-Conception and Pre-Natal "
                    "Diagnostic Techniques (PCPNDT) Act of India, fetal sex/gender determination is a "
                    "strictly punishable criminal offense. **Dar ul Shifa Diagnostic Center** strictly "
                    "prohibits gender testing and will never disclose the sex of a fetus."
                ),
            }

    for pat in EMERGENCY_PATTERNS:
        if re.search(pat, text):
            return {
                "status": "EMERGENCY_TRIAGE",
                "confidence": 1.0,
                "reply": (
                    "🚨 **Medical Emergency Alert:** Your symptoms indicate a potential acute medical emergency. "
                    f"**{settings.CLINIC_NAME}** is an outpatient diagnostic and physiotherapy center, not a 24x7 "
                    "emergency hospital. Please proceed **immediately** to the nearest hospital casualty/ER "
                    "(such as Sion Hospital, KEM Hospital, JJ Hospital, or the nearest emergency room) or call **108 / 112**."
                ),
            }

    for pat in DIAGNOSIS_PATTERNS:
        if re.search(pat, text):
            return {
                "status": "CLINICAL_ADVICE_REFUSAL",
                "confidence": 1.0,
                "reply": (
                    "🩺 **Clinical Safety Notice:** As an automated clinic assistant, I cannot diagnose medical "
                    "conditions, interpret abnormal lab values, or prescribe medications. You can book an "
                    f"**OPD Consultation (₹300)** with our physician at **{settings.CLINIC_NAME}** to review "
                    "your reports in detail. Reply **'Book OPD'** or call us at "
                    f"**{settings.CLINIC_PHONE}**."
                ),
            }

    for pat in OUT_OF_SCOPE_PATTERNS:
        match = re.search(pat, text)
        if match:
            found = match.group(1).upper()
            return {
                "status": "OUT_OF_SCOPE_SERVICE",
                "confidence": 0.95,
                "reply": (
                    f"We currently do not perform **{found}** at {settings.CLINIC_NAME}. "
                    "Our center provides **Blood Tests (Pathology), Digital X-Ray, Ultrasonography (USG), "
                    "Physiotherapy, and Doctor Consultations (OPD)**. Let me know if you need prices or "
                    "timings for any of these services!"
                ),
            }

    return None
```

### 4.7 `app/semantics.py`
```python
import re
from typing import List, Dict, Any, Tuple
from rank_bm25 import BM25Okapi
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from app.database import fetch_all_services, fetch_all_doctors

# Multilingual / Mumbai Hinglish / Marathi / Urdu Normalizer
COLLOQUIAL_NORMALIZATION_MAP = {
    "khoon": "blood",
    "rakta": "blood",
    "jaanch": "test",
    "tapani": "test",
    "khali pet": "fasting",
    "nhar mu": "fasting",
    "nahar muh": "fasting",
    "khane ke baad": "post prandial ppbs",
    "sonography": "usg ultrasound sonography",
    "pet ka scan": "usg whole abdomen sonography",
    "pathri": "kidney stone kub usg",
    "garbhvati": "pregnancy obstetric usg",
    "chhati": "chest",
    "haddi": "bone xray ortho",
    "ghutne": "knee",
    "ghutna": "knee",
    "kamar": "back spine physiotherapy xray",
    "kasrat": "physiotherapy exercise rehab",
    "dava": "consultation doctor opd",
    "dikhana": "consultation doctor opd",
    "bukhar": "fever profile dengue malaria",
    "piliya": "jaundice lft liver",
    "charbi": "cholesterol lipid profile",
    "kitna": "price cost rate",
    "भाव": "price cost rate",
    "paisa": "price cost rate",
    "charges": "price cost rate",
    "fees": "price cost rate",
    "timing": "hours schedule open time",
    "kab khulta": "hours schedule open time",
    "ghar aake": "home visit collection",
}

class HybridSemanticRouter:
    """
    Zero-GPU, ultra-low RAM (<35MB) hybrid lexical + character/word n-gram semantic engine.
    Handles spelling mistakes, medical acronyms (CBC, LFT, USG, KUB), and Hinglish seamlessly.
    """
    def __init__(self) -> None:
        self.services: List[Dict[str, Any]] = []
        self.doctors: List[Dict[str, Any]] = []
        self.corpus_docs: List[str] = []
        self.bm25: BM25Okapi | None = None
        self.tfidf: TfidfVectorizer | None = None
        self.tfidf_matrix = None
        self.reload_index()

    def normalize_query(self, query: str) -> str:
        q = query.lower().strip()
        for slang, canonical in COLLOQUIAL_NORMALIZATION_MAP.items():
            if slang in q:
                q = f"{q} {canonical}"
        q = re.sub(r"[^a-z0-9\s]", " ", q)
        return re.sub(r"\s+", " ", q).strip()

    def reload_index(self) -> None:
        self.services = fetch_all_services()
        self.doctors = fetch_all_doctors()
        self.corpus_docs = []

        for s in self.services:
            doc = f"{s['service_id']} {s['category']} {s['canonical_name']} {s['search_aliases']} {s['prep_instructions']}".lower()
            self.corpus_docs.append(re.sub(r"[^a-z0-9\s]", " ", doc))

        if self.corpus_docs:
            tokenized = [d.split() for d in self.corpus_docs]
            self.bm25 = BM25Okapi(tokenized)
            # Combined char_wb (handles typos like 'sonografy' or 'lipd') + word n-grams
            self.tfidf = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5))
            self.tfidf_matrix = self.tfidf.fit_transform(self.corpus_docs)

    def retrieve(self, user_query: str, top_k: int = 4) -> Tuple[List[Dict[str, Any]], float, str]:
        normalized = self.normalize_query(user_query)
        if not self.services or not normalized:
            return [], 0.0, "GENERAL_INFO"

        tokens = normalized.split()
        bm25_scores = self.bm25.get_scores(tokens)
        max_bm25 = max(bm25_scores) if len(bm25_scores) > 0 and max(bm25_scores) > 0 else 1.0
        norm_bm25 = [s / max_bm25 for s in bm25_scores]

        q_vec = self.tfidf.transform([normalized])
        cos_scores = cosine_similarity(q_vec, self.tfidf_matrix).flatten()

        scored_items = []
        for idx, service in enumerate(self.services):
            # Exact alias token boost
            alias_tokens = set(re.sub(r"[^a-z0-9\s]", " ", service["search_aliases"].lower()).split())
            exact_overlap = len(set(tokens).intersection(alias_tokens))
            overlap_boost = min(0.35, exact_overlap * 0.18)

            hybrid_score = (0.45 * norm_bm25[idx]) + (0.55 * float(cos_scores[idx])) + overlap_boost
            scored_items.append((hybrid_score, service))

        scored_items.sort(key=lambda x: x[0], reverse=True)
        top_matches = [item[1] for item in scored_items[:top_k] if item[0] >= 0.22]
        best_score = float(scored_items[0][0]) if scored_items else 0.0

        intent = self.detect_general_intent(normalized, best_score)
        return top_matches, round(min(best_score, 1.0), 3), intent

    def detect_general_intent(self, normalized_query: str, best_score: float) -> str:
        booking_words = {"book", "appointment", "slot", "schedule", "register", "kal subah"}
        if any(w in normalized_query for w in booking_words):
            return "BOOK_APPOINTMENT"
        general_words = {"address", "location", "where", "kahan", "timing", "open", "close", "sunday", "contact", "phone", "number"}
        if any(w in normalized_query for w in general_words) and best_score < 0.45:
            return "CLINIC_LOGISTICS"
        return "SERVICE_INQUIRY"

    @staticmethod
    def check_preparation_conflicts(matched_services: List[Dict[str, Any]]) -> str:
        has_fasting = any(bool(s.get("fasting_required")) for s in matched_services)
        has_bladder = any(bool(s.get("full_bladder_required")) for s in matched_services)
        has_pcpndt_id = any(bool(s.get("prescription_mandatory")) for s in matched_services)

        notes = []
        if has_fasting and has_bladder:
            notes.append(
                "📌 **Combined Test Preparation Note (Fasting + Full Bladder):** You have inquired about both a "
                "Fasting test and a Sonography requiring a full bladder. Please fast overnight for 10–12 hours "
                "(no food, tea, coffee, or milk). However, **plain water does NOT break medical fasting**—please "
                "drink 1 liter (4–5 glasses) of plain water 1 hour before arriving and hold your urine so both "
                "your fasting blood sample and ultrasound can be completed in a single visit."
            )
        if has_pcpndt_id:
            notes.append(
                "🪪 **Mandatory Legal Requirement for Pregnancy USG:** Please bring the **Original Doctor's "
                "Prescription** AND the patient's **Original Government Photo ID (Aadhaar / PAN / Voter ID)** as "
                "strictly required under Form-F PCPNDT regulations in Mumbai."
            )
        return "\n\n".join(notes)
```

### 4.8 `app/session_manager.py`
```python
import re
from collections import OrderedDict
from typing import Dict, Any, Optional
from app.database import create_appointment
from app.config import settings

class BookingSessionManager:
    """
    Lightweight in-memory LRU state machine (max 500 active sessions, <2MB RAM)
    for handling multi-turn appointment and home-collection requests.
    """
    def __init__(self, max_sessions: int = 500) -> None:
        self.sessions: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self.max_sessions = max_sessions

    def get_session(self, session_id: str) -> Dict[str, Any]:
        if session_id not in self.sessions:
            if len(self.sessions) >= self.max_sessions:
                self.sessions.popitem(last=False)
            self.sessions[session_id] = {
                "active_booking": False,
                "step": None,
                "service": None,
                "name": None,
                "phone": None,
                "slot": None,
            }
        self.sessions.move_to_end(session_id)
        return self.sessions[session_id]

    def reset_session(self, session_id: str) -> None:
        if session_id in self.sessions:
            del self.sessions[session_id]

    def handle_booking_turn(self, session_id: str, user_message: str, preselected_service: Optional[str] = None) -> Optional[str]:
        state = self.get_session(session_id)
        msg = user_message.strip()

        if msg.lower() in {"cancel", "stop", "exit", "rehne do", "nahi chahiye"} and state["active_booking"]:
            self.reset_session(session_id)
            return "Your booking request has been cancelled. How else can I help you with Dar ul Shifa's services?"

        if not state["active_booking"]:
            state["active_booking"] = True
            if preselected_service:
                state["service"] = preselected_service
                state["step"] = "ASK_NAME"
                return (
                    f"I can schedule your request for **{preselected_service}** at {settings.CLINIC_NAME}. "
                    "Please tell me the **Patient's Full Name** (or type *'cancel'* anytime to stop):"
                )
            else:
                state["step"] = "ASK_SERVICE"
                return (
                    "I would be happy to book an appointment or home blood collection! "
                    "Which service do you need (**Blood Test, USG, X-Ray, Physiotherapy, or Doctor Consultation**)?"
                )

        if state["step"] == "ASK_SERVICE":
            state["service"] = msg
            state["step"] = "ASK_NAME"
            return f"Got it (**{msg}**). Please share the **Patient's Full Name**:"

        if state["step"] == "ASK_NAME":
            if len(msg) < 2:
                return "Please enter a valid patient name:"
            state["name"] = msg
            state["step"] = "ASK_PHONE"
            return f"Thank you, {state['name']}. Please enter your **10-digit Mobile Number** so our reception desk can confirm your slot:"

        if state["step"] == "ASK_PHONE":
            digits = re.sub(r"\D", "", msg)
            if len(digits) < 10:
                return "Please enter a valid 10-digit Indian mobile number (e.g., 9876543210):"
            state["phone"] = digits[-10:]
            state["step"] = "ASK_SLOT"
            return (
                "Which time slot do you prefer?\n"
                "• **Morning** (8:00 AM – 12:00 PM)\n"
                "• **Afternoon** (12:00 PM – 4:00 PM)\n"
                "• **Evening** (4:00 PM – 8:30 PM)"
            )

        if state["step"] == "ASK_SLOT":
            state["slot"] = msg
            appt_id = create_appointment(
                session_id=session_id,
                name=state["name"],
                phone=state["phone"],
                service=state["service"],
                slot=state["slot"],
            )
            summary = (
                f"✅ **Appointment Request Registered (Ref #{appt_id})**\n\n"
                f"• **Patient Name:** {state['name']}\n"
                f"• **Service:** {state['service']}\n"
                f"• **Preferred Slot:** {state['slot']}\n"
                f"• **Phone:** {state['phone']}\n\n"
                f"Our reception desk at **{settings.CLINIC_NAME}** will call/WhatsApp you shortly to confirm. "
                f"For urgent queries, call **{settings.CLINIC_PHONE}**."
            )
            self.reset_session(session_id)
            return summary

        return None
```

### 4.9 `app/llm_client.py`
```python
from typing import List, Dict, Any, Optional
from app.config import settings
from app.database import fetch_all_doctors, get_operational_notice

SYSTEM_PROMPT = """You are the official automated front-desk assistant for Dar ul Shifa Diagnostic Center in Mumbai.
We provide ONLY 5 core departments:
1. Blood Tests (Pathology)
2. Doctor Consultation (OPD)
3. Digital X-Ray
4. Ultrasonography (USG / Sonography)
5. Physiotherapy

STRICT GROUNDING RULES:
1. Use ONLY the facts provided inside <CLINIC_CONTEXT>. Never guess or fabricate test prices, timings, or doctor names.
2. If the user asks in Hinglish, Marathi, or Roman Urdu, reply warmly in the same language style while keeping test names and ₹ prices crystal clear.
3. Always include preparation instructions (fasting, full bladder, or mandatory ID/prescription) whenever present in <CLINIC_CONTEXT>.
4. If <CONFLICT_WARNINGS> contains a note, include it prominently in your response.
5. Keep responses concise, structured with bullet points, and end by offering to book an appointment if relevant.
"""

def build_context_block(matched_services: List[Dict[str, Any]], conflict_note: str) -> str:
    doctors = fetch_all_doctors()
    notice = get_operational_notice()
    lines = [
        "<CLINIC_CONTEXT>",
        f"Clinic Name: {settings.CLINIC_NAME}",
        f"Address: {settings.CLINIC_ADDRESS}",
        f"Timings: {settings.CLINIC_TIMINGS}",
        f"Contact Phone: {settings.CLINIC_PHONE} | WhatsApp: {settings.CLINIC_WHATSAPP}",
    ]
    if notice:
        lines.append(f"LIVE CLINIC STATUS NOTICE: {notice}")

    if matched_services:
        lines.append("\nMATCHED DIAGNOSTIC SERVICES:")
        for s in matched_services:
            home_tag = "Yes (Home Collection Available)" if s["home_visit_available"] else "Clinic Visit Required"
            lines.append(
                f"- {s['canonical_name']} [{s['category']}]: Price = ₹{s['price_inr']} | "
                f"Prep = {s['prep_instructions']} | Report TAT = {s['report_tat']} | Home Visit = {home_tag}"
            )

    lines.append("\nDOCTORS & DEPARTMENTS:")
    for d in doctors:
        fee_str = f"₹{d['fee_inr']}" if d["fee_inr"] > 0 else "By Scan Package"
        lines.append(
            f"- {d['name']} ({d['qualification']}) - {d['department']}: {d['available_days']} ({d['timings']}) | Fee: {fee_str}"
        )
    lines.append("</CLINIC_CONTEXT>")

    if conflict_note:
        lines.append(f"\n<CONFLICT_WARNINGS>\n{conflict_note}\n</CONFLICT_WARNINGS>")

    return "\n".join(lines)

def deterministic_fallback_response(
    matched_services: List[Dict[str, Any]],
    conflict_note: str,
    confidence: float,
    intent: str,
) -> str:
    """
    Zero-dependency fallback formatter. Guarantees 100% uptime and accurate answers
    even when running completely offline or without a Gemini API key.
    """
    notice = get_operational_notice()
    header = f"📢 **Live Notice:** {notice}\n\n" if notice else ""

    if intent == "CLINIC_LOGISTICS" or not matched_services:
        doctors = fetch_all_doctors()
        doc_lines = "\n".join(
            [f"• **{d['name']}** ({d['department']}): {d['timings']}" for d in doctors]
        )
        return (
            f"{header}🏥 **{settings.CLINIC_NAME}**\n"
            f"📍 **Address:** {settings.CLINIC_ADDRESS}\n"
            f"🕒 **Timings:** {settings.CLINIC_TIMINGS}\n"
            f"📞 **Phone:** {settings.CLINIC_PHONE} | **WhatsApp:** {settings.CLINIC_WHATSAPP}\n\n"
            f"**Departments Available:** Blood Tests, Digital X-Ray, Sonography (USG), Physiotherapy, and Doctor Consultation.\n\n"
            f"**Doctors & Timings:**\n{doc_lines}\n\n"
            "Reply with any test name (e.g., *'CBC price'*, *'Abdomen sonography prep'*, *'Physiotherapy'*) or type **'Book Appointment'**!"
        )

    prefix = (
        "Here are the closest matching services at **Dar ul Shifa** (please confirm if you meant one of these):\n\n"
        if confidence < settings.HIGH_CONFIDENCE_THRESHOLD
        else f"Here are the details from **{settings.CLINIC_NAME}**:\n\n"
    )

    items = []
    for s in matched_services[:3]:
        home = "✅ Home collection available" if s["home_visit_available"] else "🏥 Clinic visit required"
        items.append(
            f"🔹 **{s['canonical_name']}** — **₹{s['price_inr']}**\n"
            f"   • **Preparation:** {s['prep_instructions']}\n"
            f"   • **Report Time:** {s['report_tat']} ({home})"
        )

    body = "\n\n".join(items)
    conflict_section = f"\n\n{conflict_note}" if conflict_note else ""
    footer = "\n\n💬 Would you like to schedule this? Reply **'Book Appointment'** or call **" + settings.CLINIC_PHONE + "**."
    return f"{header}{prefix}{body}{conflict_section}{footer}"

def generate_grounded_reply(
    user_query: str,
    matched_services: List[Dict[str, Any]],
    conflict_note: str,
    confidence: float,
    intent: str,
) -> str:
    # Low confidence clarification gate
    if 0.0 < confidence < settings.CLARIFICATION_THRESHOLD and intent != "CLINIC_LOGISTICS":
        return (
            f"I want to make sure I give you the exact rate and preparation at **{settings.CLINIC_NAME}**. "
            "Could you clarify which department you are looking for?\n"
            "• **Blood Tests** (e.g., CBC, Sugar, Lipid, Thyroid, Fever Profile)\n"
            "• **Sonography / USG** (e.g., Abdomen, KUB, Pelvis, Pregnancy Scan)\n"
            "• **Digital X-Ray** (e.g., Chest, Spine, Knee/Ortho)\n"
            "• **Physiotherapy** (Back/Knee pain, Rehab)\n"
            "• **Doctor Consultation (OPD)**\n\n"
            f"Or call our reception directly at **{settings.CLINIC_PHONE}**."
        )

    if not settings.GEMINI_API_KEY:
        return deterministic_fallback_response(matched_services, conflict_note, confidence, intent)

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        context_xml = build_context_block(matched_services, conflict_note)
        prompt = f"{context_xml}\n\nPATIENT QUERY: {user_query}"

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.0,
                max_output_tokens=450,
            ),
        )
        if response and response.text:
            return response.text.strip()
    except Exception:
        pass

    return deterministic_fallback_response(matched_services, conflict_note, confidence, intent)
```

### 4.10 `app/main.py`
```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import Optional, List
from app.seed_data import seed_database
from app.guardrails import evaluate_guardrails
from app.semantics import HybridSemanticRouter
from app.session_manager import BookingSessionManager
from app.llm_client import generate_grounded_reply

router_engine: Optional[HybridSemanticRouter] = None
session_mgr = BookingSessionManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    global router_engine
    seed_database()
    router_engine = HybridSemanticRouter()
    yield

app = FastAPI(
    title="Dar ul Shifa Diagnostic Center Chatbot API",
    version="1.0.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

class ChatRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1, max_length=1000)

class ChatResponse(BaseModel):
    reply: str
    intent: str
    confidence: float
    matched_service_ids: List[str] = []

@app.get("/")
async def serve_ui():
    return FileResponse("app/static/index.html")

@app.get("/health")
async def health():
    return {"status": "ok", "clinic": "Dar ul Shifa Diagnostic Center Mumbai"}

@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest) -> ChatResponse:
    global router_engine
    if router_engine is None:
        router_engine = HybridSemanticRouter()

    # LAYER 1: Deterministic Clinical & Legal Guardrails (<1ms)
    guardrail_hit = evaluate_guardrails(req.message)
    if guardrail_hit:
        return ChatResponse(
            reply=guardrail_hit["reply"],
            intent=guardrail_hit["status"],
            confidence=guardrail_hit["confidence"],
            matched_service_ids=[],
        )

    # Check if session is mid-booking
    current_session = session_mgr.get_session(req.session_id)
    if current_session["active_booking"]:
        booking_reply = session_mgr.handle_booking_turn(req.session_id, req.message)
        if booking_reply:
            return ChatResponse(
                reply=booking_reply,
                intent="BOOKING_FLOW",
                confidence=1.0,
                matched_service_ids=[],
            )

    # LAYER 2: Hybrid Lexical + Character N-Gram Semantic Retrieval
    matches, score, intent = router_engine.retrieve(req.message)

    # LAYER 3: Multi-Turn Booking Initiation if Intent is BOOK_APPOINTMENT
    if intent == "BOOK_APPOINTMENT":
        preselected = matches[0]["canonical_name"] if matches and score >= 0.35 else None
        booking_reply = session_mgr.handle_booking_turn(req.session_id, req.message, preselected_service=preselected)
        return ChatResponse(
            reply=booking_reply,
            intent="BOOK_APPOINTMENT",
            confidence=max(score, 0.9),
            matched_service_ids=[m["service_id"] for m in matches],
        )

    # LAYER 4: Preparation Conflict Resolution + Grounded Response Generation
    conflict_note = router_engine.check_preparation_conflicts(matches)
    reply_text = generate_grounded_reply(
        user_query=req.message,
        matched_services=matches,
        conflict_note=conflict_note,
        confidence=score,
        intent=intent,
    )

    return ChatResponse(
        reply=reply_text,
        intent=intent,
        confidence=score,
        matched_service_ids=[m["service_id"] for m in matches],
    )
```

### 4.11 `app/static/index.html`
```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Dar ul Shifa Diagnostic Center - Mumbai</title>
  <script src="[https://cdn.tailwindcss.com](https://cdn.tailwindcss.com)"></script>
</head>
<body class="bg-slate-100 h-screen flex flex-col items-center justify-center p-4">
  <div class="w-full max-w-lg bg-white rounded-2xl shadow-xl flex flex-col h-[90vh] overflow-hidden border border-slate-200">
    <!-- Header -->
    <div class="bg-emerald-800 text-white p-4 flex items-center justify-between">
      <div>
        <h1 class="font-bold text-lg">Dar ul Shifa Diagnostic Center</h1>
        <p class="text-xs text-emerald-100">Blood Tests • USG • X-Ray • Physio • OPD (Mumbai)</p>
      </div>
      <span class="bg-emerald-600 text-xs px-2.5 py-1 rounded-full font-medium">Online</span>
    </div>

    <!-- Quick Chips -->
    <div class="bg-slate-50 px-3 py-2 border-b flex gap-2 overflow-x-auto text-xs whitespace-nowrap">
      <button onclick="sendQuick('Blood test rates aur fasting rules batao')" class="bg-white border border-emerald-700 text-emerald-800 px-3 py-1 rounded-full hover:bg-emerald-50">🩸 Blood Tests</button>
      <button onclick="sendQuick('Abdomen Sonography price and preparation')" class="bg-white border border-emerald-700 text-emerald-800 px-3 py-1 rounded-full hover:bg-emerald-50">🖥️ Sonography (USG)</button>
      <button onclick="sendQuick('Chest aur Knee X-Ray charges')" class="bg-white border border-emerald-700 text-emerald-800 px-3 py-1 rounded-full hover:bg-emerald-50">🩻 Digital X-Ray</button>
      <button onclick="sendQuick('Physiotherapy session charges')" class="bg-white border border-emerald-700 text-emerald-800 px-3 py-1 rounded-full hover:bg-emerald-50">🏃 Physiotherapy</button>
      <button onclick="sendQuick('Doctor OPD consultation timings')" class="bg-white border border-emerald-700 text-emerald-800 px-3 py-1 rounded-full hover:bg-emerald-50">🩺 Doctor OPD</button>
      <button onclick="sendQuick('Book Appointment')" class="bg-emerald-700 text-white px-3 py-1 rounded-full hover:bg-emerald-800">📅 Book Slot</button>
    </div>

    <!-- Chat Messages -->
    <div id="chat-box" class="flex-1 p-4 overflow-y-auto space-y-3 text-sm">
      <div class="bg-slate-100 text-slate-800 p-3 rounded-xl max-w-[88%]">
        <strong>Assalamu Alaikum / Namaste!</strong> Welcome to <strong>Dar ul Shifa Diagnostic Center (Mumbai)</strong>.<br><br>
        Ask me in English, Hinglish, Marathi, or Urdu about:<br>
        • <strong>Blood Tests</strong> (CBC, Sugar, Lipid, Thyroid, Monsoon Fever Profile)<br>
        • <strong>Ultrasound / Sonography (USG)</strong> & Preparation<br>
        • <strong>Digital X-Ray</strong><br>
        • <strong>Physiotherapy</strong> & <strong>Doctor OPD Timings</strong>
      </div>
    </div>

    <!-- Input Box -->
    <form id="chat-form" class="p-3 border-t bg-white flex gap-2">
      <input
        id="user-input"
        type="text"
        placeholder="Type your question (e.g. Khali pet sugar aur sonography)..."
        class="flex-1 border border-slate-300 rounded-xl px-3.5 py-2 text-sm focus:outline-none focus:border-emerald-700"
        required
      />
      <button type="submit" class="bg-emerald-700 hover:bg-emerald-800 text-white px-4 py-2 rounded-xl text-sm font-medium">
        Send
      </button>
    </form>
  </div>

  <script>
    const sessionId = "sess_" + Math.random().toString(36).substring(2, 10);
    const chatBox = document.getElementById("chat-box");
    const chatForm = document.getElementById("chat-form");
    const userInput = document.getElementById("user-input");

    function appendMessage(text, isUser) {
      const div = document.createElement("div");
      div.className = isUser
        ? "bg-emerald-700 text-white p-3 rounded-xl max-w-[85%] ml-auto whitespace-pre-wrap"
        : "bg-slate-100 text-slate-800 p-3 rounded-xl max-w-[88%] whitespace-pre-wrap";
      div.innerHTML = text.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
      chatBox.appendChild(div);
      chatBox.scrollTop = chatBox.scrollHeight;
    }

    async function sendMessage(messageText) {
      appendMessage(messageText, true);
      userInput.value = "";
      try {
        const res = await fetch("/api/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ session_id: sessionId, message: messageText }),
        });
        const data = await res.json();
        appendMessage(data.reply, false);
      } catch (err) {
        appendMessage("Connection error. Please call reception directly.", false);
      }
    }

    function sendQuick(text) {
      sendMessage(text);
    }

    chatForm.addEventListener("submit", (e) => {
      e.preventDefault();
      if (userInput.value.trim()) sendMessage(userInput.value.trim());
    });
  </script>
</body>
</html>
```

### 4.12 `tests/test_system.py`
```python
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.seed_data import seed_database

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    seed_database()

client = TestClient(app)

def test_pcpndt_statutory_guardrail():
    """Must block gender determination queries in English and Hinglish with 100% precision."""
    queries = [
        "Sonography mein ladka hai ya ladki pata chalega kya?",
        "Do you do baby gender test in ultrasound?",
        "garbh ling check hota hai kya scan mein",
    ]
    for q in queries:
        res = client.post("/api/chat", json={"session_id": "test_pcpndt", "message": q})
        assert res.status_code == 200
        data = res.json()
        assert data["intent"] == "BLOCKED_PCPNDT"
        assert "PCPNDT" in data["reply"]

def test_emergency_triage_guardrail():
    """Must intercept chest pain and breathlessness and redirect to emergency casualty."""
    res = client.post(
        "/api/chat",
        json={"session_id": "test_er", "message": "Chhati mein bohot dard hai aur saans nahi aa rahi"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] == "EMERGENCY_TRIAGE"
    assert "108" in data["reply"]

def test_clinical_diagnosis_refusal():
    """Must refuse medication or report interpretation requests."""
    res = client.post(
        "/api/chat",
        json={"session_id": "test_diag", "message": "Mera creatinine 2.6 aaya hai konsi dawa lu?"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] == "CLINICAL_ADVICE_REFUSAL"

def test_hinglish_semantic_retrieval_and_combined_prep_conflict():
    """Must resolve 'khali pet sugar' (FBS) + 'pet ka scan' (USG Abdomen) and synthesize combined prep."""
    res = client.post(
        "/api/chat",
        json={"session_id": "test_conflict", "message": "khali pet sugar aur pet ka sonography dono ek saath karna hai"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "PATH_FBS" in data["matched_service_ids"]
    assert "USG_ABD" in data["matched_service_ids"]
    assert "plain water" in data["reply"].lower()

def test_multi_turn_appointment_booking_state_machine():
    """Must complete a 4-step slot-filling conversation and persist to SQLite."""
    sid = "test_booking_flow_1"
    r1 = client.post("/api/chat", json={"session_id": sid, "message": "Book appointment for Chest X-Ray"}).json()
    assert r1["intent"] == "BOOK_APPOINTMENT"

    r2 = client.post("/api/chat", json={"session_id": sid, "message": "Imran Siddiqui"}).json()
    assert "Mobile Number" in r2["reply"]

    r3 = client.post("/api/chat", json={"session_id": sid, "message": "9820112233"}).json()
    assert "Morning" in r3["reply"]

    r4 = client.post("/api/chat", json={"session_id": sid, "message": "Morning 9 AM"}).json()
    assert "Appointment Request Registered" in r4["reply"]
```

---

## 5. ANTIGRAVITY VERIFICATION PROTOCOL
After creating all files above, run the following commands in the Antigravity terminal tool:
1. `python -m venv .venv && source .venv/bin/activate` (or `.venv\Scripts\activate` on Windows)
2. `pip install -r requirements.txt`
3. `python -m app.seed_data`
4. `pytest -v`
5. Confirm all 5 test suites pass with `0 errors`, then start the server using `uvicorn app.main:app --host 0.0.0.0 --port 8000` and verify `/health` returns HTTP 200.