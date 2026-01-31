import cv2
import pytesseract
import time
import re
import os
import subprocess
import numpy as np
import platform

# ----------------------------
# PREDEFINED DATABASES
# ----------------------------

VALID_LICENSE = {
    "MH44AB4444", "DL55CD5555", "KA66EF6666",
    "TN77GH7777", "WB88JK8888", "UP44CR4444",
    "BR55MD5555", "MP66KG6666", "RJ77PN7777",
}

CRIMINAL_RECORDS = {"KA66EF6666", "UP44CR4444", "RJ77PN7777"}
TRAFFIC_VIOLATIONS = {"TN77GH7777", "BR55MD5555", "RJ77PN7777"}
INSURANCE_EXPIRED = {"WB88JK8888", "BR55MD5555", "MP66KG6666"}
PUC_INVALID = {"MP66KG6666"}
ACCIDENT_RECORDS = {"UP44CR4444", "RJ77PN7777"}

# ----------------------------
# DASHBOARD STATE
# ----------------------------

stats = {"total": 0, "approved": 0, "rejected": 0}

dashboard = {
    "plate": "-",
    "status": "-",
    "gate": "CLOSED"
}

# ----------------------------
# OS-DEPENDENT SOUND
# ----------------------------

OS_NAME = platform.system()

def play_sound_async(path):
    if not os.path.exists(path):
        return

    try:
        if OS_NAME == "Darwin":  # macOS (Intel + Apple Silicon)
            subprocess.Popen(["afplay", path],
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)

        elif OS_NAME == "Windows":
            import winsound
            winsound.PlaySound(path, winsound.SND_ASYNC)

    except Exception:
        pass  # sound must never crash demo

# ----------------------------
# CAMERA AUTO-DETECTION
# ----------------------------

def detect_cameras(max_index=5):
    cams = []
    for i in range(max_index):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            cams.append(i)
            cap.release()
    return cams

AVAILABLE_CAMERAS = detect_cameras()
if not AVAILABLE_CAMERAS:
    print("❌ No cameras detected")
    exit()

current_camera_index = AVAILABLE_CAMERAS[0]
cap = cv2.VideoCapture(current_camera_index)

def switch_camera(new_index):
    global cap, current_camera_index
    if new_index not in AVAILABLE_CAMERAS:
        return
    cap.release()
    cap = cv2.VideoCapture(new_index)
    if cap.isOpened():
        current_camera_index = new_index

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
    return re.match(r"^[A-Z]{2}[0-9]{2}[A-Z]{2}[0-9]{4}$", text) is not None

# ----------------------------
# TEXT WRAPPING (KEY FIX)
# ----------------------------

def draw_wrapped_text(img, text, x, y, max_width, line_height, color):
    words = text.split(" ")
    line = ""
    for word in words:
        test = line + word + " "
        (w, _), _ = cv2.getTextSize(test, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
        if w > max_width:
            cv2.putText(img, line, (x, y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)
            y += line_height
            line = word + " "
        else:
            line = test
    cv2.putText(img, line, (x, y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)
    return y + line_height

# ----------------------------
# DASHBOARD (RIGHT PANEL)
# ----------------------------

DASHBOARD_WIDTH = 360

def draw_dashboard(canvas, cam_width):
    cv2.rectangle(canvas, (cam_width, 0),
                  (cam_width + DASHBOARD_WIDTH, canvas.shape[0]),
                  (30, 30, 30), -1)

    x = cam_width + 15
    y = 40

    cv2.putText(canvas, "SMART TOLL GATE", (x, y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
    y += 35

    cv2.putText(canvas, f"Plate: {dashboard['plate']}", (x, y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    y += 30

    status_color = (0, 255, 0) if "APPROVED" in dashboard["status"] else (0, 0, 255)
    y = draw_wrapped_text(
        canvas,
        f"Status: {dashboard['status']}",
        x, y, DASHBOARD_WIDTH - 30, 28, status_color
    )

    cv2.putText(canvas, f"Gate: {dashboard['gate']}", (x, y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                (0, 255, 0) if dashboard["gate"] == "OPEN" else (0, 0, 255), 2)
    y += 30

    cv2.putText(canvas, f"Total: {stats['total']}", (x, y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    y += 25
    cv2.putText(canvas, f"Approved: {stats['approved']}", (x, y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
    y += 25
    cv2.putText(canvas, f"Rejected: {stats['rejected']}", (x, y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
    y += 30

    cv2.putText(canvas, f"Camera: {current_camera_index}", (x, y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)
    y += 22
    cv2.putText(canvas, "Switch: 0 / 1 / 2", (x, y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (150, 150, 150), 1)

# ----------------------------
# MAIN LOOP
# ----------------------------

last_plate = ""
last_time = 0
COOLDOWN_SECONDS = 3

while True:
    ret, frame = cap.read()
    if not ret:
        break

    h, w, _ = frame.shape
    canvas = np.zeros((h, w + DASHBOARD_WIDTH, 3), dtype=np.uint8)
    canvas[:, :w] = frame

    x1, y1 = int(w * 0.25), int(h * 0.35)
    x2, y2 = int(w * 0.75), int(h * 0.65)
    roi = frame[y1:y2, x1:x2]

    resized = cv2.resize(roi, None, fx=2.5, fy=2.5, interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)

    plate = pytesseract.image_to_string(
        thresh,
        config="--oem 3 --psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    ).strip().replace(" ", "").replace("\n", "")

    now = time.time()
    if is_valid_plate(plate):
        if plate != last_plate or now - last_time > COOLDOWN_SECONDS:
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

            last_plate, last_time = plate, now

    cv2.rectangle(canvas, (x1, y1), (x2, y2), (0, 255, 0), 2)
    cv2.putText(canvas, "Place Number Plate Here",
                (x1, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

    draw_dashboard(canvas, w)
    cv2.imshow("Smart Toll Gate Camera", canvas)

    key = cv2.waitKey(1) & 0xFF
    if key == ord('0'): switch_camera(0)
    elif key == ord('1'): switch_camera(1)
    elif key == ord('2'): switch_camera(2)
    elif key == ord('q'): break

cap.release()
cv2.destroyAllWindows()
