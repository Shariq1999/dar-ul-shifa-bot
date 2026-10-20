import io
import csv
from contextlib import asynccontextmanager
from fastapi import FastAPI, Response, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from app.seed_data import seed_database
from app.database import (
    get_latest_appointments,
    get_latest_inquiries,
    get_dashboard_stats,
    update_appointment_status,
    log_inquiry,
)
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

class StatusUpdateRequest(BaseModel):
    status: str = Field(..., min_length=1)

@app.get("/")
async def serve_ui():
    return FileResponse("app/static/index.html")

@app.get("/dashboard")
async def serve_dashboard():
    return FileResponse("app/static/dashboard.html")

@app.get("/health")
async def health():
    return {"status": "ok", "clinic": "Dar ul Shifa Diagnostic Center Mumbai"}

# Front-desk read-only endpoint for viewing latest appointments
@app.get("/api/appointments")
async def read_appointments() -> List[Dict[str, Any]]:
    return get_latest_appointments(limit=100)

# Inquiries / leads endpoint
@app.get("/api/inquiries")
async def read_inquiries() -> List[Dict[str, Any]]:
    return get_latest_inquiries(limit=100)

# Clinic dashboard statistics
@app.get("/api/stats")
async def read_stats() -> Dict[str, Any]:
    return get_dashboard_stats()

# Update appointment status (e.g. Confirmed, Called, Cancelled)
@app.patch("/api/appointments/{appt_id}/status")
async def change_appointment_status(appt_id: int, req: StatusUpdateRequest):
    success = update_appointment_status(appt_id, req.status)
    if not success:
        raise HTTPException(status_code=404, detail="Appointment not found")
    return {"status": "updated", "appt_id": appt_id, "new_status": req.status}

# Export Appointments to CSV
@app.get("/api/export/appointments.csv")
async def export_appointments_csv():
    records = get_latest_appointments(limit=1000)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Session ID", "Patient Name", "Phone", "Service Requested", "Preferred Slot", "Status", "Created At"])
    for r in records:
        writer.writerow([r.get("id"), r.get("session_id"), r.get("patient_name"), r.get("phone"), r.get("service_requested"), r.get("preferred_slot"), r.get("status"), r.get("created_at")])
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=dar_ul_shifa_appointments.csv"}
    )

# Export Inquiries to CSV
@app.get("/api/export/inquiries.csv")
async def export_inquiries_csv():
    records = get_latest_inquiries(limit=1000)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Session ID", "Query", "Intent", "Matched Services", "Confidence", "Created At"])
    for r in records:
        writer.writerow([r.get("id"), r.get("session_id"), r.get("user_query"), r.get("intent"), r.get("matched_services"), r.get("confidence"), r.get("created_at")])
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=dar_ul_shifa_inquiries.csv"}
    )

@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest) -> ChatResponse:
    global router_engine
    if router_engine is None:
        router_engine = HybridSemanticRouter()

    # LAYER 1: Deterministic Clinical & Legal Guardrails (<1ms)
    guardrail_hit = evaluate_guardrails(req.message)
    if guardrail_hit:
        log_inquiry(req.session_id, req.message, guardrail_hit["status"], "", guardrail_hit["confidence"])
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
        # If booking_reply is returned, respond. If None (Patch 5: mid-booking question escape), fall through!
        if booking_reply is not None:
            log_inquiry(req.session_id, req.message, "BOOKING_FLOW", "", 1.0)
            return ChatResponse(
                reply=booking_reply,
                intent="BOOKING_FLOW",
                confidence=1.0,
                matched_service_ids=[],
            )

    # LAYER 2: Hybrid Lexical + Character N-Gram Semantic Retrieval
    matches, score, intent = router_engine.retrieve(req.message)
    matched_ids = [m["service_id"] for m in matches]

    # LAYER 3: Multi-Turn Booking Initiation if Intent is BOOK_APPOINTMENT
    if intent == "BOOK_APPOINTMENT":
        preselected = matches[0]["canonical_name"] if matches and score >= 0.35 else None
        booking_reply = session_mgr.handle_booking_turn(req.session_id, req.message, preselected_service=preselected)
        log_inquiry(req.session_id, req.message, "BOOK_APPOINTMENT", ",".join(matched_ids), max(score, 0.9))
        return ChatResponse(
            reply=booking_reply,
            intent="BOOK_APPOINTMENT",
            confidence=max(score, 0.9),
            matched_service_ids=matched_ids,
        )

    # LAYER 4: Preparation Conflict Resolution + Grounded Response Generation
    conflict_note = router_engine.check_preparation_conflicts(matches, req.message)
    reply_text = generate_grounded_reply(
        user_query=req.message,
        matched_services=matches,
        conflict_note=conflict_note,
        confidence=score,
        intent=intent,
    )

    log_inquiry(req.session_id, req.message, intent, ",".join(matched_ids), score)

    return ChatResponse(
        reply=reply_text,
        intent=intent,
        confidence=score,
        matched_service_ids=matched_ids,
    )
