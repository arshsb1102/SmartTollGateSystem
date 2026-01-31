import cv2
import pytesseract
import time
import re
import os
import subprocess

# ----------------------------
# PREDEFINED DATABASES
# ----------------------------

VALID_LICENSE = {
    "MH01AB1234",
    "DL05CD5678",
    "KA09EF1111"
}

CRIMINAL_RECORDS = {"UP32ZZ9999"}
TRAFFIC_VIOLATIONS = {"RJ14AA0001"}
INSURANCE_EXPIRED = {"PB10XY8888"}
PUC_INVALID = {"HR26TT4321"}
ACCIDENT_RECORDS = {"GJ01MM0007"}

# ----------------------------
# DASHBOARD STATE
# ----------------------------

stats = {
    "total": 0,
    "approved": 0,
    "rejected": 0
}

dashboard = {
    "plate": "-",
    "status": "-",
    "reason": "-",
    "gate": "CLOSED"
}

# ----------------------------
# SOUND (macOS afplay)
# ----------------------------

def play_sound_async(path):
    if os.path.exists(path):
        subprocess.Popen(
            ["afplay", path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

# ----------------------------
# DECISION ENGINE
# ----------------------------

def check_vehicle(plate):
    if plate not in VALID_LICENSE:
        return "REJECTED", "Invalid License Plate"
    if plate in CRIMINAL_RECORDS:
        return "REJECTED", "Criminal Record Found"
    if plate in TRAFFIC_VIOLATIONS:
        return "REJECTED", "Traffic Violations Pending"
    if plate in INSURANCE_EXPIRED:
        return "REJECTED", "Insurance Expired"
    if plate in PUC_INVALID:
        return "REJECTED", "PUC Invalid"
    if plate in ACCIDENT_RECORDS:
        return "REJECTED", "Accident Record Found"
    return "APPROVED", "Clean Record"

def is_valid_plate(text):
    return re.match(r"^[A-Z]{2}[0-9]{2}[A-Z]{2}[0-9]{4}$", text) is not None

# ----------------------------
# OPENCV DASHBOARD
# ----------------------------

def draw_dashboard(frame):
    cv2.rectangle(frame, (5, 5), (430, 260), (0, 0, 0), -1)

    lines = [
        ("SMART TOLL GATE DASHBOARD", (0, 255, 255)),
        (f"Plate: {dashboard['plate']}", (255, 255, 255)),
        (f"Status: {dashboard['status']}",
         (0, 255, 0) if dashboard["status"] == "APPROVED" else (0, 0, 255)),
        (f"Reason: {dashboard['reason']}", (200, 200, 200)),
        (f"Gate: {dashboard['gate']}",
         (0, 255, 0) if dashboard["gate"] == "OPEN" else (0, 0, 255)),
        (f"Total Cars: {stats['total']}", (255, 255, 255)),
        (f"Approved: {stats['approved']}", (0, 255, 0)),
        (f"Rejected: {stats['rejected']}", (0, 0, 255)),
    ]

    y = 30
    for text, color in lines:
        cv2.putText(
            frame, text, (15, y),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2
        )
        y += 28

# ----------------------------
# CAMERA SETUP
# ----------------------------

cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("❌ Cannot open camera")
    exit()

print("System started. Scanning for vehicles...")

last_plate = ""
last_time = 0
COOLDOWN_SECONDS = 3

# ----------------------------
# MAIN LOOP
# ----------------------------

while True:
    ret, frame = cap.read()
    if not ret:
        break

    h, w, _ = frame.shape

    # Scan zone
    x1, y1 = int(w * 0.25), int(h * 0.35)
    x2, y2 = int(w * 0.75), int(h * 0.65)
    roi = frame[y1:y2, x1:x2]

    # OCR preprocessing (keep simple – works best)
    resized = cv2.resize(roi, None, fx=2.5, fy=2.5, interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)

    config = (
        "--oem 3 --psm 7 "
        "-c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    )

    text = pytesseract.image_to_string(thresh, config=config)
    plate = text.strip().replace(" ", "").replace("\n", "")

    current_time = time.time()

    if len(plate) >= 6 and is_valid_plate(plate):
        if plate != last_plate or (current_time - last_time) > COOLDOWN_SECONDS:
            status, reason = check_vehicle(plate)

            stats["total"] += 1
            dashboard["plate"] = plate
            dashboard["status"] = status
            dashboard["reason"] = reason

            if status == "APPROVED":
                stats["approved"] += 1
                dashboard["gate"] = "OPEN"
                play_sound_async("sounds/approved.mp3")
            else:
                stats["rejected"] += 1
                dashboard["gate"] = "CLOSED"
                play_sound_async("sounds/rejected.mp3")

            print("\nDetected Plate:", plate)
            print("Decision:", status)
            print("Reason:", reason)

            last_plate = plate
            last_time = current_time

    # UI overlays
    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
    cv2.putText(
        frame,
        "Place Number Plate Here",
        (x1, y1 - 10),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (0, 255, 0),
        2
    )

    draw_dashboard(frame)

    cv2.imshow("Smart Toll Gate Camera", frame)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
