import os
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = (
    Path("/tmp/turf_bookings.db")
    if os.getenv("VERCEL")
    else Path(__file__).resolve().parent.parent / "turf_bookings.db"
)

TURFS = {
    "Classic Box": {"capacity": "6v6 / 7v7", "day_rate": 700, "night_rate": 1000},
    "Grand Arena": {"capacity": "8v8 / 9v9", "day_rate": 1000, "night_rate": 1300},
}

ADDON_PRICES = {
    "extra_ball": 80,
    "extra_bat": 50,
    "drinks_crate": 150,
}

OPERATING_HOURS = [
    "06:00", "07:00", "08:00", "09:00", "10:00", "11:00",
    "12:00", "13:00", "14:00", "15:00", "16:00", "17:00",
    "18:00", "19:00", "20:00", "21:00", "22:00", "23:00"
]


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_connection() as conn:
        # Check if old schema exists without turf_name; migrate cleanly if needed
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(bookings)").fetchall()]
        if cols and "turf_name" not in cols:
            conn.execute("DROP TABLE bookings")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_name TEXT NOT NULL,
                phone TEXT NOT NULL,
                turf_name TEXT NOT NULL DEFAULT 'Classic Box',
                booking_date TEXT NOT NULL,
                start_time TEXT NOT NULL,
                duration_hours INTEGER NOT NULL DEFAULT 1,
                addons TEXT DEFAULT 'None',
                total_price INTEGER NOT NULL,
                language TEXT DEFAULT 'English',
                status TEXT DEFAULT 'CONFIRMED',
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS call_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                call_id TEXT UNIQUE NOT NULL,
                caller_phone TEXT,
                language TEXT,
                summary TEXT DEFAULT '',
                transcript TEXT,
                recording_path TEXT,
                created_at TEXT NOT NULL
            )
        """)
        conn.commit()


def calculate_price(turf_name: str, booking_date: str, start_time: str, duration_hours: int, addons_list: list[str] | None = None) -> int:
    """Calculates exact INR price based on Turf, Day/Night floodlights, Weekend surge, and Add-ons."""
    turf = TURFS.get(turf_name, TURFS["Classic Box"])
    dt = datetime.strptime(booking_date, "%Y-%m-%d")
    is_weekend = dt.weekday() in (5, 6)  # Saturday=5, Sunday=6
    weekend_extra = 200 if is_weekend else 0

    start_hour = int(start_time.split(":")[0])
    total = 0
    for i in range(duration_hours):
        hr = start_hour + i
        base = turf["night_rate"] if hr >= 18 else turf["day_rate"]
        total += base + weekend_extra

    if addons_list:
        for item in addons_list:
            total += ADDON_PRICES.get(item, 0)
    return total


def get_booked_slots(booking_date: str, turf_name: str = "Classic Box") -> list[str]:
    init_db()
    occupied = set()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT start_time, duration_hours FROM bookings WHERE booking_date = ? AND turf_name = ? AND status = 'CONFIRMED'",
            (booking_date, turf_name)
        ).fetchall()

    for row in rows:
        start_hour = int(row["start_time"].split(":")[0])
        for offset in range(row["duration_hours"]):
            occupied.add(f"{start_hour + offset:02d}:00")
    return sorted(occupied)


def get_available_slots(booking_date: str, turf_name: str = "Classic Box") -> list[str]:
    booked = set(get_booked_slots(booking_date, turf_name))
    return [slot for slot in OPERATING_HOURS if slot not in booked]


def create_booking(
    customer_name: str,
    phone: str,
    booking_date: str,
    start_time: str,
    duration_hours: int = 1,
    turf_name: str = "Classic Box",
    addons: str = "None",
    language: str = "English"
) -> dict:
    init_db()
    if turf_name not in TURFS:
        turf_name = "Classic Box"
    if start_time not in OPERATING_HOURS:
        return {"success": False, "error": f"Invalid time {start_time}. Operating hours are 06:00 to 23:00."}

    start_hour = int(start_time.split(":")[0])
    if start_hour + duration_hours > 24:
        return {"success": False, "error": "Booking exceeds closing time (24:00)."}

    booked = set(get_booked_slots(booking_date, turf_name))
    needed_slots = [f"{start_hour + i:02d}:00" for i in range(duration_hours)]
    conflicts = [s for s in needed_slots if s in booked]
    if conflicts:
        return {"success": False, "error": f"{turf_name} slot(s) {', '.join(conflicts)} already booked on {booking_date}."}

    addon_keys = [a.strip() for a in addons.split(",") if a.strip() in ADDON_PRICES]
    total_price = calculate_price(turf_name, booking_date, start_time, duration_hours, addon_keys)
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO bookings (customer_name, phone, turf_name, booking_date, start_time, duration_hours, addons, total_price, language, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'CONFIRMED', ?)
            """,
            (customer_name, phone, turf_name, booking_date, start_time, duration_hours, addons or "None", total_price, language, created_at)
        )
        conn.commit()
        booking_id = cursor.lastrowid

    return {
        "success": True,
        "booking_id": booking_id,
        "customer_name": customer_name,
        "phone": phone,
        "turf_name": turf_name,
        "booking_date": booking_date,
        "start_time": start_time,
        "duration_hours": duration_hours,
        "addons": addons or "None",
        "total_price": total_price
    }


def lookup_bookings(phone: str = "", booking_id: int | None = None) -> list[dict]:
    init_db()
    with get_connection() as conn:
        if booking_id:
            rows = conn.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,)).fetchall()
        elif phone:
            rows = conn.execute("SELECT * FROM bookings WHERE phone LIKE ? ORDER BY id DESC", (f"%{phone[-10:]}%",)).fetchall()
        else:
            rows = []
    return [dict(r) for r in rows]


def cancel_booking(booking_id: int) -> dict:
    init_db()
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,)).fetchone()
        if not row:
            return {"success": False, "error": f"Booking ID {booking_id} not found."}
        if row["status"] == "CANCELLED":
            return {"success": False, "error": f"Booking ID {booking_id} is already cancelled."}
        conn.execute("UPDATE bookings SET status = 'CANCELLED' WHERE id = ?", (booking_id,))
        conn.commit()
    return {"success": True, "booking_id": booking_id, "message": f"Booking ID {booking_id} has been cancelled."}


def save_call_log(call_id: str, caller_phone: str, language: str, transcript: str, recording_path: str = "", summary: str = ""):
    init_db()
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO call_logs (call_id, caller_phone, language, summary, transcript, recording_path, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (call_id, caller_phone, language, summary, transcript, recording_path, created_at)
        )
        conn.commit()


def get_all_bookings() -> list[dict]:
    init_db()
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM bookings ORDER BY booking_date DESC, start_time ASC").fetchall()
    return [dict(r) for r in rows]


def get_all_call_logs() -> list[dict]:
    init_db()
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM call_logs ORDER BY id DESC").fetchall()
    return [dict(r) for r in rows]