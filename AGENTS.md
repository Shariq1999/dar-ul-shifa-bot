# AGENTS.md – DAR UL SHIFA DIAGNOSTIC CENTER BOT

## ARCHITECTURAL CONSTRAINTS & EXECUTION DIRECTIVES

1. **Zero-Cost & Minimal-Hardware Constraint**:
   - NEVER install `torch`, `tensorflow`, `transformers`, `sentence-transformers`, `langchain`, or `chromadb`. They exceed the 200MB RAM budget.
   - Use pure-Python + `scikit-learn` (TF-IDF character/word n-grams) + `rank_bm25` + `difflib` hybrid lexical-semantic scoring engine on standard library `sqlite3` (WAL mode). Total RAM footprint must stay under 120MB.
   - Use the official `google-genai` SDK (`from google import genai`) calling `gemini-2.5-flash` (Free Tier) with `temperature=0.0`.
   - Include a deterministic offline fallback formatter so the chatbot functions with 100% accuracy even if `GEMINI_API_KEY` is missing or rate-limited (HTTP 429).
   - Designed to run in perpetuity free of cost (e.g. on Oracle Cloud Always Free, Render Free tier, or local clinic CPU PC).

2. **Clinical & Statutory Safety Gate (Zero Tolerance)**:
   - Layer 1 (`app/guardrails.py`) MUST execute BEFORE any database search or LLM call.
   - **PCPNDT Act**: Any query matching fetal sex/gender determination keywords in English, Hinglish, Marathi, or Roman Urdu must immediately return the statutory legal refusal and NEVER invoke the LLM.
   - **Acute Medical Emergency**: Any query matching acute medical emergencies (chest pain, stroke, severe breathlessness, heavy bleeding, unconsciousness, poisoning) must immediately trigger an emergency casualty redirect (108 / nearest 24x7 hospital) and bypass appointment booking.
   - **Diagnosis / Prescription**: Any query asking for report interpretation, diagnosis, or medicine prescription must be refused and redirected to book an OPD Consultation.
   - **Smart Out-of-Scope (OOS)**: Do NOT block queries mentioning MRI or CT scan if the user is also asking about an in-scope service (physiotherapy, physio, kasrat, exercise, rehab, opd, consultation, doctor, xray, usg, sonography, blood).
   - **PET Scan Disambiguation**: Oncology/nuclear terms (cancer, nuclear, fdg, oncology, tumor, metastasis, pet-ct) trigger OUT_OF_SCOPE_SERVICE. Plain "pet scan" / "pet ka scan" is routed to USG_ABD (Abdomen Ultrasound / Stomach Scan) with a clarification note.

3. **70% Confidence Match Provision**:
   - A 70% threshold (`HIGH_CONFIDENCE_THRESHOLD = 0.70`, `CLARIFICATION_THRESHOLD = 0.70`) is enforced for understanding. Queries scoring below 0.70 prompt the user with a structured department selection menu to ensure precise understanding rather than low-confidence guessing.

4. **Multi-Turn Booking & Reception Alerts**:
   - In `handle_booking_turn()`, token-based cancellation handles "cancel", "stop", "exit", "abort", "rehne do", "nahi chahiye", "back".
   - Mid-booking question escape allows users asking questions mid-flow to reset and have their question answered immediately.
   - Reception notifications via Telegram and WhatsApp Business Cloud API are fired as non-blocking background tasks and silently no-op when unconfigured.
   - Front-desk read-only endpoint `GET /api/appointments` returns recent appointments.

5. **Zero-Hallucination Grounding**:
   - The LLM is strictly forbidden from inventing prices, timings, doctor names, or test preparations. It may only synthesize facts passed inside `<CLINIC_CONTEXT>` XML tags.
