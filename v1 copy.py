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
# ----------------------------==
VALID_LICENSE = {
    # Clean records
    "MH44AB4444", "DL55CD5555", "GJ22LM2222",
    "HR33MN3333", "KA11UV1111",

    # Criminal record
    "KA66EF6666", "KA77BC7777", "UP88CD8888", "RJ22EF2222",

    # Traffic violations
    "TN77GH7777", "HR66GH6666", "PB77JK7777",

    # Insurance / PUC
    "WB88JK8888", "MP66KG6666",

    # Multiple offenses
    "UP44CR4444", "BR55MD5555", "RJ77PN7777"
}

# Criminal records
CRIMINAL_RECORDS = {
    "KA66EF6666",
    "KA77BC7777",
    "UP88CD8888",
    "RJ22EF2222",
    "UP44CR4444",
    "RJ77PN7777"
}

# Traffic violations
TRAFFIC_VIOLATIONS = {
    "TN77GH7777",
    "HR66GH6666",
    "PB77JK7777",
    "BR55MD5555",
    "RJ77PN7777"
}

# Insurance expired
INSURANCE_EXPIRED = {
    "WB88JK8888",
    "BR55MD5555",
    "MP66KG6666"
}

# PUC invalid
PUC_INVALID = {
    "MP66KG6666",
    "MP22PU2222",
    "UP33PU3333",
    "BR44PU4444",
    "RJ55PU5555"
}

# Accident records
ACCIDENT_RECORDS = {
    "UP44CR4444",
    "RJ77PN7777"
}

# ----------------------------
# INVALID LICENSE (not listed in VALID_LICENSE)
# ----------------------------
# MH99AB9999
# DL88AA8888
# KA55BB5555
# RJ66CC6666
# PB77DD7777

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
last_manual_plate = None
pending_plate = None
processing_in_progress = False
current_decision = None
frozen_frame = None

# ----------------------------
# RESET TIMERS (ONLY CHANGE)
# ----------------------------
RESET_DELAY_APPROVED = 5
RESET_DELAY_REJECTED = 30
reset_at = None

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

def put_wrapped_text(img, text, x, y, max_width, color, scale=0.7, thickness=2):
    words = text.split(" ")
    line = ""
    line_height = int(30 * scale)

    for word in words:
        test_line = line + word + " "
        (w, _), _ = cv2.getTextSize(
            test_line, cv2.FONT_HERSHEY_SIMPLEX, scale, thickness
        )

        if w > max_width:
            cv2.putText(
                img, line, (x, y),
                cv2.FONT_HERSHEY_SIMPLEX, scale, color, thickness
            )
            y += line_height
            line = word + " "
        else:
            line = test_line

    if line:
        cv2.putText(
            img, line, (x, y),
            cv2.FONT_HERSHEY_SIMPLEX, scale, color, thickness
        )
        y += line_height

    return y

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

    status_color = (0,255,0) if "APPROVED" in dashboard["status"] else (0,0,255)
    y = put_wrapped_text(
        canvas,
        f"Status: {dashboard['status']}",
        x,
        y,
        DASHBOARD_WIDTH - 40,
        status_color
    )
    put(f"")
    put(f"Payment: {dashboard['payment']}")
    put(f"Cash Collected: {dashboard['cash']}")
    put(f"Total Cash: INR {total_cash}")
    y += 10
    put(f"Approved: {stats['approved']}", (0,255,0))
    put(f"Rejected: {stats['rejected']}", (0,0,255))
    put(f"Manual Approved: {stats['manual_approved']}", (255,255,0))
    y += 10
    put("ENTER=Process | M=Manual | R=Re-Scan", (180,180,180))
    put("1/2/3=Camera | Q=Quit", (180,180,180))

# ----------------------------
# CAMERA SWITCHING
# ----------------------------
def switch_camera(new_index):
    global cap, processing_in_progress, pending_plate, frozen_frame

    cap.release()
    time.sleep(0.3)

    new_cap = cv2.VideoCapture(new_index)
    if not new_cap.isOpened():
        cap = cv2.VideoCapture(0)
        return

    cap = new_cap
    processing_in_progress = False
    pending_plate = None
    frozen_frame = None

# ----------------------------
# CAMERA SETUP
# ----------------------------
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    cap = cv2.VideoCapture(1)
if not cap.isOpened():
    print("No camera available")
    sys.exit(1)

# ----------------------------
# MAIN LOOP
# ----------------------------
while True:

    # AUTO RESET AFTER 5 SECONDS
    if reset_at and time.time() >= reset_at:
        dashboard.update({
            "plate": "-",
            "status": "Waiting for vehicle",
            "gate": "CLOSED",
            "payment": "-",
            "cash": "NO"
        })
        current_decision = None
        last_processed_plate = None
        last_manual_plate = None
        reset_at = None

    if not processing_in_progress:
        ret, frame = cap.read()
        if not ret:
            break
    else:
        frame = frozen_frame.copy()

    h, w, _ = frame.shape
    canvas = np.zeros((h, w + DASHBOARD_WIDTH, 3), dtype=np.uint8)
    canvas[:, :w] = frame

    x1, y1 = int(w*0.25), int(h*0.45)
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

    # ---------------- TOP BANNER ----------------
    if dashboard["gate"] == "OPEN":
        # Payment successful banner
        cv2.rectangle(canvas, (0, 0), (w, 70), (0, 0, 0), -1)
        cv2.putText(
            canvas,
            "INR 50 PAID SUCCESSFULLY",
            (int(w * 0.18), 45),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            (0, 255, 0),
            3
        )

    elif processing_in_progress:
        # Payment pending banner
        cv2.rectangle(canvas, (0, 0), (w, 70), (0, 0, 0), -1)
        cv2.putText(
            canvas,
            "PLEASE PAY TOLL CHARGES : INR 50",
            (int(w * 0.15), 45),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            (0, 255, 255),
            3
        )

        cv2.putText(canvas,
                    'Press "ENTER" to process',
                    (int(w*0.28), int(h*0.55)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,255,255), 2)


    cv2.rectangle(canvas, (x1,y1), (x2,y2), (0,255,0), 2)
    cv2.putText(canvas, "Place Number Plate Here",
                (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,0), 2)
    # ----------------------------
    # GATE STATUS (BOTTOM LEFT)
    # ----------------------------
    gate_text = f"GATE : {dashboard['gate']}"
    gate_color = (0, 255, 0) if dashboard["gate"] == "OPEN" else (0, 0, 255)

    # Background box
    cv2.rectangle(
        canvas,
        (10, h - 60),
        (260, h - 10),
        (0, 0, 0),
        -1
    )

    # Text
    cv2.putText(
        canvas,
        gate_text,
        (20, h - 25),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        gate_color,
        3
    )

    draw_dashboard(canvas, w)
    cv2.imshow("Smart Toll Gate", canvas)

    key = cv2.waitKey(1) & 0xFF

    # ENTER
    if key == 13 and pending_plate:
        dashboard["status"] = "ANALYSING VEHICLE RECORDS ..."
        draw_dashboard(canvas, w)
        cv2.imshow("Smart Toll Gate", canvas)
        cv2.waitKey(1)
        time.sleep(2)
        
        stats["total"] += 1
        dashboard["status"] = check_vehicle(pending_plate)
        current_decision = dashboard["status"]

        if "APPROVED" in current_decision:
            dashboard["payment"] = "INR 50 credited"
            dashboard["gate"] = "OPEN"
            dashboard["cash"] = "YES"
            stats["approved"] += 1
            total_cash += 50
            play_sound("approved")
            reset_at = time.time() + RESET_DELAY_APPROVED
        else:
            dashboard["payment"] = "Payment failed"
            dashboard["gate"] = "CLOSED"
            stats["rejected"] += 1
            play_sound("rejected")
            reset_at = time.time() + RESET_DELAY_REJECTED

        last_processed_plate = pending_plate
        pending_plate = None
        processing_in_progress = False

    # MANUAL
    elif key == ord('m') and dashboard["gate"] == "CLOSED" and dashboard["status"].startswith("REJECTED") and last_manual_plate != dashboard["plate"]:
        dashboard["status"] = "MANUAL APPROVED"
        dashboard["payment"] = "INR 50 credited (Manual)"
        dashboard["gate"] = "OPEN"
        dashboard["cash"] = "YES"
        stats["manual_approved"] += 1
        total_cash += 50
        play_sound("approved")

        last_manual_plate = dashboard["plate"]
        reset_at = time.time() + RESET_DELAY_APPROVED

    elif key == ord('1'):
        switch_camera(0)
    elif key == ord('2'):
        switch_camera(1)
    elif key == ord('3'):
        switch_camera(2)
    elif key == ord('q'):
        break
    elif key == ord('r'):
        dashboard.update({
            "plate": "-",
            "status": "Waiting for vehicle",
            "gate": "CLOSED",
            "payment": "-",
            "cash": "NO"
        })
        current_decision = None
        last_processed_plate = None
        last_manual_plate = None
        pending_plate = None
        processing_in_progress = False
        reset_at = None

cap.release()
cv2.destroyAllWindows()
