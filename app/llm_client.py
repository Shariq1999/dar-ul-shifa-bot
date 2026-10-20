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
            home_tag = "Yes (Home Collection Available)" if s.get("home_visit_available") else "Clinic Visit Required"
            lines.append(
                f"- {s['canonical_name']} [{s['category']}]: Price = ₹{s['price_inr']} | "
                f"Prep = {s['prep_instructions']} | Report TAT = {s['report_tat']} | Home Visit = {home_tag}"
            )

    lines.append("\nDOCTORS & DEPARTMENTS:")
    for d in doctors:
        fee_str = f"₹{d['fee_inr']}" if d.get("fee_inr", 0) > 0 else "By Scan Package"
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
        "Here are the closest matching services at **Dar ul Shifa**:\n\n"
        if confidence < settings.HIGH_CONFIDENCE_THRESHOLD
        else f"Here are the details from **{settings.CLINIC_NAME}**:\n\n"
    )

    items = []
    for s in matched_services[:3]:
        home = "✅ Home collection available" if s.get("home_visit_available") else "🏥 Clinic visit required"
        items.append(
            f"🔹 **{s['canonical_name']}** — **₹{s['price_inr']}**\n"
            f"   • **Preparation:** {s['prep_instructions']}\n"
            f"   • **Report Time:** {s['report_tat']} ({home})"
        )

    body = "\n\n".join(items)
    conflict_section = f"\n\n{conflict_note}" if conflict_note else ""
    footer = f"\n\n💬 Would you like to schedule this? Reply **'Book Appointment'** or call **{settings.CLINIC_PHONE}**."
    return f"{header}{prefix}{body}{conflict_section}{footer}"

def generate_grounded_reply(
    user_query: str,
    matched_services: List[Dict[str, Any]],
    conflict_note: str,
    confidence: float,
    intent: str,
) -> str:
    # 70% match threshold: if confidence < 0.70 and not pure logistics, ask for clarification
    if confidence < settings.CLARIFICATION_THRESHOLD and intent != "CLINIC_LOGISTICS":
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

    # Pure deterministic offline formatting (Zero-cost, 100% factual accuracy, zero hallucination)
    return deterministic_fallback_response(matched_services, conflict_note, confidence, intent)
