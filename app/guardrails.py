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

# 4. In-Scope Keywords for MRI / CT Context Disambiguation (Patch 2)
IN_SCOPE_KEYWORDS = [
    "physiotherapy", "physio", "kasrat", "exercise", "rehab",
    "opd", "consultation", "doctor", "xray", "x-ray", "usg", "sonography", "blood", "pathology"
]

# 5. Out-of-Scope Patterns (Excluding PET scan which is handled separately)
OUT_OF_SCOPE_PATTERNS = [
    r"\b(mri|ct\s*scan|mammography|endoscopy|colonoscopy|dialysis|icu|admission|surgery|operation)\b"
]

# 6. Oncology / Nuclear Medicine terms for PET-CT Disambiguation (Patch 3)
ONCOLOGY_NUCLEAR_PATTERNS = [
    r"\b(cancer|nuclear|fdg|oncology|tumor|tumour|metastasis|pet\s*ct|pet-ct)\b"
]

def evaluate_guardrails(user_query: str) -> Optional[Dict[str, Any]]:
    """
    Deterministic, zero-latency CPU safety filter. Executes BEFORE any RAG or LLM call.
    """
    text = user_query.lower().strip()

    # Layer 1.1: PCPNDT Statutory Gate
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

    # Layer 1.2: Acute Emergency Triage Gate
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

    # Layer 1.3: Clinical Diagnosis / Prescription Refusal Gate
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

    # Layer 1.4: PET Scan Disambiguation (Patch 3)
    if re.search(r"\b(pet\s*scan|pet\s*ct|pet-ct)\b", text):
        has_oncology = any(re.search(pat, text) for pat in ONCOLOGY_NUCLEAR_PATTERNS)
        if has_oncology:
            return {
                "status": "OUT_OF_SCOPE_SERVICE",
                "confidence": 0.95,
                "reply": (
                    f"We currently do not perform **PET-CT / Nuclear Oncology Scans** at {settings.CLINIC_NAME}. "
                    "Our center provides **Blood Tests (Pathology), Digital X-Ray, Ultrasonography (USG), "
                    "Physiotherapy, and Doctor Consultations (OPD)**. If you need Abdomen Ultrasound (Stomach Scan), "
                    "let me know!"
                ),
            }
        # If user simply says 'pet scan' or 'pet ka scan' without oncology terms, DO NOT BLOCK here.
        # It will be routed by HybridSemanticRouter to USG_ABD with clarification note.

    # Layer 1.5: Out-of-Scope Services Gate with In-Scope Disambiguation (Patch 2)
    for pat in OUT_OF_SCOPE_PATTERNS:
        match = re.search(pat, text)
        if match:
            found = match.group(1).upper()
            # Patch 2: Do NOT block queries mentioning mri or ct scan if the user is also asking about an in-scope service
            if found in ["MRI", "CT SCAN"] or "ct" in found.lower():
                has_in_scope = any(re.search(rf"\b{re.escape(k)}\b", text) for k in IN_SCOPE_KEYWORDS)
                if has_in_scope:
                    # Let it pass through to semantic router
                    continue

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
