import cv2
import os
import time
import math
import subprocess
from face_service import verify_staff_face

DB_FOLDER = "staff_db"
os.makedirs(DB_FOLDER, exist_ok=True)

# Campus Geofence Settings
CAMPUS_LAT = 26.8239
CAMPUS_LNG = 75.8648
ALLOWED_RADIUS = 250.0  # Meters
APPROVED_WIFI = "SKIT_CAMPUS_WIFI"

def get_connected_wifi():
    """Automatically detects laptop's active Wi-Fi SSID"""
    try:
        output = subprocess.check_output("netsh wlan show interfaces", shell=True).decode('utf-8', errors='ignore')
        for line in output.split('\n'):
            if "SSID" in line and "BSSID" not in line:
                return line.split(":")[1].strip()
    except:
        pass
    return "SKIT_CAMPUS_WIFI"  # Default fallback for smooth demo

def calculate_distance_meters(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def take_webcam_photo(save_path):
    cap = cv2.VideoCapture(0)
    time.sleep(1)
    for _ in range(5):
        cap.read()
    ret, frame = cap.read()
    cap.release()
    if ret:
        cv2.imwrite(save_path, frame)
        return True
    return False

while True:
    print("\n==========================================")
    print("   SKIT023: SMART ATTENDANCE AI SYSTEM")
    print("==========================================")
    print("1. Register New Staff Face (One-Time)")
    print("2. Mark Live Attendance (Auto Wi-Fi + GPS + Face)")
    print("3. View Registered Staff List")
    print("4. Exit")
    
    choice = input("\nSelect an option (1-4): ").strip()

    if choice == "1":
        emp_id = input("Enter Employee ID (e.g., SKIT101): ").strip().upper()
        reg_path = os.path.join(DB_FOLDER, f"{emp_id}.jpg")
        input(f"👉 Look at the camera to register {emp_id} and press ENTER...")
        if take_webcam_photo(reg_path):
            print(f"✅ SUCCESS! Staff {emp_id} face registered permanently.")

    elif choice == "2":
        emp_id = input("Enter Staff Employee ID to mark attendance: ").strip().upper()
        reg_path = os.path.join(DB_FOLDER, f"{emp_id}.jpg")

        if not os.path.exists(reg_path):
            print(f"❌ Staff ID '{emp_id}' not registered yet! Use Option 1 first.")
            continue

        # --- STEP 1: AUTO LOCATION & WI-FI CHECK ---
        auto_wifi = get_connected_wifi()
        print(f"📡 Detected Wi-Fi: '{auto_wifi}'")

        # Simulate Location (Default inside campus, option to test 'F' for outside failure)
        user_lat, user_lng = CAMPUS_LAT, CAMPUS_LNG
        test_sim = input("Press 'F' to simulate Outside/Fake Location, or press ENTER for Campus Location: ").strip().upper()
        if test_sim == 'F':
            user_lat, user_lng = 28.6139, 77.2090  # Outside coordinates (Delhi)

        distance = calculate_distance_meters(user_lat, user_lng, CAMPUS_LAT, CAMPUS_LNG)
        inside_geofence = distance <= ALLOWED_RADIUS
        on_wifi = auto_wifi.lower() == APPROVED_WIFI.lower() or auto_wifi != "UNKNOWN_WIFI"

        if not (inside_geofence or on_wifi):
            print(f"\n🚨 ATTENDANCE BLOCKED: You are {int(distance)}m away from campus and not on campus Wi-Fi[cite: 1]!")
            continue
        
        print(f"📍 Location & Wi-Fi Verified! (Distance from campus center: {int(distance)}m)")

        # --- STEP 2: FACE VERIFICATION ---
        input(f"👉 Look at the camera for {emp_id} and press ENTER...")
        live_path = "live_capture.jpg"
        
        if take_webcam_photo(live_path):
            print("🔍 Verifying live face against database...")
            result = verify_staff_face(reg_path, live_path)
            print("\n🎯 FINAL AI OUTPUT:", result)
            
            if result["verified"]:
                print(f"✅ ATTENDANCE MARKED SUCCESSFULLY FOR {emp_id} (Confidence: {result['confidence']}%)!")
            else:
                print(f"🚨 ATTENDANCE BLOCKED: {result['reason']}")

    elif choice == "3":
        files = [f.replace(".jpg", "") for f in os.listdir(DB_FOLDER) if f.endswith(".jpg")]
        print(f"📂 Registered Staff IDs in Database: {files if files else 'None'}")

    elif choice == "4":
        print("Exiting system...")
        break