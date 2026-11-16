import os
import uuid
import html
import sqlite3
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.responses import HTMLResponse, Response, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from backend.database import (
    init_db,
    get_all_bookings,
    get_all_call_logs,
    save_call_log,
    get_available_slots,
    TURFS
)
from backend.ai_brain import TurfCallSession
from backend.voice_engine import (
    transcribe_audio,
    generate_speech_mp3,
    CallRecorder,
    RECORDINGS_DIR
)

load_dotenv()

IS_VERCEL = bool(os.getenv("VERCEL"))
BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
TEMP_DIR = Path("/tmp/temp_audio") if IS_VERCEL else BASE_DIR / "temp_audio"
ACTIVE_RECORDINGS_DIR = Path("/tmp/recordings") if IS_VERCEL else RECORDINGS_DIR

TEMP_DIR.mkdir(parents=True, exist_ok=True)
ACTIVE_RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)

try:
    init_db()
except Exception as init_err:
    print("DB INIT WARNING:", init_err)

# Auto-fix missing 'summary' column in any existing SQLite database file
search_root = Path("/tmp") if IS_VERCEL else BASE_DIR
for db_file in search_root.rglob("*.db"):
    try:
        conn = sqlite3.connect(str(db_file))
        conn.execute("ALTER TABLE call_logs ADD COLUMN summary TEXT DEFAULT ''")
        conn.commit()
        conn.close()
    except Exception:
        pass

app = FastAPI(title="Noor's AI Turf Call Assistant")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/recordings", StaticFiles(directory=str(ACTIVE_RECORDINGS_DIR)), name="recordings")

ACTIVE_CALLS: dict[str, dict] = {}
VERCEL_DOMAIN = f"https://{os.getenv('VERCEL_URL')}" if os.getenv("VERCEL_URL") else ""
NGROK_BASE_URL = (
    os.getenv("PUBLIC_BASE_URL")
    or VERCEL_DOMAIN
    or "https://oaf-starch-stitch.ngrok-free.dev"
).rstrip("/")


@app.get("/", response_class=HTMLResponse)
async def serve_home():
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return HTMLResponse(content=index_file.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Frontend missing!</h1>")


@app.post("/api/call/start")
async def start_browser_call(caller_phone: str = Form("Web Caller")):
    call_id = f"CALL-{uuid.uuid4().hex[:8].upper()}"
    session = TurfCallSession(call_id=call_id, caller_phone=caller_phone)
    recorder = CallRecorder(call_id=call_id)

    greeting_text = session.get_initial_greeting()
    greet_public = ACTIVE_RECORDINGS_DIR / f"{call_id}_greet.mp3"
    await generate_speech_mp3(greeting_text, str(greet_public), language="Hindi")
    recorder.append_audio_file(str(greet_public))

    ACTIVE_CALLS[call_id] = {"session": session, "recorder": recorder}

    return {
        "call_id": call_id,
        "ai_text": greeting_text,
        "audio_url": f"/recordings/{call_id}_greet.mp3",
        "language": session.language
    }


@app.post("/api/call/turn")
async def process_call_turn(
    call_id: str = Form(...),
    audio: UploadFile | None = File(None),
    text_input: str = Form("")
):
    if call_id not in ACTIVE_CALLS:
        return JSONResponse(status_code=404, content={"error": "Call session not found."})

    session: TurfCallSession = ACTIVE_CALLS[call_id]["session"]
    recorder: CallRecorder = ACTIVE_CALLS[call_id]["recorder"]

    if audio is not None:
        ext = os.path.splitext(audio.filename or "input.webm")[1] or ".webm"
        user_audio_path = str(TEMP_DIR / f"{call_id}_{uuid.uuid4().hex[:6]}{ext}")
        with open(user_audio_path, "wb") as f:
            f.write(await audio.read())
        caller_text = transcribe_audio(user_audio_path)
    else:
        caller_text = text_input.strip()

    noise_words = {"", ".", "...", "you", "thank you.", "thanks for watching."}
    if caller_text.lower().strip() in noise_words:
        return {"call_id": call_id, "ignored": True}

    ai_reply = session.process_user_input(caller_text)

    turn_id = uuid.uuid4().hex[:6]
    ai_audio_filename = f"{call_id}_{turn_id}.mp3"
    ai_audio_public = ACTIVE_RECORDINGS_DIR / ai_audio_filename
    await generate_speech_mp3(ai_reply, str(ai_audio_public), language=session.language)
    recorder.append_audio_file(str(ai_audio_public))

    return {
        "call_id": call_id,
        "caller_text": caller_text,
        "ai_text": ai_reply,
        "audio_url": f"/recordings/{ai_audio_filename}",
        "language": session.language
    }


@app.post("/api/call/end")
async def end_browser_call(call_id: str = Form(...)):
    if call_id not in ACTIVE_CALLS:
        return {"status": "already_ended"}

    session: TurfCallSession = ACTIVE_CALLS[call_id]["session"]
    recorder: CallRecorder = ACTIVE_CALLS[call_id]["recorder"]

    transcript = session.get_full_transcript()
    rec_url = recorder.get_relative_url()
    summary = f"{session.language} Call ({len(session.transcript_lines)} turns)"

    try:
        save_call_log(
            call_id=call_id,
            caller_phone=session.caller_phone,
            language=session.language,
            transcript=transcript,
            recording_path=rec_url,
            summary=summary
        )
    except Exception as db_err:
        print("DB LOG WARNING:", db_err)

    del ACTIVE_CALLS[call_id]

    return {
        "status": "saved",
        "call_id": call_id,
        "recording_url": rec_url,
        "transcript": transcript
    }


@app.get("/api/admin/data")
async def get_admin_dashboard_data(date: str = ""):
    try:
        bookings = get_all_bookings()
        call_logs = get_all_call_logs()
    except Exception as e:
        print("ADMIN DATA WARNING:", e)
        bookings, call_logs = [], []

    total_revenue = sum(b["total_price"] for b in bookings if b.get("status") == "CONFIRMED")
    slots_info = {}
    if date:
        for t_name in TURFS:
            try:
                slots_info[t_name] = get_available_slots(date, t_name)
            except Exception:
                slots_info[t_name] = []

    return {
        "bookings": bookings,
        "call_logs": call_logs,
        "total_revenue": total_revenue,
        "slots_info": slots_info
    }


async def _get_twilio_params(request: Request) -> dict:
    params = dict(request.query_params)
    if request.method == "POST":
        form = await request.form()
        params.update(dict(form))
    return params


@app.api_route("/twilio/voice", methods=["GET", "POST"])
async def twilio_incoming_call(request: Request):
    params = await _get_twilio_params(request)
    call_sid = str(params.get("CallSid", f"TW-{uuid.uuid4().hex[:8]}"))
    caller_number = str(params.get("From", "Phone Caller"))

    try:
        session = TurfCallSession(call_id=call_sid, caller_phone=caller_number)
        greeting = html.escape(session.get_initial_greeting())
        ACTIVE_CALLS[call_sid] = {"session": session, "recorder": CallRecorder(call_sid)}
    except Exception as e:
        print("TWILIO VOICE ERROR:", e)
        greeting = "Welcome to Noor's AI Turf. Which language would you prefer, English or Hindi?"

    gather_url = f"{NGROK_BASE_URL}/twilio/gather"

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather input="speech" action="{gather_url}" method="POST" language="hi-IN" speechTimeout="auto">
        <Say voice="Polly.Aditi">{greeting}</Say>
    </Gather>
</Response>"""
    return Response(content=twiml, media_type="application/xml")


@app.api_route("/twilio/gather", methods=["GET", "POST"])
async def twilio_gather_speech(request: Request):
    params = await _get_twilio_params(request)
    call_sid = str(params.get("CallSid", f"TW-{uuid.uuid4().hex[:8]}"))
    speech_result = str(params.get("SpeechResult", "")).strip()

    try:
        if call_sid not in ACTIVE_CALLS:
            session = TurfCallSession(call_id=call_sid, caller_phone=str(params.get("From", "Phone Caller")))
            ACTIVE_CALLS[call_sid] = {"session": session, "recorder": CallRecorder(call_sid)}
        else:
            session = ACTIVE_CALLS[call_sid]["session"]

        raw_reply = (
            "Sorry, I didn't catch that. Could you please repeat?"
            if not speech_result
            else session.process_user_input(speech_result)
        )
        reply = html.escape(raw_reply)
    except Exception as e:
        print("TWILIO AI ERROR:", e)
        reply = "Sorry, I didn't catch that. Please repeat your booking request."

    try:
        save_call_log(
            call_id=call_sid,
            caller_phone=session.caller_phone,
            language=session.language,
            transcript=session.get_full_transcript(),
            recording_path=str(params.get("RecordingUrl", "")),
            summary="Live Twilio Phone Call"
        )
    except Exception as db_err:
        print("TWILIO DB LOG WARNING:", db_err)

    gather_url = f"{NGROK_BASE_URL}/twilio/gather"

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather input="speech" action="{gather_url}" method="POST" language="hi-IN" speechTimeout="auto">
        <Say voice="Polly.Aditi">{reply}</Say>
    </Gather>
</Response>"""
    return Response(content=twiml, media_type="application/xml")