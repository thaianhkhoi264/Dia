"""
gesture_controller.py — Dia Pi-side entry point (Part 2: pipeline + debug).

Runs the Hailo/GStreamer pose-estimation pipeline and extracts keypoints
from each frame. In --debug-keypoints mode, prints them to stdout so you
can verify detection at distance before gesture logic is added in Part 3.

Usage:
    source ~/hailo-rpi5-examples/setup_env.sh
    ~/Dia/venv/bin/python ~/Dia/pi/gesture_controller.py --debug-keypoints
"""

import argparse
import logging

import gi
gi.require_version("Gst", "1.0")
from gi.repository import Gst

import hailo

# Compatibility shim — supports both old and new hailo-apps-infra layouts
try:
    from hailo_apps_infra.pose_estimation_pipeline import GStreamerPoseEstimationApp
    from hailo_apps_infra.hailo_rpi_common import get_caps_from_pad, app_callback_class
except ImportError:
    from hailo_apps.hailo_app_python.apps.pose_estimation.pose_estimation_pipeline import (
        GStreamerPoseEstimationApp,
    )
    from hailo_apps.hailo_app_python.core.gstreamer.gstreamer_app import app_callback_class
    from hailo_apps.hailo_app_python.core.common.buffer_utils import get_caps_from_pad

import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Set by --debug-keypoints flag
DEBUG_KEYPOINTS = False

# COCO keypoint names (index = position in landmarks list)
_KP_NAMES = [
    "nose",          # 0
    "left_eye",      # 1
    "right_eye",     # 2
    "left_ear",      # 3
    "right_ear",     # 4
    "left_shoulder", # 5  ← person's left = RIGHT side of image
    "right_shoulder",# 6  ← person's right = LEFT side of image
    "left_elbow",    # 7
    "right_elbow",   # 8
    "left_wrist",    # 9
    "right_wrist",   # 10
    "left_hip",      # 11
    "right_hip",     # 12
    "left_knee",     # 13
    "right_knee",    # 14
    "left_ankle",    # 15
    "right_ankle",   # 16
]


class _UserData(app_callback_class):
    def __init__(self):
        super().__init__()


def app_callback(pad, info, user_data):
    """
    GStreamer pad-probe callback — called on every frame.
    Extracts keypoints and prints them in debug mode.
    """
    buffer = info.get_buffer()
    if buffer is None:
        return Gst.PadProbeReturn.OK

    format, width, height = get_caps_from_pad(pad)

    roi        = hailo.get_roi_from_buffer(buffer)
    detections = roi.get_objects_typed(hailo.HAILO_DETECTION)

    if not detections:
        if DEBUG_KEYPOINTS:
            print("  (no person detected)\n")
        return Gst.PadProbeReturn.OK

    # Use the highest-confidence detection (handles multiple people)
    best = max(detections, key=lambda d: d.get_confidence())

    if best.get_confidence() < config.PERSON_CONFIDENCE_THRESHOLD:
        if DEBUG_KEYPOINTS:
            print(f"  (detection below threshold: {best.get_confidence():.2f})\n")
        return Gst.PadProbeReturn.OK

    bbox      = best.get_bbox()
    landmarks = best.get_objects_typed(hailo.HAILO_LANDMARKS)

    if not landmarks:
        return Gst.PadProbeReturn.OK

    raw_points = landmarks[0].get_points()
    keypoints  = []

    for pt in raw_points:
        conf = pt.confidence() if hasattr(pt, "confidence") else 1.0
        if conf >= config.KEYPOINT_CONFIDENCE_THRESHOLD:
            px = pt.x() * bbox.width()  + bbox.xmin()
            py = pt.y() * bbox.height() + bbox.ymin()
            keypoints.append((px, py, conf))
        else:
            keypoints.append(None)

    if DEBUG_KEYPOINTS:
        _print_keypoints(keypoints, best.get_confidence())

    return Gst.PadProbeReturn.OK


def _print_keypoints(keypoints, person_conf):
    print(f"  person confidence: {person_conf:.2f}")
    for i, kp in enumerate(keypoints):
        name = _KP_NAMES[i] if i < len(_KP_NAMES) else f"kp{i}"
        if kp is None:
            print(f"  {name:>16}: (low confidence)")
        else:
            print(f"  {name:>16}: x={kp[0]:.3f}  y={kp[1]:.3f}  conf={kp[2]:.2f}")
    print()


def main():
    global DEBUG_KEYPOINTS

    parser = argparse.ArgumentParser(description="Dia gesture controller")
    parser.add_argument(
        "--debug-keypoints",
        action="store_true",
        help="Print raw keypoints each frame (no gestures fired)",
    )
    args, _unknown = parser.parse_known_args()
    DEBUG_KEYPOINTS = args.debug_keypoints

    if DEBUG_KEYPOINTS:
        logger.info("Debug-keypoints mode — gestures will NOT fire")
        logger.info("Raise both arms and verify wrist Y < nose Y")
    else:
        logger.info("No mode specified — run with --debug-keypoints for Part 2")

    user_data = _UserData()
    app = GStreamerPoseEstimationApp(app_callback, user_data)
    logger.info("Starting GStreamer pipeline…")
    app.run()


if __name__ == "__main__":
    main()
