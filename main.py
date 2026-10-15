from fastapi import FastAPI, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
from face_service import verify_staff_face
import os
import math
import shutil
import sqlite3
from fastapi.responses import FileResponse

app = FastAPI(title="SKIT023 Smart Attendance API - Final Edition")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.get("/")
def read_index():
    return FileResponse("index.html")

@app.get("/vericamp_admin")
def read_admin():
    return FileResponse("vericamp_admin.html")


DB_FOLDER = "staff_db"
PENDING_FACES = "pending_faces"
PROXY_EVIDENCE = "proxy_evidence"
os.makedirs(DB_FOLDER, exist_ok=True)
os.makedirs(PENDING_FACES, exist_ok=True)
os.makedirs(PROXY_EVIDENCE, exist_ok=True)
os.makedirs("temp", exist_ok=True)

CAMPUS_LAT = 26.8239
CAMPUS_LNG = 75.8648
ALLOWED_RADIUS = 250.0
APPROVED_WIFI = "SKIT_CAMPUS_WIFI"

def get_db():
    return sqlite3.connect("skit_attendance.db")

def init_db():
    conn = sqlite3.connect("skit_attendance.db")
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS staff (
        emp_id TEXT PRIMARY KEY, name TEXT, department TEXT, 
        photo_path TEXT, failed_attempts INTEGER DEFAULT 0, locked_until TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT, emp_id TEXT, date_str TEXT, 
        timestamp TEXT, distance_meters INTEGER, confidence REAL, status TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS leave_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT, emp_id TEXT, start_date TEXT, 
        end_date TEXT, reason TEXT, status TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS admin_alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT, emp_id TEXT, alert_message TEXT, 
        evidence_photo TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS face_update_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT, emp_id TEXT, reason TEXT, 
        new_photo_path TEXT, status TEXT)''')
    conn.commit()
    conn.close()

# Initialize tables on startup
init_db()

def calculate_distance_meters(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def is_staff_on_approved_leave(emp_id: str, check_date: str) -> bool:
    conn = get_db()
    cursor = conn.cursor()
    row = cursor.execute("""
        SELECT id FROM leave_requests 
        WHERE emp_id = ? AND status = 'APPROVED' 
        AND ? BETWEEN start_date AND end_date
    """, (emp_id, check_date)).fetchone()
    conn.close()
    return row is not None


# ==========================================================
# ADMIN STAFF REGISTRATION
# ==========================================================
@app.post("/admin/register")
async def register_staff(
    emp_id: str = Form(...),
    name: str = Form("Staff Member"),
    department: str = Form("CSE"),
    photo: UploadFile = File(...)
):
    emp_id = emp_id.upper().strip()
    path = os.path.join(DB_FOLDER, f"{emp_id}.jpg")
    with open(path, "wb") as buffer:
        buffer.write(await photo.read())

    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO staff (emp_id, name, department, photo_path, failed_attempts, locked_until) VALUES (?, ?, ?, ?, 0, NULL)",
        (emp_id, name, department, path)
    )
    conn.commit()
    conn.close()
    return {"status": "success", "message": f"Staff {emp_id} registered successfully!"}


# ==========================================================
# 1. ZERO-TOUCH POP-UP
# ==========================================================
@app.get("/staff/zero-touch-popup")
def zero_touch_popup(emp_id: str, lat: float, lng: float, wifi_ssid: str = ""):
    emp_id = emp_id.upper().strip()
    today_str = datetime.now().strftime("%Y-%m-%d")

    if is_staff_on_approved_leave(emp_id, today_str):
        return {"show_popup": False, "reason": "Staff is on APPROVED LEAVE today."}

    distance = calculate_distance_meters(lat, lng, CAMPUS_LAT, CAMPUS_LNG)
    inside_radius = distance <= ALLOWED_RADIUS
    on_wifi = wifi_ssid.strip().lower() == APPROVED_WIFI.lower()

    if inside_radius or on_wifi:
        return {
            "show_popup": True,
            "popup_title": "📍 Inside SKIT Campus Radius!",
            "popup_message": f"You are {int(distance)}m from center. Tap to mark Attendance.",
            "distance_meters": int(distance)
        }
    return {"show_popup": False, "distance_meters": int(distance)}


# ==========================================================
# 2. HOURLY POP-UP CHECKER
# ==========================================================
@app.get("/staff/hourly-attendance-popup")
def hourly_attendance_popup(emp_id: str):
    emp_id = emp_id.upper().strip()
    today_str = datetime.now().strftime("%Y-%m-%d")

    if is_staff_on_approved_leave(emp_id, today_str):
        return {"popup_required": False, "message": "On Approved Leave today."}

    conn = get_db()
    row = conn.execute(
        "SELECT timestamp FROM attendance WHERE emp_id = ? AND status = 'PRESENT' ORDER BY id DESC LIMIT 1",
        (emp_id,)
    ).fetchone()
    conn.close()

    if not row:
        return {
            "popup_required": True,
            "popup_message": "🔔 Initial Attendance Pending! Please mark your attendance."
        }

    last_time = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
    elapsed_minutes = int((datetime.now() - last_time).total_seconds() // 60)

    if elapsed_minutes >= 60:
        return {
            "popup_required": True,
            "elapsed_minutes": elapsed_minutes,
            "popup_message": f"⏰ 1 Hour Completed ({elapsed_minutes} mins)! Please re-verify your presence."
        }

    return {
        "popup_required": False,
        "next_popup_in_minutes": 60 - elapsed_minutes,
        "message": f"✅ Already marked! Next hourly check-in in {60 - elapsed_minutes} minutes."
    }


# ==========================================================
# 3. MARK ATTENDANCE
# ==========================================================
@app.post("/staff/mark-attendance")
async def mark_attendance(
    emp_id: str = Form(...),
    lat: float = Form(...),
    lng: float = Form(...),
    wifi_ssid: str = Form(...),
    live_photo: UploadFile = File(...)
):
    emp_id = emp_id.upper().strip()
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")

    if is_staff_on_approved_leave(emp_id, today_str):
        return {
            "status": "on_leave",
            "reason": "Your leave is APPROVED for today. Attendance is disabled."
        }

    reg_path = os.path.join(DB_FOLDER, f"{emp_id}.jpg")
    if not os.path.exists(reg_path):
        return {"status": "rejected", "reason": f"Staff ID '{emp_id}' not registered."}

    conn = get_db()
    cursor = conn.cursor()

    last_att = cursor.execute(
        "SELECT timestamp FROM attendance WHERE emp_id = ? AND status = 'PRESENT' ORDER BY id DESC LIMIT 1",
        (emp_id,)
    ).fetchone()

    if last_att:
        last_time = datetime.strptime(last_att[0], "%Y-%m-%d %H:%M:%S")
        elapsed_mins = int((now - last_time).total_seconds() // 60)
        if elapsed_mins < 60:
            conn.close()
            remaining_mins = 60 - elapsed_mins
            return {
                "status": "already_marked",
                "reason": f"⏳ Attendance already marked! You can mark again after {remaining_mins} minutes (1-hour cooldown active)."
            }

    row = cursor.execute("SELECT failed_attempts, locked_until FROM staff WHERE emp_id = ?", (emp_id,)).fetchone()
    failed_attempts = row[0] if row else 0
    locked_until_str = row[1] if row else None

    if locked_until_str:
        locked_until = datetime.strptime(locked_until_str, "%Y-%m-%d %H:%M:%S")
        if now < locked_until:
            remaining_hours = round((locked_until - now).total_seconds() / 3600, 1)
            conn.close()
            return {
                "status": "blocked_24h",
                "reason": f"🔒 ACCOUNT BLOCKED FOR 24 HOURS due to 3 failed face attempts! ({remaining_hours} hrs remaining)."
            }
        else:
            failed_attempts = 0
            cursor.execute("UPDATE staff SET failed_attempts = 0, locked_until = NULL WHERE emp_id = ?", (emp_id,))
            conn.commit()

    distance = calculate_distance_meters(lat, lng, CAMPUS_LAT, CAMPUS_LNG)
    if not (distance <= ALLOWED_RADIUS or wifi_ssid.strip().lower() == APPROVED_WIFI.lower()):
        conn.close()
        return {"status": "rejected", "reason": f"Outside Campus Radius ({int(distance)}m away)."}

    live_path = f"temp/{emp_id}_live.jpg"
    with open(live_path, "wb") as buffer:
        buffer.write(await live_photo.read())

    result = verify_staff_face(reg_path, live_path)

    if not result["verified"]:
        failed_attempts += 1
        evidence_path = os.path.join(PROXY_EVIDENCE, f"{emp_id}_strike_{failed_attempts}.jpg")
        shutil.copy(live_path, evidence_path)

        if failed_attempts >= 3:
            lock_time = (now + timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute(
                "UPDATE staff SET failed_attempts = ?, locked_until = ? WHERE emp_id = ?",
                (failed_attempts, lock_time, emp_id)
            )
            alert_msg = f"CRITICAL: {emp_id} failed face verification 3 times! Blocked until {lock_time}."
            cursor.execute(
                "INSERT INTO admin_alerts (emp_id, alert_message, evidence_photo) VALUES (?, ?, ?)",
                (emp_id, alert_msg, evidence_path)
            )
            conn.commit()
            conn.close()
            return {
                "status": "blocked_24h",
                "reason": "🚨 WRONG FACE DETECTED! 3rd Strike! Account BLOCKED for 24 Hours & Proxy Alert sent to Admin."
            }

        cursor.execute("UPDATE staff SET failed_attempts = ? WHERE emp_id = ?", (failed_attempts, emp_id))
        conn.commit()
        conn.close()
        return {
            "status": "rejected",
            "reason": f"❌ WRONG FACE DETECTED! (Strike {failed_attempts}/3). Face did not match registered staff profile. {3 - failed_attempts} attempts left before 24h block."
        }

    cursor.execute("UPDATE staff SET failed_attempts = 0, locked_until = NULL WHERE emp_id = ?", (emp_id,))
    cursor.execute(
        "INSERT INTO attendance (emp_id, date_str, timestamp, distance_meters, confidence, status) VALUES (?, ?, ?, ?, ?, 'PRESENT')",
        (emp_id, today_str, now.strftime("%Y-%m-%d %H:%M:%S"), int(distance), result["confidence"])
    )
    conn.commit()
    conn.close()

    return {
        "status": "success",
        "message": "Attendance Marked Successfully! Next pop-up in 1 hour.",
        "distance_from_campus_meters": int(distance),
        "confidence": result["confidence"]
    }

@app.get("/admin/proxy-alerts")
def get_admin_alerts():
    conn = get_db()
    rows = conn.execute("SELECT id, emp_id, alert_message, evidence_photo, timestamp FROM admin_alerts ORDER BY id DESC").fetchall()
    conn.close()
    return {"alerts": [{"id": r[0], "emp_id": r[1], "message": r[2], "photo": r[3], "time": r[4]} for r in rows]}


# ==========================================================
# 4. LEAVE APPROVAL
# ==========================================================
@app.post("/staff/apply-leave")
def apply_leave(
    emp_id: str = Form(...),
    start_date: str = Form(...),
    end_date: str = Form(...),
    reason: str = Form(...)
):
    conn = get_db()
    conn.execute(
        "INSERT INTO leave_requests (emp_id, start_date, end_date, reason, status) VALUES (?, ?, ?, ?, 'PENDING')",
        (emp_id.upper().strip(), start_date, end_date, reason)
    )
    conn.commit()
    conn.close()
    return {"status": "success", "message": "Leave request submitted for Admin approval."}

@app.post("/admin/approve-leave")
def approve_leave(leave_id: int = Form(...), approve: bool = Form(True)):
    status = "APPROVED" if approve else "REJECTED"
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE leave_requests SET status = ? WHERE id = ?", (status, leave_id))
    
    if approve:
        leave_row = cursor.execute("SELECT emp_id, start_date, end_date FROM leave_requests WHERE id = ?", (leave_id,)).fetchone()
        if leave_row:
            cursor.execute(
                "DELETE FROM attendance WHERE emp_id = ? AND date_str BETWEEN ? AND ?",
                (leave_row[0], leave_row[1], leave_row[2])
            )
    conn.commit()
    conn.close()
    return {"status": "success", "message": f"Leave #{leave_id} is now {status}."}

@app.get("/staff/attendance-records")
def get_attendance_records(emp_id: str):
    emp_id = emp_id.upper().strip()
    conn = get_db()
    rows = conn.execute("""
        SELECT id, date_str, timestamp, distance_meters, confidence, status 
        FROM attendance a
        WHERE emp_id = ? 
        AND NOT EXISTS (
            SELECT 1 FROM leave_requests l 
            WHERE l.emp_id = a.emp_id 
            AND l.status = 'APPROVED' 
            AND a.date_str BETWEEN l.start_date AND l.end_date
        )
        ORDER BY id DESC
    """, (emp_id,)).fetchall()
    conn.close()
    return {
        "emp_id": emp_id,
        "visible_attendance_logs": [
            {"id": r[0], "date": r[1], "timestamp": r[2], "distance_m": r[3], "confidence": r[4], "status": r[5]}
            for r in rows
        ]
    }


# ==========================================================
# 5. ACCIDENT FACE UPDATE & STAFF LIST
# ==========================================================
@app.post("/staff/request-accident-face-update")
async def request_accident_face_update(
    emp_id: str = Form(...),
    accident_or_medical_reason: str = Form(...),
    new_photo: UploadFile = File(...)
):
    emp_id = emp_id.upper().strip()
    pending_path = os.path.join(PENDING_FACES, f"{emp_id}_pending.jpg")
    with open(pending_path, "wb") as buffer:
        buffer.write(await new_photo.read())

    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO face_update_requests (emp_id, reason, new_photo_path, status) VALUES (?, ?, ?, 'PENDING')",
        (emp_id, accident_or_medical_reason, pending_path)
    )
    conn.commit()
    conn.close()
    return {"status": "pending_admin_approval", "message": "Emergency face update submitted!"}

@app.post("/admin/approve-accident-face-update")
def approve_accident_face_update(emp_id: str = Form(...), approve: bool = Form(True)):
    emp_id = emp_id.upper().strip()
    pending_path = os.path.join(PENDING_FACES, f"{emp_id}_pending.jpg")
    official_path = os.path.join(DB_FOLDER, f"{emp_id}.jpg")

    if not os.path.exists(pending_path):
        return {"status": "error", "message": "No pending face update request found."}

    conn = get_db()
    if approve:
        shutil.copy(pending_path, official_path)
        conn.execute("UPDATE face_update_requests SET status = 'APPROVED' WHERE emp_id = ?", (emp_id,))
        conn.execute("UPDATE staff SET failed_attempts = 0, locked_until = NULL WHERE emp_id = ?", (emp_id,))
        msg = f"Approved! {emp_id}'s new face is active."
    else:
        conn.execute("UPDATE face_update_requests SET status = 'REJECTED' WHERE emp_id = ?", (emp_id,))
        msg = "Face update rejected."

    conn.commit()
    conn.close()
    return {"status": "success", "message": msg}

@app.get("/admin/staff-list")
def get_staff_list():
    conn = get_db()
    rows = conn.execute("SELECT emp_id, name, department FROM staff").fetchall()
    conn.close()
    return {
        "faculty": [
            {"emp_id": r[0], "name": r[1], "department": r[2]} 
            for r in rows
        ]
    }
