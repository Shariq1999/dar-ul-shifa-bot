# 🏥 Dar ul Shifa Diagnostic Center Chatbot & Front-Desk Dashboard

A zero-cost, minimal-hardware clinical triage chatbot and front-desk patient lead dashboard for **Dar ul Shifa Diagnostic Center (Mumbai)**.

---

## 🌟 Key Features

1. **Patient Triage & Service Discovery**:
   - Covers all 5 departments: **Blood Tests (Pathology)**, **Doctor Consultation (OPD)**, **Digital X-Ray**, **Ultrasonography (USG)**, and **Physiotherapy**.
   - Handles English, Hinglish, Marathi, and Roman Urdu with 60+ colloquial normalizations.
   - Typo tolerance via `difflib`.
   - 70% confidence threshold: vague queries trigger a clear department clarification menu.
2. **Statutory Medical & Safety Guardrails**:
   - **PCPNDT Act Gate**: Strictly refuses fetal sex/gender determination.
   - **Emergency Casualty Triage**: Instantly redirects acute symptoms to 108 / nearest emergency hospital.
   - **Clinical Diagnosis Refusal**: Refuses prescription requests and lab report interpretations.
   - **Smart OOS**: Allows queries combining out-of-scope imaging with in-scope physiotherapy/OPD.
   - **PET Scan Disambiguation**: Differentiates Abdomen Ultrasound from nuclear PET-CT scans.
3. **Multi-Turn Appointment Booking**:
   - Guided 4-step clinic visit booking with +91 phone validation.
   - Token-based cancellation (`"cancel"`, `"stop"`, `"rehne do"`).
   - Mid-booking question escape hatch (resets and answers questions immediately).
4. **Front-Desk Clinic Dashboard (`/dashboard`)**:
   - Live metrics: Total Bookings, Today's Bookings, Pending Callbacks, Total Inquiries/Leads.
   - Lead tracking: Every question and inquiry from patients is permanently recorded.
   - Quick-action buttons to mark bookings as **`Confirmed`**, **`Called`**, or **`Cancelled`**.
   - Direct dial links (`tel:...`) for reception staff.
   - 1-click **CSV Export** for both appointments and inquiries.
5. **Zero-Cost & Pure Deterministic Mode**:
   - Operates 100% locally and offline without external API keys.
   - RAM footprint < 120MB, CPU-only.

---

## 🚀 How to Host on GitHub + Render.com

### Step 1: Push Code to Your GitHub Account

1. Open your terminal in this project folder:
   ```powershell
   # If not already initialized
   git remote add origin https://github.com/YOUR_USERNAME/dar-ul-shifa-bot.git
   git push -u origin main
   ```
   *(Replace `YOUR_USERNAME/dar-ul-shifa-bot` with your GitHub repo URL)*

---

### Step 2: Deploy to Render.com

1. Sign up or log into [Render.com](https://dashboard.render.com/) (Free).
2. Click **New +** → **Web Service**.
3. Select **Build and deploy from a Git repository** and connect your GitHub repo.
4. Render will auto-detect [`render.yaml`](./render.yaml). If setting up manually, configure:
   - **Name:** `dar-ul-shifa-bot`
   - **Runtime:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt && python -m app.seed_data`
   - **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Plan:** `Free`

---

### Step 3: Ensure Data is NEVER Wiped When Domain is Idle

To guarantee your patient appointments and inquiry leads are permanently preserved:

#### Option A: Attach a Render Persistent Disk (Most Reliable)
1. In your Render dashboard, navigate to your Web Service → **Disks**.
2. Click **Add Disk**:
   - **Name:** `clinic-data`
   - **Mount Path:** `/var/data`
   - **Size:** `1 GB`
3. Under **Environment**, add:
   - `DB_PATH` = `/var/data/darulshifa.db`
4. Save changes.
> **Why this works:** The `/var/data` disk is permanent block storage. Even if the domain is idle for days or months, your SQLite database file (`darulshifa.db`) is safely preserved.

#### Option B: Free Keep-Alive Monitor (Free Tier Without Paid Disk)
If using Render's 100% Free plan without attaching a disk:
1. Render gives **750 free compute hours/month** (more than enough for a service running 24/7).
2. Go to [UptimeRobot.com](https://uptimerobot.com/) (Free account).
3. Add a new monitor:
   - **Type:** `HTTP(s)`
   - **URL:** `https://your-app.onrender.com/health`
   - **Interval:** Every 10 minutes.
> **Why this works:** The periodic `/health` ping keeps the instance awake, so the container never spins down, keeping your database online and active 24/7.

---

## 📱 URLs After Deployment

| Purpose | URL |
|---|---|
| **Patient Chat UI** | `https://your-app.onrender.com/` |
| **Front-Desk Clinic Dashboard** | `https://your-app.onrender.com/dashboard` |
| **Download Bookings CSV** | `https://your-app.onrender.com/api/export/appointments.csv` |
| **Download Inquiries CSV** | `https://your-app.onrender.com/api/export/inquiries.csv` |
| **Health Check Endpoint** | `https://your-app.onrender.com/health` |

---

## 🧪 Running Tests Locally

```powershell
.venv\Scripts\Activate.ps1
pytest -v
```
All 17 test suites verify:
- Statutory PCPNDT refusal
- 108 Emergency triage
- Diagnosis/prescription refusal
- Combined fasting + full bladder conflict resolution
- 4-step booking state machine
- Mid-booking cancellation and question escape
- Smart OOS with physiotherapy
- PET scan disambiguation
- Dashboard metrics and inquiry logging
- CSV exports and health status
