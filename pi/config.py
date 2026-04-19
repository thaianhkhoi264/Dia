# =============================================================================
# Dia Gesture Controller — Configuration
#
# Sensitive values (PC_IP, PC_MAC) are read from environment variables so they
# are never committed to git. Set them in the .env file at the repo root:
#
#   DIA_PC_IP=192.168.1.123
#   DIA_PC_MAC=AA:BB:CC:DD:EE:FF
#
# See .env.example for the template.
# =============================================================================

import os
from pathlib import Path

# Load .env when running manually.
# When running as a systemd service, EnvironmentFile handles this instead.
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

# --- Network -----------------------------------------------------------------
PC_IP           = os.environ.get("DIA_PC_IP",  "")
PC_MAC          = os.environ.get("DIA_PC_MAC", "")
PC_COMMAND_PORT = 7000

if not PC_IP or not PC_MAC:
    raise RuntimeError(
        "DIA_PC_IP and DIA_PC_MAC must be set. "
        "Copy .env.example to .env and fill in the values."
    )

# --- Blaze hand detection ----------------------------------------------------
# Path to the cloned blaze_app_python repo on the Pi.
# Clone it with: git clone https://github.com/AlbertaBeef/blaze_app_python.git ~/blaze_app_python
BLAZE_APP_PATH = os.path.expanduser("~/blaze_app_python")

# HEF model paths (relative to BLAZE_APP_PATH)
PALM_HEF_PATH     = os.path.join(BLAZE_APP_PATH, "blaze_hailo/models/palm_detection_lite.hef")
LANDMARK_HEF_PATH = os.path.join(BLAZE_APP_PATH, "blaze_hailo/models/hand_landmark_lite.hef")

# Palm detection confidence threshold (0–1). Lower = more detections but more false positives.
PALM_CONFIDENCE_THRESHOLD = 0.5

# Webcam device index for cv2.VideoCapture
CAMERA_INDEX = 0

# --- Gesture hold durations (seconds) ----------------------------------------
# Each gesture must be held continuously for this long before firing.
WAKE_HOLD_S        = 2.0
PLAY_PAUSE_HOLD_S  = 1.5
NEXT_TRACK_HOLD_S  = 1.5
VOLUME_UP_HOLD_S   = 1.5
VOLUME_DOWN_HOLD_S = 1.5

# --- Cooldown after a gesture fires (prevents immediate re-triggering) --------
COOLDOWN_S = 3.0

# --- Gesture thread polling interval -----------------------------------------
GESTURE_POLL_INTERVAL_S = 0.03   # ~33 Hz
