import re
import difflib
from typing import List, Dict, Any, Tuple
from rank_bm25 import BM25Okapi
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from app.database import fetch_all_services, fetch_all_doctors

# Comprehensive Multilingual / Mumbai Hinglish / Marathi / Urdu Normalization Map
COLLOQUIAL_NORMALIZATION_MAP = {
    # Blood & Pathology
    "khoon": "blood",
    "rakta": "blood",
    "jaanch": "test",
    "tapani": "test",
    "khali pet": "fasting",
    "nhar mu": "fasting",
    "nahar muh": "fasting",
    "khane ke baad": "post prandial ppbs",
    "sugar check": "blood glucose fasting ppbs hba1c diabetes",
    "sugar test": "blood glucose fasting ppbs hba1c diabetes",
    "thyroid": "thyroid profile tsh t3 t4",
    "thyroid badhna": "thyroid tsh t3 t4 hormonal weight gain",
    "liver kharab": "lft liver bilirubin sgpt jaundice",
    "jigar": "liver lft bilirubin",
    "piliya": "jaundice lft liver bilirubin",
    "kidney problem": "kft rft kidney creatinine urea renal",
    "gurda": "kidney kft rft creatinine renal",
    "gurde": "kidney kft rft creatinine renal",
    "vitamin ki kami": "vitamin d b12 combo haddi kamzori",
    "naso mein dard": "vitamin d b12 combo nerve pain",
    "bukhar": "fever profile cbc malaria dengue widal",
    "dengue": "fever profile dengue ns1 malaria cbc",
    "malaria": "fever profile malaria cbc widal dengue",
    "typhoid": "fever profile widal typhoid cbc",
    "charbi": "cholesterol lipid profile triglycerides",
    "cholesterol": "lipid profile cholesterol triglycerides",
    "hb kam": "cbc hemoglobin hemogram",
    "anemia": "cbc hemoglobin hemogram",
    "platelets": "cbc hemogram platelets",

    # Sonography / USG
    "sonography": "usg ultrasound sonography",
    "sonografy": "usg ultrasound sonography",
    "ultrasound": "usg ultrasound sonography",
    "pet scan": "usg whole abdomen sonography stomach scan",
    "pet ka scan": "usg whole abdomen sonography stomach scan",
    "pet ka sonography": "usg whole abdomen sonography",
    "pet sonography": "usg whole abdomen sonography",
    "stomach scan": "usg whole abdomen sonography",
    "pathri": "kidney stone kub usg pelvis",
    "kidney stone": "kidney stone kub usg pelvis",
    "garbhvati": "pregnancy obstetric usg anc growth scan",
    "pregnancy scan": "pregnancy obstetric usg anc growth scan",

    # Radiology / X-Ray
    "chhati": "chest xray",
    "chhati ka xray": "chest xray lungs",
    "khansi": "chest xray tb cough opd",
    "lungs xray": "chest xray pa view",
    "kamar": "back spine l-s spine physiotherapy xray",
    "reedh ki haddi": "spine l-s spine xray physiotherapy",
    "slip disc": "spine l-s spine xray physiotherapy",
    "haddi ka dard": "bone xray orthopedic physiotherapy",
    "ghutne": "knee xray joint physiotherapy ortho",
    "ghutna": "knee xray joint physiotherapy ortho",
    "pair ka xray": "knee xray bone ortho",

    # Physiotherapy
    "kasrat": "physiotherapy exercise rehab",
    "physio": "physiotherapy rehabilitation therapy",
    "kamar dard therapy": "physiotherapy l-s spine rehab",
    "frozen shoulder": "physiotherapy manual therapy electrotherapy",
    "paralysis rehab": "physiotherapy neuro rehab package",
    "stroke rehab": "physiotherapy neuro rehab package",

    # OPD / Doctor
    "dava": "consultation doctor opd physician",
    "dawa": "consultation doctor opd physician",
    "dikhana": "consultation doctor opd physician",
    "doctor ko dikhana": "consultation doctor opd physician",
    "bp check": "opd doctor consultation general physician blood pressure",
    "general physician": "doctor consultation opd general physician",

    # Pricing & Logistics
    "kitna": "price cost rate charges fees",
    "kitne": "price cost rate charges fees",
    "bhav": "price cost rate charges fees",
    "भाव": "price cost rate charges fees",
    "paisa": "price cost rate charges fees",
    "charges": "price cost rate charges fees",
    "rate": "price cost rate charges fees",
    "fees": "price cost rate charges fees",
    "timing": "hours schedule open time timings",
    "kab khulta": "hours schedule open time timings",
    "kahan hai": "address location directions",
    "ghar aake": "home visit collection",
    "home collection": "home visit collection",
}

QUESTION_STARTERS = {"what", "when", "do i need", "kya", "kitna", "kitne", "how", "kaise", "kab", "kahan", "charges", "fees", "price", "rate"}
EXPLICIT_BOOKING_PHRASES = [
    "book", "schedule", "register",
    "appointment chahiye", "appointment lena", "slot book",
    "kal subah book", "fix karo", "confirm karo"
]

class HybridSemanticRouter:
    """
    Zero-GPU, ultra-low RAM (<35MB) hybrid lexical + character/word n-gram semantic engine.
    Handles spelling mistakes, medical acronyms (CBC, LFT, USG, KUB), and Hinglish seamlessly.
    """
    def __init__(self) -> None:
        self.services: List[Dict[str, Any]] = []
        self.doctors: List[Dict[str, Any]] = []
        self.corpus_docs: List[str] = []
        self.vocabulary: List[str] = []
        self.bm25: BM25Okapi | None = None
        self.tfidf: TfidfVectorizer | None = None
        self.tfidf_matrix = None
        self.reload_index()

    def normalize_query(self, query: str) -> str:
        q = query.lower().strip()
        # Colloquial replacements
        for slang, canonical in COLLOQUIAL_NORMALIZATION_MAP.items():
            if slang in q:
                q = f"{q} {canonical}"

        # Clean non-alphanumeric except spaces
        q = re.sub(r"[^a-z0-9\s]", " ", q)
        tokens = q.split()

        # Typo correction via difflib against known vocabulary
        corrected_tokens = []
        for t in tokens:
            if len(t) >= 4 and t not in self.vocabulary:
                matches = difflib.get_close_matches(t, self.vocabulary, n=1, cutoff=0.78)
                if matches:
                    corrected_tokens.append(matches[0])
            corrected_tokens.append(t)

        return re.sub(r"\s+", " ", " ".join(corrected_tokens)).strip()

    def reload_index(self) -> None:
        self.services = fetch_all_services()
        self.doctors = fetch_all_doctors()
        self.corpus_docs = []

        vocab_set = set()
        for s in self.services:
            doc = f"{s['service_id']} {s['category']} {s['canonical_name']} {s['search_aliases']} {s['prep_instructions']}".lower()
            clean_doc = re.sub(r"[^a-z0-9\s]", " ", doc)
            self.corpus_docs.append(clean_doc)
            vocab_set.update(clean_doc.split())

        for d in self.doctors:
            doc = f"{d['doctor_id']} {d['name']} {d['department']} {d['qualification']}".lower()
            clean_doc = re.sub(r"[^a-z0-9\s]", " ", doc)
            vocab_set.update(clean_doc.split())

        self.vocabulary = list(vocab_set)

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
            # Exact alias & canonical token overlap boost
            searchable_text = f"{service['canonical_name']} {service['search_aliases']}".lower()
            target_tokens = set(re.sub(r"[^a-z0-9\s]", " ", searchable_text).split())
            exact_overlap = len(set(tokens).intersection(target_tokens))
            overlap_boost = min(0.35, exact_overlap * 0.18)

            hybrid_score = (0.45 * norm_bm25[idx]) + (0.55 * float(cos_scores[idx])) + overlap_boost
            scored_items.append((hybrid_score, service))

        scored_items.sort(key=lambda x: x[0], reverse=True)
        # Filter top matches with a baseline threshold
        top_matches = [item[1] for item in scored_items[:top_k] if item[0] >= 0.25]
        best_score = float(scored_items[0][0]) if scored_items else 0.0

        # Refined general intent detection (Patch 6)
        intent = self.detect_general_intent(user_query, normalized, best_score)
        return top_matches, round(min(best_score, 1.0), 3), intent

    def detect_general_intent(self, raw_query: str, normalized_query: str, best_score: float) -> str:
        """
        Patch 6: Refined BOOK_APPOINTMENT Intent.
        Only return 'BOOK_APPOINTMENT' when explicit booking action phrases are present
        AND the query is not an informational question starting with 'what', 'when', 'do i need', 'kya', or 'kitna'.
        """
        raw_lower = raw_query.lower().strip()
        tokens = raw_lower.split()
        first_token = tokens[0] if tokens else ""

        is_info_question = (
            first_token in QUESTION_STARTERS
            or raw_lower.startswith("what ")
            or raw_lower.startswith("when ")
            or raw_lower.startswith("do i need ")
            or raw_lower.startswith("kya ")
            or raw_lower.startswith("kitna ")
            or raw_lower.startswith("kitne ")
            or "?" in raw_lower
        )

        has_explicit_booking = any(phrase in raw_lower for phrase in EXPLICIT_BOOKING_PHRASES)

        if has_explicit_booking and not is_info_question:
            return "BOOK_APPOINTMENT"

        # Check logistics intent
        general_words = {"address", "location", "where", "kahan", "timing", "open", "close", "sunday", "contact", "phone", "number"}
        if any(w in normalized_query.split() for w in general_words) and best_score < 0.45:
            return "CLINIC_LOGISTICS"

        return "SERVICE_INQUIRY"

    @staticmethod
    def check_preparation_conflicts(matched_services: List[Dict[str, Any]], user_query: str = "") -> str:
        has_fasting = any(bool(s.get("fasting_required")) for s in matched_services)
        has_bladder = any(bool(s.get("full_bladder_required")) for s in matched_services)
        has_pcpndt_id = any(bool(s.get("prescription_mandatory")) for s in matched_services)

        notes = []
        # Fasting + Full bladder conflict resolution
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

        # Patch 3: Clarify Stomach Ultrasound vs Nuclear PET-CT scan if query asked for pet scan
        q_lower = user_query.lower()
        if "pet scan" in q_lower or "pet ka scan" in q_lower:
            notes.append(
                "💡 **Clarification on Scan:** Dar ul Shifa performs **USG Whole Abdomen (Sonography / Stomach Scan)**. "
                "We do not perform nuclear medicine PET-CT scans."
            )

        return "\n\n".join(notes)
