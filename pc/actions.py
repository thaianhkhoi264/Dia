"""
actions.py — Spotify playback actions for the Dia PC listener.

All playback is controlled through the Spotify Web API via Spotipy.
Requires Spotify Premium and credentials in .env (see .env.example).
"""

import logging
import os

import spotipy
from spotipy.oauth2 import SpotifyOAuth

logger = logging.getLogger(__name__)

VOLUME_STEP = 10  # percentage points per gesture

_sp: spotipy.Spotify | None = None


def _spotify() -> spotipy.Spotify:
    """Return the shared Spotipy client, creating it on first call."""
    global _sp
    if _sp is None:
        _sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
            client_id     = os.environ["SPOTIPY_CLIENT_ID"],
            client_secret = os.environ["SPOTIPY_CLIENT_SECRET"],
            redirect_uri  = os.environ.get("SPOTIPY_REDIRECT_URI", "http://127.0.0.1:8888/callback"),
            scope         = "user-read-playback-state user-modify-playback-state",
            cache_handler = spotipy.cache_handler.CacheFileHandler(
                cache_path = os.path.join(os.path.dirname(__file__), ".spotify_cache")
            ),
            open_browser  = True,
        ))
    return _sp


# ---------------------------------------------------------------------------
# Action implementations
# ---------------------------------------------------------------------------

def action_play_pause() -> None:
    sp = _spotify()
    playback = sp.current_playback()
    if playback and playback["is_playing"]:
        sp.pause_playback()
        logger.info("Action: pause")
    else:
        sp.start_playback()
        logger.info("Action: resume")


def action_next_track() -> None:
    _spotify().next_track()
    logger.info("Action: next track")


def action_volume_up() -> None:
    sp = _spotify()
    playback = sp.current_playback()
    if playback:
        current = playback["device"]["volume_percent"]
        new_vol = min(100, current + VOLUME_STEP)
        sp.volume(new_vol)
        logger.info("Action: volume up %d%% → %d%%", current, new_vol)


def action_volume_down() -> None:
    sp = _spotify()
    playback = sp.current_playback()
    if playback:
        current = playback["device"]["volume_percent"]
        new_vol = max(0, current - VOLUME_STEP)
        sp.volume(new_vol)
        logger.info("Action: volume down %d%% → %d%%", current, new_vol)


# ---------------------------------------------------------------------------
# Dispatch map
# ---------------------------------------------------------------------------

ACTION_MAP = {
    "PLAY_PAUSE":  action_play_pause,
    "NEXT_TRACK":  action_next_track,
    "VOLUME_UP":   action_volume_up,
    "VOLUME_DOWN": action_volume_down,
}
