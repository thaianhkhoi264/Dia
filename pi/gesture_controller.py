"""
gesture_controller.py — Dia Pi-side entry point (Part 2: blaze hand detection).

Uses MediaPipe hand landmark models (palm_detection_lite + hand_landmark_lite)
accelerated on the Hailo-8L NPU via blaze_app_python. Camera capture via OpenCV.

Pipeline per frame:
  1. resize_pad(frame) → feed into palm_detection_lite.hef (192×192)
  2. denormalize_detections + detection2roi → locate hand crop
  3. extract_roi → warped 224×224 crop → hand_landmark_lite.hef
  4. Returns (flags, landmarks[21×3], handedness)

Usage:
    cd ~/hailo-rpi5-examples && source setup_env.sh
    ~/hailo-rpi5-examples/venv_hailo_rpi_examples/bin/python \\
        ~/Dia/pi/gesture_controller.py --debug-keypoints

Prerequisites on Pi (one-time):
    git clone https://github.com/AlbertaBeef/blaze_app_python.git ~/blaze_app_python
    cd ~/blaze_app_python/blaze_hailo/models
    source ./get_hailo8l_models.sh && unzip -o blaze_hailo8l_models.zip && cp hailo8l/*.hef .
"""

import argparse
import logging
import os
import sys
import time
import threading

import cv2
import numpy as np

import config

# Add blaze_app_python and blaze_common to import path
sys.path.insert(0, config.BLAZE_APP_PATH)
sys.path.insert(0, os.path.join(config.BLAZE_APP_PATH, "blaze_common"))

try:
    from blaze_hailo.hailo_inference import HailoInference
    from blaze_hailo.blazedetector import BlazeDetector
    from blaze_hailo.blazelandmark import BlazeLandmark
except ImportError as e:
    print(f"ERROR: Could not import blaze_hailo: {e}")
    print(f"  Expected repo at: {config.BLAZE_APP_PATH}")
    print("  Run: git clone https://github.com/AlbertaBeef/blaze_app_python.git ~/blaze_app_python")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared state — written by capture loop, read by gesture thread (Part 3)
# ---------------------------------------------------------------------------
shared_state: dict = {"landmarks": None, "handedness": None, "timestamp": 0.0}
state_lock = threading.Lock()

DEBUG_KEYPOINTS = False

# MediaPipe hand landmark names (21 points, indices match model output)
_LM_NAMES = [
    "wrist",                                                   # 0
    "thumb_cmc",  "thumb_mcp",   "thumb_ip",    "thumb_tip",  # 1-4
    "index_mcp",  "index_pip",   "index_dip",   "index_tip",  # 5-8
    "middle_mcp", "middle_pip",  "middle_dip",  "middle_tip", # 9-12
    "ring_mcp",   "ring_pip",    "ring_dip",    "ring_tip",   # 13-16
    "pinky_mcp",  "pinky_pip",   "pinky_dip",   "pinky_tip",  # 17-20
]


# Hand skeleton edges (pairs of landmark indices)
_HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),          # thumb
    (0, 5), (5, 6), (6, 7), (7, 8),           # index
    (0, 9), (9, 10), (10, 11), (11, 12),      # middle
    (0, 13), (13, 14), (14, 15), (15, 16),    # ring
    (0, 17), (17, 18), (18, 19), (19, 20),    # pinky
    (5, 9), (9, 13), (13, 17),                # palm knuckle bar
]


def _draw_landmarks(frame_bgr, landmarks_px, flags, handedness):
    """Draw hand skeleton onto frame. landmarks_px must be in frame pixel coords."""
    out = frame_bgr.copy()
    hand_side = "left" if handedness > 0.5 else "right"

    pts = [(int(lm[0]), int(lm[1])) for lm in landmarks_px]

    # Draw skeleton
    for a, b in _HAND_CONNECTIONS:
        cv2.line(out, pts[a], pts[b], (0, 200, 0), 2)

    # Draw landmark dots — fingertips slightly larger
    tips = {4, 8, 12, 16, 20}
    for i, pt in enumerate(pts):
        r = 6 if i in tips else 4
        cv2.circle(out, pt, r, (0, 255, 255), -1)
        cv2.circle(out, pt, r, (0, 0, 0), 1)

    # Label wrist with hand side + confidence
    cv2.putText(out, f"{hand_side}  conf={flags:.2f}",
                (pts[0][0] + 8, pts[0][1] - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    return out


def _print_landmarks(landmarks, flags, handedness):
    """Print all 21 landmarks to stdout for calibration/debug."""
    hand_side = "left" if handedness > 0.5 else "right"
    print(f"  hand: {hand_side}  landmark_confidence: {flags:.2f}")
    for i, lm in enumerate(landmarks):
        name = _LM_NAMES[i] if i < len(_LM_NAMES) else f"lm{i}"
        print(f"  {name:>12}: x={lm[0]:.3f}  y={lm[1]:.3f}  z={lm[2]:.3f}")
    print()


def main():
    global DEBUG_KEYPOINTS

    parser = argparse.ArgumentParser(description="Dia gesture controller")
    parser.add_argument(
        "--debug-keypoints",
        action="store_true",
        help="Print raw hand landmarks each frame (no gestures fired)",
    )
    args = parser.parse_args()
    DEBUG_KEYPOINTS = args.debug_keypoints

    if DEBUG_KEYPOINTS:
        logger.info("Debug mode — printing landmarks, gestures will NOT fire")
        logger.info("Show your hand to the camera and check the coordinates")

    # ---------------------------------------------------------------------------
    # Initialise Hailo inference + blaze models
    # ---------------------------------------------------------------------------
    logger.info("Initialising HailoInference...")
    hailo_infer = HailoInference()

    logger.info("Loading palm detector: %s", config.PALM_HEF_PATH)
    palm_detector = BlazeDetector("blazepalm", hailo_infer)
    palm_detector.load_model(config.PALM_HEF_PATH)

    logger.info("Loading hand landmark model: %s", config.LANDMARK_HEF_PATH)
    hand_landmark = BlazeLandmark("blazehandlandmark", hailo_infer)
    hand_landmark.load_model(config.LANDMARK_HEF_PATH)

    # ---------------------------------------------------------------------------
    # Open webcam
    # ---------------------------------------------------------------------------
    cap = cv2.VideoCapture(config.CAMERA_INDEX)
    if not cap.isOpened():
        logger.error("Could not open camera index %d", config.CAMERA_INDEX)
        sys.exit(1)
    logger.info("Camera opened (index %d) — press Ctrl+C to stop", config.CAMERA_INDEX)

    if DEBUG_KEYPOINTS:
        cv2.namedWindow("Dia - hand landmarks", cv2.WINDOW_NORMAL)

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                logger.warning("Empty frame, skipping")
                if DEBUG_KEYPOINTS and cv2.waitKey(1) & 0xFF == ord("q"):
                    break
                continue

            # blaze_app_python expects RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # --- Stage 1: palm detection ------------------------------------
            img_resized, scale, pad = palm_detector.resize_pad(frame_rgb)
            detections = palm_detector.predict_on_image(img_resized)

            display = frame  # default: plain frame when no hand found

            if len(detections) > 0:
                # Denormalize to frame coordinates
                detections = palm_detector.denormalize_detections(detections, scale, pad)

                best_idx  = int(np.argmax(detections[:, 16]))
                best_conf = detections[best_idx, 16]

                if best_conf >= config.PALM_CONFIDENCE_THRESHOLD:
                    best_detection = detections[best_idx:best_idx+1]

                    # --- Stage 2: hand landmark inference -------------------
                    xc, yc, scale_roi, theta = palm_detector.detection2roi(best_detection)
                    roi_imgs, roi_affines, roi_points = hand_landmark.extract_roi(
                        frame_rgb, xc, yc, theta, scale_roi
                    )
                    flags, landmarks, handedness = hand_landmark.predict(roi_imgs)

                    lm   = landmarks[0].copy()   # normalized [0,1] — kept for gesture logic
                    flag = float(flags[0].flat[0])
                    hand = float(handedness[0].flat[0])

                    with state_lock:
                        shared_state["landmarks"]  = lm
                        shared_state["handedness"] = hand
                        shared_state["timestamp"]  = time.monotonic()

                    if DEBUG_KEYPOINTS:
                        _print_landmarks(lm, flag, hand)
                        lm_px = hand_landmark.denormalize_landmarks(
                            landmarks.copy(), roi_affines
                        )[0]
                        display = _draw_landmarks(frame, lm_px, flag, hand)
                else:
                    with state_lock:
                        shared_state["landmarks"] = None
                        shared_state["timestamp"] = time.monotonic()
            else:
                with state_lock:
                    shared_state["landmarks"] = None
                    shared_state["timestamp"] = time.monotonic()

            if DEBUG_KEYPOINTS:
                cv2.imshow("Dia - hand landmarks", display)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

    except KeyboardInterrupt:
        logger.info("Stopped by user")
    finally:
        cap.release()
        if DEBUG_KEYPOINTS:
            cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
