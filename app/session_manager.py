import re
from collections import OrderedDict
from typing import Dict, Any, Optional
from app.database import create_appointment
from app.config import settings

CANCEL_PHRASES = ["rehne do", "nahi chahiye", "cancel booking", "please cancel booking"]
CANCEL_TOKENS = {"cancel", "stop", "exit", "abort", "back"}

INFO_QUESTION_SIGNALS = {
    "?", "price", "rate", "kitna", "kitne", "charges", "fees", "timing", "timings",
    "address", "kahan", "fasting", "khali pet", "prep", "preparation", "kab", "dawa"
}

class BookingSessionManager:
    """
    Lightweight in-memory LRU state machine (max 500 active sessions, <2MB RAM)
    for handling multi-turn appointment booking requests.
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

    def _is_cancellation(self, msg: str) -> bool:
        msg_lower = msg.lower().strip()
        if any(phrase in msg_lower for phrase in CANCEL_PHRASES):
            return True
        tokens = set(msg_lower.split())
        return bool(tokens.intersection(CANCEL_TOKENS))

    def _is_informational_question(self, msg: str) -> bool:
        msg_lower = msg.lower().strip()
        if "?" in msg_lower:
            return True
        tokens = set(re.sub(r"[^a-z0-9\s]", " ", msg_lower).split())
        return bool(tokens.intersection(INFO_QUESTION_SIGNALS))

    def handle_booking_turn(self, session_id: str, user_message: str, preselected_service: Optional[str] = None) -> Optional[str]:
        state = self.get_session(session_id)
        msg = user_message.strip()

        # Patch 4: Token and phrase cancellation matching
        if state["active_booking"] and self._is_cancellation(msg):
            self.reset_session(session_id)
            return "Your booking request has been cancelled. How else can I help you with Dar ul Shifa's services?"

        # Patch 5: Mid-booking question escape hatch for ASK_SERVICE and ASK_NAME
        if state["active_booking"] and state["step"] in {"ASK_SERVICE", "ASK_NAME"}:
            if self._is_informational_question(msg):
                self.reset_session(session_id)
                return None  # Let main.py fall through to Layer 2

        # Start booking flow if not yet active
        if not state["active_booking"]:
            state["active_booking"] = True
            if preselected_service:
                state["service"] = preselected_service
                state["step"] = "ASK_NAME"
                return (
                    f"I can schedule your clinic visit for **{preselected_service}** at {settings.CLINIC_NAME}. "
                    "Please tell me the **Patient's Full Name** (or type *'cancel'* anytime to stop):"
                )
            else:
                state["step"] = "ASK_SERVICE"
                return (
                    "I would be happy to book an appointment at our clinic! "
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
            if digits.startswith("91") and len(digits) == 12:
                digits = digits[2:]
            if len(digits) != 10 or digits[0] not in "6789":
                return "Please enter a valid 10-digit Indian mobile number (e.g., 9820112233):"
            state["phone"] = digits
            state["step"] = "ASK_SLOT"
            return (
                "Which clinic time slot do you prefer?\n"
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

            # Optional WhatsApp notification hook
            from app.whatsapp_notify import notify_reception_whatsapp_sync
            notify_reception_whatsapp_sync(appt_id, state["name"], state["phone"], state["service"], state["slot"])

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
