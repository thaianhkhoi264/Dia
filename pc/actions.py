"""
actions.py — Windows action implementations for the Dia PC listener.

Each function corresponds to one gesture command sent from the Pi.
All OS-specific code (pycaw, keyboard, Spotify URI) is isolated here.
"""

import logging
import os

import keyboard
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

logger = logging.getLogger(__name__)

SPOTIFY_RICKROLL_URI = "spotify:track:4PTG3Z6ehGkBFwjybzWkR8"
VOLUME_STEP = 0.10  # 10% per gesture


# ---------------------------------------------------------------------------
# pycaw helper
# ---------------------------------------------------------------------------

def _get_volume_interface() -> IAudioEndpointVolume:
    """Return the default audio endpoint volume COM interface."""
    devices = AudioUtilities.GetSpeakers()
    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    return interface.QueryInterface(IAudioEndpointVolume)


# ---------------------------------------------------------------------------
# Action implementations
# ---------------------------------------------------------------------------

def action_play_pause() -> None:
    keyboard.send("play/pause media")
    logger.info("Action: play/pause")


def action_next_track() -> None:
    keyboard.send("next track")
    logger.info("Action: next track")


def action_volume_up() -> None:
    vol = _get_volume_interface()
    current = vol.GetMasterVolumeLevelScalar()
    new_vol = min(1.0, current + VOLUME_STEP)
    vol.SetMasterVolumeLevelScalar(new_vol, None)
    logger.info("Action: volume up %.0f%% → %.0f%%", current * 100, new_vol * 100)


def action_volume_down() -> None:
    vol = _get_volume_interface()
    current = vol.GetMasterVolumeLevelScalar()
    new_vol = max(0.0, current - VOLUME_STEP)
    vol.SetMasterVolumeLevelScalar(new_vol, None)
    logger.info("Action: volume down %.0f%% → %.0f%%", current * 100, new_vol * 100)


def action_rickroll() -> None:
    os.startfile(SPOTIFY_RICKROLL_URI)
    logger.info("Action: rickroll — opened %s", SPOTIFY_RICKROLL_URI)


# ---------------------------------------------------------------------------
# Dispatch map
# ---------------------------------------------------------------------------

ACTION_MAP = {
    "PLAY_PAUSE":   action_play_pause,
    "NEXT_TRACK":   action_next_track,
    "VOLUME_UP":    action_volume_up,
    "VOLUME_DOWN":  action_volume_down,
    "RICKROLL":     action_rickroll,
}
