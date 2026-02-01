import cv2
import pytesseract
import time
import re
import os
import subprocess
import numpy as np
import platform
import sys

# ----------------------------
# RESOURCE PATH (for EXE)
# ----------------------------
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# ----------------------------
# DATABASES
# ----------------------------
VALID_LICENSE = {
    "MH44AB4444", "DL55CD5555", "KA66EF6666",
    "TN77GH7777", "WB88JK8888", "UP44CR4444",
    "BR55MD5555", "MP66KG6666", "RJ77PN7777"
}

CRIMINAL_RECORDS = {"KA66EF6666", "UP44CR4444", "RJ77PN7777"}
TRAFFIC_VIOLATIONS = {"TN77GH7777", "BR55MD5555", "RJ77PN7777"}
INSURANCE_EXPIRED = {"WB88JK8888", "BR55MD5555", "MP66KG6666"}
PUC_INVALID = {"MP66KG6666"}
ACCIDENT_RECORDS = {"UP44CR4444", "RJ77PN7777"}

# ----------------------------
# STATE
# ----------------------------
stats = {"total": 0, "approved": 0, "rejected": 0, "manual_approved": 0}
total_cash = 0

dashboard = {
    "plate": "-",
    "status": "Waiting for vehicle",
    "gate": "CLOSED",
    "payment": "-",
    "cash": "NO"
}

last_processed_plate = None
pending_plate = None
processing_in_progress = False
current_decision = None
frozen_frame = None

# ----------------------------
# SOUND
# ----------------------------
OS_NAME = platform.system()

def play_sound(sound):
    try:
        if OS_NAME == "Windows":
            import winsound
            winsound.PlaySound(resource_path(f"sounds/{sound}.wav"),
                               winsound.SND_ASYNC)
        elif OS_NAME == "Darwin":
            subprocess.Popen(
                ["afplay", resource_path(f"sounds/{sound}.mp3")],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
    except:
        pass

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
        return f"REJECTED | {', '.join(offenses)}"
    return "APPROVED | Clean Record"

def is_valid_plate(text):
    return re.match(r"^[A-Z]{2}[0-9]{2}[A-Z]{2}[0-9]{4}$", text)

# ----------------------------
# DASHBOARD
# ----------------------------
DASHBOARD_WIDTH = 760

def draw_dashboard(canvas, cam_w):
    cv2.rectangle(canvas, (cam_w, 0),
                  (cam_w + DASHBOARD_WIDTH, canvas.shape[0]),
                  (30, 30, 30), -1)

    x, y = cam_w + 20, 45

    def put(t, c=(255,255,255)):
        nonlocal y
        cv2.putText(canvas, t, (x, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, c, 2)
        y += 32

    put("SMART TOLL GATE", (0,255,255))
    put(f"Plate: {dashboard['plate']}")
    put(f"Status: {dashboard['status']}",
        (0,255,0) if "APPROVED" in dashboard["status"] else (0,0,255))
    put(f"Gate: {dashboard['gate']}",
        (0,255,0) if dashboard["gate"]=="OPEN" else (0,0,255))
    put(f"Payment: {dashboard['payment']}")
    put(f"Cash Collected: {dashboard['cash']}")
    put(f"Total Cash: INR {total_cash}")
    y += 10
    put(f"Approved: {stats['approved']}", (0,255,0))
    put(f"Rejected: {stats['rejected']}", (0,0,255))
    put(f"Manual Approved: {stats['manual_approved']}", (255,255,0))
    y += 10
    put("ENTER = Process | M = Manual | Q = Quit", (180,180,180))

# ----------------------------
# CAMERA SETUP
# ----------------------------
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    cap = cv2.VideoCapture(1)
if not cap.isOpened():
    print("No camera")
    exit()

# ----------------------------
# MAIN LOOP
# ----------------------------
while True:
    if not processing_in_progress:
        ret, frame = cap.read()
        if not ret:
            break
    else:
        frame = frozen_frame.copy()

    h, w, _ = frame.shape
    canvas = np.zeros((h, w + DASHBOARD_WIDTH, 3), dtype=np.uint8)
    canvas[:, :w] = frame

    x1, y1 = int(w*0.25), int(h*0.35)
    x2, y2 = int(w*0.75), int(h*0.65)

    if not processing_in_progress:
        roi = frame[y1:y2, x1:x2]
        gray = cv2.cvtColor(cv2.resize(roi, None, fx=2.5, fy=2.5),
                            cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)

        plate = pytesseract.image_to_string(
            thresh,
            config="--oem 3 --psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        ).strip().replace(" ", "").replace("\n", "")

        if is_valid_plate(plate) and plate != last_processed_plate:
            pending_plate = plate
            frozen_frame = frame.copy()
            processing_in_progress = True

            dashboard["plate"] = plate
            dashboard["status"] = "Awaiting payment confirmation"
            dashboard["payment"] = "INR 50 pending"
            dashboard["gate"] = "CLOSED"
            dashboard["cash"] = "NO"

    # Overlay payment instruction when frozen
    if processing_in_progress:
        cv2.rectangle(canvas, (0, int(h*0.4)), (w, int(h*0.6)), (0,0,0), -1)
        cv2.putText(canvas,
                    "Please Pay Toll Gate Charges : INR 50",
                    (int(w*0.12), int(h*0.48)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0,255,255), 3)
        cv2.putText(canvas,
                    'Press "ENTER" to process',
                    (int(w*0.28), int(h*0.55)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,255,255), 2)

    cv2.rectangle(canvas, (x1,y1), (x2,y2), (0,255,0), 2)
    cv2.putText(canvas, "Place Number Plate Here",
                (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX,
                0.7, (0,255,0), 2)

    draw_dashboard(canvas, w)
    cv2.imshow("Smart Toll Gate", canvas)

    key = cv2.waitKey(1) & 0xFF

    # ENTER → PROCESS
    if key == 13 and pending_plate:
        stats["total"] += 1
        dashboard["status"] = "ANALYSING VEHICLE RECORDS ..."
        draw_dashboard(canvas, w)
        cv2.imshow("Smart Toll Gate", canvas)
        cv2.waitKey(1)

        time.sleep(3)

        decision = check_vehicle(pending_plate)
        current_decision = decision
        dashboard["status"] = decision

        if "APPROVED" in decision:
            dashboard["payment"] = "INR 50 credited successfully"
            dashboard["gate"] = "OPEN"
            dashboard["cash"] = "YES"
            stats["approved"] += 1
            total_cash += 50
            play_sound("approved")
        else:
            dashboard["payment"] = "Payment failed due to vehicle issues"
            dashboard["gate"] = "CLOSED"
            dashboard["cash"] = "NO"
            stats["rejected"] += 1
            play_sound("rejected")

        last_processed_plate = pending_plate
        pending_plate = None
        processing_in_progress = False

    # MANUAL ONLY IF REJECTED
    elif key == ord('m') and current_decision and "REJECTED" in current_decision:
        dashboard["status"] = "MANUAL APPROVED"
        dashboard["payment"] = "INR 50 credited (Manual)"
        dashboard["gate"] = "OPEN"
        dashboard["cash"] = "YES"
        stats["manual_approved"] += 1
        total_cash += 50
        play_sound("approved")

        last_processed_plate = dashboard["plate"]
        processing_in_progress = False

    elif key == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
