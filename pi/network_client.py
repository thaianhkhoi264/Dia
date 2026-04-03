"""
network_client.py — Outbound network operations for Dia.

  send_wol()     — broadcasts a Wake-on-LAN magic packet (PC doesn't need to be on)
  send_command() — HTTP POST to the PC listener (PC must be awake)
"""

import logging

import requests
import wakeonlan

logger = logging.getLogger(__name__)


def send_wol(mac: str) -> None:
    """Send a Wake-on-LAN magic packet to the given MAC address."""
    try:
        wakeonlan.send_magic_packet(mac)
        logger.info("WoL packet sent to %s", mac)
    except Exception:
        logger.exception("Failed to send WoL packet to %s", mac)


def send_command(action: str, pc_ip: str, port: int) -> None:
    """
    POST {"action": action} to http://{pc_ip}:{port}/command.

    Connection errors are swallowed — the PC may still be waking up.
    """
    url = f"http://{pc_ip}:{port}/command"
    try:
        resp = requests.post(url, json={"action": action}, timeout=2)
        resp.raise_for_status()
        logger.info("Command sent: %s → %s", action, resp.json())
    except requests.exceptions.ConnectionError:
        logger.warning("Could not reach PC at %s (offline or firewall?)", url)
    except requests.exceptions.Timeout:
        logger.warning("Command timed out: %s → %s", action, url)
    except Exception:
        logger.exception("Unexpected error sending command %s", action)
