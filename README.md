# Noor's AI Turf Call Assistant

An end-to-end automated voice receptionist and sports turf booking system powered by **FastAPI**, **Twilio Voice API**, **Large Language Models (LLM)**, and **SQLite**. Designed to handle real-time bilingual phone conversations (**English & Hindi**), verify live slot availability, prevent double-bookings, and synchronize call transcripts and revenue analytics to a live admin dashboard.

---

## Key Features

- **Automated Bilingual Telephony (English & Hindi):** Integrates with Twilio Programmable Voice (`<Gather>` & Amazon Polly `Polly.Aditi`) for real-time speech-to-text capture and natural neural voice responses.
- **Stateful Conversational Booking Engine:** Multi-turn AI state machine (`ai_brain.py`) extracts turf preference (*Classic Box*, etc.), booking date, time slot, customer name, and phone number while enforcing conflict-free slot validation.
- **Real-Time Admin & Analytics Dashboard:** Single-page web interface displaying confirmed reservations, dynamic day/night pricing calculations, total revenue tracking, and searchable call transcripts.
- **Dual-Mode Call Testing:** Supports both live PSTN phone calls via Twilio webhooks and an interactive browser-based audio call simulator with MP3 recording playback.
- **Cloud-Ready Serverless Deployment:** Configured with environment-aware storage (`/tmp` fallback for Vercel serverless functions) and automatic SQLite schema migration.

---

## System Architecture

```text
Caller (PSTN Phone / Browser)
        │
        ▼
Twilio Voice Webhook (/twilio/voice & /twilio/gather)
        │
        ▼
FastAPI Backend (backend/main.py)
   ├──► Conversational AI Engine (backend/ai_brain.py)
   ├──► Voice & Audio Pipeline (backend/voice_engine.py)
   └──► SQLite Persistence Layer (backend/database.py)
        │
        ▼
Admin Dashboard & Live Metrics (frontend/index.html)