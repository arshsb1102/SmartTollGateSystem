import cv2
import pytesseract
import time
import re
import os
import subprocess
import numpy as np

# ----------------------------
# PREDEFINED DATABASES
# ----------------------------

VALID_LICENSE = {
    "MH44AB4444",
    "DL55CD5555",
    "KA66EF6666",
    "TN77GH7777",
    "WB88JK8888",
    "UP44CR4444",
    "BR55MD5555",
    "MP66KG6666",
    "RJ77PN7777",
}

CRIMINAL_RECORDS = {
    "KA66EF6666",
    "UP44CR4444",
    "RJ77PN7777",
}

TRAFFIC_VIOLATIONS = {
    "TN77GH7777",
    "BR55MD5555",
    "RJ77PN7777",
}

INSURANCE_EXPIRED = {
    "WB88JK8888",
    "BR55MD5555",
    "MP66KG6666",
}

PUC_INVALID = {
    "MP66KG6666",
}

ACCIDENT_RECORDS = {
    "UP44CR4444",
    "RJ77PN7777",
}

# ----------------------------
# DASHBOARD STATE
# ----------------------------

stats = {"total": 0, "approved": 0, "rejected": 0}

dashboard = {
    "plate": "-",
    "status": "-",
    "reason": "-",
    "gate": "CLOSED"
}

# ----------------------------
# SOUND (macOS)
# ----------------------------

def play_sound_async(path):
    if os.path.exists(path):
        subprocess.Popen(["afplay", path],
                         stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)

# ----------------------------
# DECISION ENGINE
# ----------------------------

def check_vehicle(plate):
    offenses = []

    if plate not in VALID_LICENSE:
        offenses.append("Invalid License")
    if plate in CRIMINAL_RECORDS:
        offenses.append("Criminal Record")
    if plate in TRAFFIC_VIOLATIONS:
        offenses.append("Traffic Violations")
    if plate in INSURANCE_EXPIRED:
        offenses.append("Insurance Expired")
    if plate in PUC_INVALID:
        offenses.append("PUC Invalid")
    if plate in ACCIDENT_RECORDS:
        offenses.append("Accident Record")

    if offenses:
        return f"REJECTED | {' , '.join(offenses)}"

    return "APPROVED | Clean Record"


def is_valid_plate(text):
    return re.match(r"^[A-Z]{2}[0-9]{2}[A-Z]{2}[0-9]{4}$", text) is not None

# ----------------------------
# DASHBOARD (RIGHT PANEL)
# ----------------------------

DASHBOARD_WIDTH = 300

def draw_dashboard(canvas, cam_width):
    x = cam_width + 10

    cv2.rectangle(canvas, (cam_width, 0),
                  (cam_width + DASHBOARD_WIDTH, canvas.shape[0]),
                  (30, 30, 30), -1)

    lines = [
        ("SMART TOLL GATE", (0, 255, 255)),
        (f"Plate: {dashboard['plate']}", (255, 255, 255)),
        (f"Status: {dashboard['status']}",
         (0, 255, 0) if "APPROVED" in dashboard["status"] else (0, 0, 255)),
        (f"Gate: {dashboard['gate']}",
         (0, 255, 0) if dashboard["gate"] == "OPEN" else (0, 0, 255)),
        (f"Total Cars: {stats['total']}", (255, 255, 255)),
        (f"Approved: {stats['approved']}", (0, 255, 0)),
        (f"Rejected: {stats['rejected']}", (0, 0, 255)),
    ]

    y = 40
    for text, color in lines:
        cv2.putText(canvas, text, (x, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        y += 35

# ----------------------------
# CAMERA SETUP
# ----------------------------

cap = cv2.VideoCapture(0)
if not cap.isOpened():
    cap = cv2.VideoCapture(1)

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

    # Create extended canvas
    canvas = np.zeros((h, w + DASHBOARD_WIDTH, 3), dtype=np.uint8)
    canvas[:, :w] = frame

    # Scan zone
    x1, y1 = int(w * 0.25), int(h * 0.35)
    x2, y2 = int(w * 0.75), int(h * 0.65)
    roi = frame[y1:y2, x1:x2]

    # OCR preprocessing
    resized = cv2.resize(roi, None, fx=2.5, fy=2.5,
                         interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)

    config = "--oem 3 --psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    text = pytesseract.image_to_string(thresh, config=config)
    plate = text.strip().replace(" ", "").replace("\n", "")

    current_time = time.time()

    if is_valid_plate(plate):
        if plate != last_plate or (current_time - last_time) > COOLDOWN_SECONDS:
            status = check_vehicle(plate)

            stats["total"] += 1
            dashboard["plate"] = plate
            dashboard["status"] = status
            dashboard["gate"] = "OPEN" if "APPROVED" in status else "CLOSED"

            if "APPROVED" in status:
                stats["approved"] += 1
                play_sound_async("sounds/approved.mp3")
            else:
                stats["rejected"] += 1
                play_sound_async("sounds/rejected.mp3")

            print(plate, "→", status)
            last_plate = plate
            last_time = current_time

    # Draw scan box
    cv2.rectangle(canvas, (x1, y1), (x2, y2), (0, 255, 0), 2)
    cv2.putText(canvas, "Place Number Plate Here",
                (x1, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                (0, 255, 0), 2)

    draw_dashboard(canvas, w)

    cv2.imshow("Smart Toll Gate Camera", canvas)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
