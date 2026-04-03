# Dia — Gesture-Based PC Controller

Control your Windows PC from across the room using body gestures detected by a Raspberry Pi 5 + Hailo-8L AI HAT.

> **This repo is built incrementally.** Currently contains Part 1: the Windows PC listener.

## How it works (full system)

```
[USB Webcam] → [Raspberry Pi 5 + Hailo-8L NPU] → [Gesture Detection]
    → [LAN] → [PC Listener] → [Windows Action]
```

## Part 1 — PC Listener

The PC side runs a small HTTP server. When the Pi detects a gesture, it sends a POST request here and the listener executes the corresponding Windows action (media keys, volume, Spotify).

### Setup

```powershell
cd pc
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Allow inbound connections (run PowerShell as Administrator):
```powershell
New-NetFirewallRule -DisplayName "Dia Gesture Listener" `
    -Direction Inbound -Protocol TCP -LocalPort 7000 -Action Allow -Profile Private
```

Run:
```powershell
python listener.py
```

### Test

```bash
# Health check
curl http://localhost:7000/ping

# Send a command
curl -X POST http://localhost:7000/command \
     -H "Content-Type: application/json" \
     -d '{"action": "PLAY_PAUSE"}'
```

Available actions: `PLAY_PAUSE`, `NEXT_TRACK`, `VOLUME_UP`, `VOLUME_DOWN`, `RICKROLL`
