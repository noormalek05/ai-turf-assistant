# 🎙️ Noor's AI Turf Call Assistant

AI-Powered Bilingual Voice Receptionist & Automated Turf Booking Platform

## 🚀 Live Application

👉 https://ai-turf-assistant.vercel.app

**Noor's AI Turf Call Assistant** is a full-stack conversational voice AI application that combines **Telephony Automation (Twilio Voice)**, **Speech-to-Text (`Whisper-large-v3-turbo`)**, **LLM Reasoning (Groq)**, and **Neural Text-to-Speech (`Edge-TTS`)** to handle real-world customer phone calls and automate sports turf slot reservations.

It conducts natural, real-time conversations in both **English and Hindi**, checks real-time slot availability, confirms bookings, records call audio, and updates a live management dashboard.

---

## 🚀 Features

### 📞 Bilingual AI Voice Receptionist
* **Real-Time Phone Call Handling:** Answers incoming and outbound customer calls automatically via Twilio Voice webhooks (`/twilio/voice` and `/twilio/gather`)[cite: 10]
* **English & Hindi Language Support:** Greets callers bilingually[cite: 10], detects preferred language automatically, and responds using natural Indian voices (`en-IN-NeerjaNeural` and `hi-IN-SwaraNeural`)
* **Ultra-Fast Speech Recognition:** Transcribes Hindi, Hinglish, and English caller speech accurately using Groq's `whisper-large-v3-turbo` model
* **Conversational Slot Booking:** Extracts caller name, sport/turf preference, date, and time slot naturally across multi-turn dialogue

### 📊 Live Booking & Call Operations Dashboard
* **Real-Time Reservations Table:** Displays confirmed turf bookings, customer details, dates, and time slots
* **Call Logs & Transcripts:** Stores full conversation histories and call outcomes for quick review
* **Downloadable Call Recordings:** Stitches caller and AI audio segments into playable MP3 call recordings
* **Serverless Cloud Deployment:** Hosted 24/7 on Vercel with automatic HTTPS webhook routing[cite: 10]

---

## 🛠️ Tech Stack

* **Backend:** Python, FastAPI, Uvicorn
* **Telephony & Webhooks:** Twilio Voice API (TwiML)
* **Speech-to-Text & LLM:** Groq API (`whisper-large-v3-turbo`)
* **Text-to-Speech:** Microsoft Edge-TTS (`en-IN-NeerjaNeural`, `hi-IN-SwaraNeural`)
* **Database:** SQLite
* **Frontend:** HTML5, CSS3, Vanilla JavaScript
* **Deployment:** Vercel Serverless Functions[cite: 10]

---

## 📂 Project Structure

```text
ai-turf-assistant/
├── backend/
│   ├── main.py            # FastAPI routes & Twilio TwiML voice webhooks
│   ├── ai_brain.py        # Conversational LLM logic & booking extraction
│   ├── voice_engine.py    # Groq Whisper STT, Edge-TTS & MP3 call recorder
│   └── database.py        # SQLite booking & call log persistence
├── frontend/
│   └── index.html         # Live turf booking & call monitoring dashboard
├── requirements.txt       # Python dependencies
└── vercel.json            # Vercel serverless routing configuration
