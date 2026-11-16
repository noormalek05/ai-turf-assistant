import os
import json
from datetime import datetime
from dotenv import load_dotenv
from groq import Groq
from backend.database import (
    get_available_slots,
    create_booking,
    calculate_price,
    lookup_bookings,
    cancel_booking,
    TURFS,
    ADDON_PRICES
)

load_dotenv()

TURF_NAME = os.getenv("TURF_NAME", "Noor's AI Turf")
client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL_NAME = "openai/gpt-oss-120b"

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "check_availability",
            "description": "Check open 1-hour slots for Classic Box and Grand Arena on a given date (YYYY-MM-DD).",
            "parameters": {
                "type": "object",
                "properties": {
                    "booking_date": {"type": "string", "description": "Date in YYYY-MM-DD format"}
                },
                "required": ["booking_date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "quote_price",
            "description": "Calculate exact price in INR for a turf, date, start time, duration, and optional add-ons.",
            "parameters": {
                "type": "object",
                "properties": {
                    "turf_name": {"type": "string", "enum": ["Classic Box", "Grand Arena"]},
                    "booking_date": {"type": "string", "description": "YYYY-MM-DD"},
                    "start_time": {"type": "string", "description": "24-hour format like '19:00'"},
                    "duration_hours": {"type": "integer"},
                    "addons": {"type": "string", "description": "Comma-separated keys from: extra_ball, extra_bat, drinks_crate, or 'None'"}
                },
                "required": ["turf_name", "booking_date", "start_time", "duration_hours"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "book_turf_slot",
            "description": "Confirm and save a new turf booking in the database.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_name": {"type": "string"},
                    "phone": {"type": "string", "description": "10-digit mobile number"},
                    "turf_name": {"type": "string", "enum": ["Classic Box", "Grand Arena"]},
                    "booking_date": {"type": "string", "description": "YYYY-MM-DD"},
                    "start_time": {"type": "string", "description": "24-hour format like '20:00'"},
                    "duration_hours": {"type": "integer"},
                    "addons": {"type": "string", "description": "Comma-separated add-on keys or 'None'"},
                    "language": {"type": "string", "enum": ["English", "Hindi"]}
                },
                "required": ["customer_name", "phone", "turf_name", "booking_date", "start_time", "duration_hours", "language"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_my_booking",
            "description": "Find existing bookings by customer phone number or booking ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "phone": {"type": "string", "description": "Customer 10-digit mobile number"},
                    "booking_id": {"type": "integer", "description": "Numeric Booking ID"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_turf_booking",
            "description": "Cancel an existing booking using its Booking ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "booking_id": {"type": "integer"}
                },
                "required": ["booking_id"]
            }
        }
    }
]


def get_system_prompt() -> str:
    today_str = datetime.now().strftime("%Y-%m-%d (%A)")
    return f"""You are the warm, natural, professional AI Call Receptionist for '{TURF_NAME}', a premium box cricket & football turf in Gujarat.
Today's date is {today_str}.

TURF DETAILS & PRICING:
- Two Pitches:
  1. 'Classic Box' (6v6 / 7v7 Box Cricket): Day (06:00-18:00) ₹700/hr | Night Floodlights (18:00-24:00) ₹1,000/hr.
  2. 'Grand Arena' (8v8 / 9v9 Box Cricket or Football): Day ₹1,000/hr | Night Floodlights ₹1,300/hr.
  - Weekend Surge (Saturday & Sunday): +₹200/hr on all slots.
- Free Amenities: 2 bats, 1 new tennis ball, stumps, LED floodlights, chilled RO drinking water, dugout seating, and free bike/car parking.
- Optional Add-ons: Extra Tennis Ball (₹80), Extra Bat (₹50), Cold Drinks Crate (₹150).
- Rules & Payment: Flat sports shoes or barefoot only (no metal spikes). No gutkha/outside food inside net. ₹300 UPI advance token (noorturf@upi) or pay at counter before match starts.

NATURAL CALL FLOW RULES:
1. Keep every spoken reply SHORT (1 to 3 sentences max), natural, and warm—like a real Gujarat turf receptionist. NEVER use markdown (*, #, bullets) or emojis because Text-to-Speech reads them aloud.
2. Language Rule:
   - Once the caller chooses or speaks Hindi/Hinglish, reply in polite conversational Hindi written in Devanagari script (e.g., "जी ज़रूर, कल रात 8 बजे Classic Box खाली है।").
   - If English, reply in friendly Indian English.
3. Step-by-Step Conversation (Do NOT ask 5 questions at once—ask 1 or 2 naturally):
   - Step A: Ask how you can help (new booking, rates/details, or check/cancel existing booking).
   - Step B: For booking, ask Date, Time & Duration, and Pitch preference (Classic Box or Grand Arena). Check availability first! If one pitch is booked, suggest the other pitch or nearest slot.
   - Step C: Quote exact price via `quote_price`, briefly mention free bat/ball and ask if they want any add-ons.
   - Step D: Ask their Name and 10-digit Mobile Number, then call `book_turf_slot` and confirm Booking ID + total amount."""


class TurfCallSession:
    def __init__(self, call_id: str, caller_phone: str = "Unknown"):
        self.call_id = call_id
        self.caller_phone = caller_phone
        self.language = "English"
        self.messages = [{"role": "system", "content": get_system_prompt()}]
        self.transcript_lines = []

    def get_initial_greeting(self) -> str:
        greeting = (
            f"Hello! Welcome to {TURF_NAME}. "
            f"Which language would you prefer to proceed in, English or Hindi? "
            f"नमस्ते! {TURF_NAME} में आपका स्वागत है। आप किस भाषा में बात करना चाहेंगे, English या हिंदी?"
        )
        self.messages.append({"role": "assistant", "content": greeting})
        self.transcript_lines.append(f"AI: {greeting}")
        return greeting

    def _detect_language(self, user_text: str):
        hindi_keywords = ["hindi", "हिंदी", "हिन्दी", "bhai", "kal", "aaj", "baje", "slot", "chahiye", "kitne", "kya", "hai", "haan", "ji"]
        lower = user_text.lower()
        if any("\u0900" <= ch <= "\u097f" for ch in user_text) or any(w in lower.split() for w in hindi_keywords):
            self.language = "Hindi"
        elif "english" in lower:
            self.language = "English"

    def process_user_input(self, user_text: str) -> str:
        self._detect_language(user_text)
        self.messages.append({"role": "user", "content": user_text})
        self.transcript_lines.append(f"Caller: {user_text}")

        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=self.messages,
            tools=TOOLS,
            tool_choice="auto",
            temperature=0.3,
            max_tokens=300
        )

        msg = response.choices[0].message

        if msg.tool_calls:
            self.messages.append(msg)
            for tool_call in msg.tool_calls:
                fn_name = tool_call.function.name
                args = json.loads(tool_call.function.arguments)

                if fn_name == "check_availability":
                    d = args["booking_date"]
                    tool_result = json.dumps({
                        "date": d,
                        "Classic Box available": get_available_slots(d, "Classic Box"),
                        "Grand Arena available": get_available_slots(d, "Grand Arena")
                    })
                elif fn_name == "quote_price":
                    addon_keys = [a.strip() for a in args.get("addons", "").split(",") if a.strip() in ADDON_PRICES]
                    price = calculate_price(
                        args.get("turf_name", "Classic Box"),
                        args["booking_date"],
                        args["start_time"],
                        args["duration_hours"],
                        addon_keys
                    )
                    tool_result = json.dumps({"estimated_total_inr": price})
                elif fn_name == "book_turf_slot":
                    args.setdefault("language", self.language)
                    args.setdefault("turf_name", "Classic Box")
                    args.setdefault("addons", "None")
                    result = create_booking(**args)
                    tool_result = json.dumps(result)
                elif fn_name == "check_my_booking":
                    records = lookup_bookings(phone=args.get("phone", ""), booking_id=args.get("booking_id"))
                    tool_result = json.dumps({"bookings": records})
                elif fn_name == "cancel_turf_booking":
                    result = cancel_booking(args["booking_id"])
                    tool_result = json.dumps(result)
                else:
                    tool_result = json.dumps({"error": "Unknown tool"})

                self.messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": tool_result
                })

            followup = client.chat.completions.create(
                model=MODEL_NAME,
                messages=self.messages,
                temperature=0.3,
                max_tokens=300
            )
            reply = followup.choices[0].message.content.strip()
        else:
            reply = msg.content.strip()

        self.messages.append({"role": "assistant", "content": reply})
        self.transcript_lines.append(f"AI: {reply}")
        return reply

    def get_full_transcript(self) -> str:
        return "\n".join(self.transcript_lines)


if __name__ == "__main__":
    session = TurfCallSession(call_id="TEST-002")
    print("AI:", session.get_initial_greeting())
    while True:
        user_msg = input("\nYou (type 'exit' to quit): ").strip()
        if user_msg.lower() == "exit":
            break
        print("AI:", session.process_user_input(user_msg))