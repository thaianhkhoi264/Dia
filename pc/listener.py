"""
listener.py — Dia PC-side command listener.

Runs a Flask HTTP server on port 7000.
The Pi sends POST /command with {"action": "PLAY_PAUSE"} (etc.) and this
server dispatches to the appropriate Windows action.

Usage:
    python listener.py

Firewall: allow inbound TCP 7000 on Private profile.
  New-NetFirewallRule -DisplayName "Dia Gesture Listener" `
      -Direction Inbound -Protocol TCP -LocalPort 7000 -Action Allow -Profile Private
"""

import logging
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from flask import Flask, jsonify, request

from actions import ACTION_MAP

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)


@app.route("/command", methods=["POST"])
def command():
    data = request.get_json(silent=True)

    if not data or "action" not in data:
        logger.warning("Bad request — missing 'action' field: %s", data)
        return jsonify({"error": "missing 'action' field"}), 400

    action = data["action"]
    fn = ACTION_MAP.get(action)

    if fn is None:
        logger.warning("Unknown action: %s", action)
        return jsonify({"error": f"unknown action: {action}"}), 400

    try:
        fn()
        return jsonify({"status": "ok", "action": action})
    except Exception as exc:
        logger.exception("Action '%s' raised an exception", action)
        return jsonify({"error": str(exc)}), 500


@app.route("/ping", methods=["GET"])
def ping():
    """Simple health-check — useful for testing connectivity from the Pi."""
    return jsonify({"status": "alive"})


if __name__ == "__main__":
    logger.info("Dia PC listener starting on 0.0.0.0:7000")
    app.run(host="0.0.0.0", port=7000)
