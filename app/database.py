import sqlite3
from typing import List, Dict, Any, Optional
import httpx
from app.config import settings

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn

def init_db() -> None:
    conn = get_connection()
    try:
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

        CREATE TABLE IF NOT EXISTS inquiries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            user_query TEXT NOT NULL,
            intent TEXT NOT NULL,
            matched_services TEXT,
            confidence REAL DEFAULT 0.0,
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
    finally:
        conn.close()

def fetch_all_services() -> List[Dict[str, Any]]:
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM services").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def fetch_all_doctors() -> List[Dict[str, Any]]:
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM doctors").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def create_appointment(session_id: str, name: str, phone: str, service: str, slot: str) -> int:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO appointments (session_id, patient_name, phone, service_requested, preferred_slot) VALUES (?, ?, ?, ?, ?)",
            (session_id, name, phone, service, slot),
        )
        appt_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()

    # Patch 8: Non-blocking Telegram notification with 2s timeout & silent exception catch
    if settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_RECEPTION_CHAT_ID:
        try:
            tg_msg = (
                f"📋 *New Appointment Alert (Ref #{appt_id})*\n\n"
                f"• *Patient:* {name}\n"
                f"• *Phone:* {phone}\n"
                f"• *Service:* {service}\n"
                f"• *Preferred Slot:* {slot}\n\n"
                f"Dar ul Shifa Front Desk Alert"
            )
            url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
            with httpx.Client(timeout=2.0) as client:
                client.post(url, json={"chat_id": settings.TELEGRAM_RECEPTION_CHAT_ID, "text": tg_msg, "parse_mode": "Markdown"})
        except Exception:
            pass

    return appt_id

def log_inquiry(session_id: str, query: str, intent: str, matched_services: str, confidence: float) -> int:
    """Stores every user query / lead inquiring for details."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO inquiries (session_id, user_query, intent, matched_services, confidence) VALUES (?, ?, ?, ?, ?)",
            (session_id, query, intent, matched_services, confidence),
        )
        inquiry_id = cur.lastrowid
        conn.commit()
        return inquiry_id
    finally:
        conn.close()

def get_latest_appointments(limit: int = 100) -> List[Dict[str, Any]]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM appointments ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def get_latest_inquiries(limit: int = 100) -> List[Dict[str, Any]]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM inquiries ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def update_appointment_status(appt_id: int, status: str) -> bool:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE appointments SET status = ? WHERE id = ?", (status, appt_id))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()

def get_dashboard_stats() -> Dict[str, Any]:
    conn = get_connection()
    try:
        total_appts = conn.execute("SELECT COUNT(*) FROM appointments").fetchone()[0]
        today_appts = conn.execute("SELECT COUNT(*) FROM appointments WHERE date(created_at) = date('now')").fetchone()[0]
        pending_appts = conn.execute("SELECT COUNT(*) FROM appointments WHERE status = 'PENDING_RECEPTION_CALL'").fetchone()[0]
        total_inquiries = conn.execute("SELECT COUNT(*) FROM inquiries").fetchone()[0]
        today_inquiries = conn.execute("SELECT COUNT(*) FROM inquiries WHERE date(created_at) = date('now')").fetchone()[0]
        return {
            "total_appointments": total_appts,
            "today_appointments": today_appts,
            "pending_calls": pending_appts,
            "total_inquiries": total_inquiries,
            "today_inquiries": today_inquiries,
        }
    finally:
        conn.close()

def get_operational_notice() -> Optional[str]:
    conn = get_connection()
    try:
        row = conn.execute("SELECT value FROM clinic_status WHERE key='operational_notice'").fetchone()
        if row and row["value"] != "OPEN_NORMAL":
            return row["value"]
        return None
    finally:
        conn.close()
