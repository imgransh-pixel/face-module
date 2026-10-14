import sqlite3

DB_NAME = "skit_attendance.db"

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS staff (
        emp_id TEXT PRIMARY KEY, 
        name TEXT, 
        department TEXT, 
        photo_path TEXT, 
        failed_attempts INTEGER DEFAULT 0, 
        locked_until TEXT
    )''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        emp_id TEXT, 
        date_str TEXT, 
        timestamp TEXT, 
        distance_meters INTEGER, 
        confidence REAL, 
        status TEXT
    )''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS leave_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        emp_id TEXT, 
        start_date TEXT, 
        end_date TEXT, 
        reason TEXT, 
        status TEXT
    )''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS admin_alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        emp_id TEXT, 
        alert_message TEXT, 
        evidence_photo TEXT, 
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS face_update_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        emp_id TEXT, 
        reason TEXT, 
        new_photo_path TEXT, 
        status TEXT
    )''')
    
    conn.commit()
    conn.close()



# import sqlite3

# def init_db():
#     conn = sqlite3.connect("skit_attendance.db")
#     cursor = conn.cursor()
    
#     # 1. Staff Table (Includes 3-Strike 24hr Lockout timestamp)
#     cursor.execute("""
#         CREATE TABLE IF NOT EXISTS staff (
#             emp_id TEXT PRIMARY KEY,
#             name TEXT,
#             department TEXT,
#             photo_path TEXT,
#             failed_attempts INTEGER DEFAULT 0,
#             locked_until DATETIME DEFAULT NULL
#         )
#     """)
    
#     # 2. Attendance Logs Table
#     cursor.execute("""
#         CREATE TABLE IF NOT EXISTS attendance (
#             id INTEGER PRIMARY KEY AUTOINCREMENT,
#             emp_id TEXT,
#             date_str TEXT,
#             timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
#             distance_meters INTEGER,
#             confidence REAL,
#             status TEXT
#         )
#     """)

#     # 3. Leave Requests Table (Start Date to End Date)
#     cursor.execute("""
#         CREATE TABLE IF NOT EXISTS leave_requests (
#             id INTEGER PRIMARY KEY AUTOINCREMENT,
#             emp_id TEXT,
#             start_date TEXT,
#             end_date TEXT,
#             reason TEXT,
#             status TEXT DEFAULT 'PENDING'
#         )
#     """)

#     # 4. Face Update Requests Table (Accident / Medical Emergency Case)
#     cursor.execute("""
#         CREATE TABLE IF NOT EXISTS face_update_requests (
#             emp_id TEXT PRIMARY KEY,
#             reason TEXT,
#             new_photo_path TEXT,
#             status TEXT DEFAULT 'PENDING',
#             requested_at DATETIME DEFAULT CURRENT_TIMESTAMP
#         )
#     """)

#     # 5. Admin Security Alerts Table (Shares 3-Strike Proxy Info with Admin)
#     cursor.execute("""
#         CREATE TABLE IF NOT EXISTS admin_alerts (
#             id INTEGER PRIMARY KEY AUTOINCREMENT,
#             emp_id TEXT,
#             alert_message TEXT,
#             evidence_photo TEXT,
#             timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
#         )
#     """)
    
#     conn.commit()
#     conn.close()

# if __name__ == "__main__":
#     init_db()
#     print("✅ Final SQLite Database & All 5 Feature Tables Created Successfully!")

