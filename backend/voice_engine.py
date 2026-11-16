import os
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq
import edge_tts

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
RECORDINGS_DIR = Path(__file__).resolve().parent.parent / "recordings"
RECORDINGS_DIR.mkdir(exist_ok=True)

VOICE_ENGLISH = "en-IN-NeerjaNeural"
VOICE_HINDI = "hi-IN-SwaraNeural"


def transcribe_audio(audio_file_path: str) -> str:
    """Transcribes caller voice (Hindi, Hinglish, or English) using Groq Whisper."""
    with open(audio_file_path, "rb") as f:
        transcription = client.audio.transcriptions.create(
            file=(os.path.basename(audio_file_path), f.read()),
            model="whisper-large-v3-turbo",
            response_format="text"
        )
    return str(transcription).strip()


def _pick_voice(text: str, language: str = "English") -> str:
    """Picks Hindi voice if Devanagari text is present or language is Hindi; otherwise Indian English."""
    if any("\u0900" <= ch <= "\u097f" for ch in text) or language == "Hindi":
        return VOICE_HINDI
    return VOICE_ENGLISH


async def generate_speech_mp3(text: str, output_path: str, language: str = "English") -> str:
    """Converts AI text reply into natural Indian English or Hindi MP3 audio."""
    voice = _pick_voice(text, language)
    communicate = edge_tts.Communicate(text=text, voice=voice, rate="+5%")
    await communicate.save(output_path)
    return output_path


class CallRecorder:
    """Appends caller and AI audio segments into a single downloadable MP3 call recording."""
    def __init__(self, call_id: str):
        self.call_id = call_id
        self.recording_path = RECORDINGS_DIR / f"{call_id}.mp3"

    def append_audio_file(self, segment_path: str):
        if os.path.exists(segment_path):
            with open(segment_path, "rb") as src, open(self.recording_path, "ab") as dst:
                dst.write(src.read())

    def get_relative_url(self) -> str:
        if self.recording_path.exists():
            return f"/recordings/{self.call_id}.mp3"
        return ""