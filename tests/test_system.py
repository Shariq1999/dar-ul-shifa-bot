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

# Patch 10: Unit test for mid-booking cancellation with phrase "please cancel booking"
def test_mid_booking_cancellation_phrase():
    sid = "test_booking_cancel"
    # Initiate booking
    r1 = client.post("/api/chat", json={"session_id": sid, "message": "Book appointment for CBC"}).json()
    assert r1["intent"] == "BOOK_APPOINTMENT"

    # Mid-booking cancellation
    r2 = client.post("/api/chat", json={"session_id": sid, "message": "please cancel booking"}).json()
    assert "cancelled" in r2["reply"].lower() or "cancel" in r2["reply"].lower()

    # Next message should not be in booking flow
    r3 = client.post("/api/chat", json={"session_id": sid, "message": "CBC rate"}).json()
    assert r3["intent"] != "BOOKING_FLOW"

# Patch 10: Unit test for "I have an MRI report, need physiotherapy" routing to PHYSIO_SESSION
def test_mri_report_with_physio_not_blocked():
    res = client.post(
        "/api/chat",
        json={"session_id": "test_mri_physio", "message": "I have an MRI report, need physiotherapy"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] != "OUT_OF_SCOPE_SERVICE"
    assert "PHYSIO_SESSION" in data["matched_service_ids"]

# Patch 3: Unit test for PET scan disambiguation
def test_pet_scan_disambiguation():
    # Oncology terms -> Out of scope
    res_onc = client.post(
        "/api/chat",
        json={"session_id": "test_pet_onc", "message": "Need pet ct scan for cancer metastasis"},
    ).json()
    assert res_onc["intent"] == "OUT_OF_SCOPE_SERVICE"

    # Plain pet scan / pet ka scan -> USG Whole Abdomen
    res_abd = client.post(
        "/api/chat",
        json={"session_id": "test_pet_abd", "message": "pet ka scan kitne ka hai"},
    ).json()
    assert res_abd["intent"] != "OUT_OF_SCOPE_SERVICE"
    assert "USG_ABD" in res_abd["matched_service_ids"]
    assert "Abdomen" in res_abd["reply"] or "Stomach" in res_abd["reply"]

# Patch 5: Mid-booking question escape hatch
def test_mid_booking_question_escape():
    sid = "test_escape"
    r1 = client.post("/api/chat", json={"session_id": sid, "message": "Book appointment for CBC"}).json()
    assert r1["intent"] == "BOOK_APPOINTMENT"

    # Asking price question while in ASK_NAME step
    r2 = client.post("/api/chat", json={"session_id": sid, "message": "L-S spine X-ray ka rate kitna hai?"}).json()
    # Booking must be cancelled/escaped and question answered
    assert r2["intent"] != "BOOKING_FLOW"
    assert "XRAY_SPINE" in r2["matched_service_ids"]

# Patch 9: Admin appointments endpoint
def test_get_appointments_endpoint():
    res = client.get("/api/appointments")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert "patient_name" in data[0]

# 70% threshold clarification test
def test_70_percent_threshold_clarification():
    res = client.post(
        "/api/chat",
        json={"session_id": "test_vague", "message": "kuch batao"},
    ).json()
    # Low confidence query triggers department clarification
    assert "Blood Tests" in res["reply"] or "department" in res["reply"].lower()

def test_health_endpoint():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

def test_inquiries_logging_and_fetch():
    """Any customer inquiry must be stored and retrievable for lead tracking."""
    client.post("/api/chat", json={"session_id": "test_inq_1", "message": "Lipid profile rate kya hai?"})
    res = client.get("/api/inquiries")
    assert res.status_code == 200
    inquiries = res.json()
    assert len(inquiries) >= 1
    assert any("Lipid" in i["user_query"] for i in inquiries)

def test_dashboard_stats_endpoint():
    res = client.get("/api/stats")
    assert res.status_code == 200
    stats = res.json()
    assert "total_appointments" in stats
    assert "total_inquiries" in stats
    assert "pending_calls" in stats

def test_appointment_status_update():
    # Fetch first appointment
    appts = client.get("/api/appointments").json()
    assert len(appts) >= 1
    appt_id = appts[0]["id"]

    res = client.patch(f"/api/appointments/{appt_id}/status", json={"status": "CONFIRMED"})
    assert res.status_code == 200
    assert res.json()["new_status"] == "CONFIRMED"

def test_csv_export_endpoints():
    r_appts = client.get("/api/export/appointments.csv")
    assert r_appts.status_code == 200
    assert "text/csv" in r_appts.headers["content-type"]
    assert "Patient Name" in r_appts.text

    r_inq = client.get("/api/export/inquiries.csv")
    assert r_inq.status_code == 200
    assert "text/csv" in r_inq.headers["content-type"]
    assert "Query" in r_inq.text

def test_dashboard_ui_endpoint():
    res = client.get("/dashboard")
    assert res.status_code == 200
    assert "Dashboard" in res.text
