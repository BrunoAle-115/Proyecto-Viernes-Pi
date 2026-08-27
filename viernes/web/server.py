"""
Servidor Web FastAPI y Hub de WebSockets para el Dashboard HUD de V.I.E.R.N.E.S.
"""

import os
import json
import asyncio
import logging
from typing import List, Dict, Any
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from viernes.core.telemetry import SystemTelemetry
from viernes.core.event_bus import bus, Event
from viernes.core.tools_registry import ToolsDispatcher
from viernes.core.gemini_live import gemini_client
from viernes.core.audio_pipeline import audio_pipeline
from viernes.core.wake_word import wakeword_detector
from viernes.iot.device_manager import device_mgr
from viernes.mail.gmail_client import gmail_client
from viernes.mail.zoho_client import zoho_client
from viernes.integrations.github_monitor import github_monitor
from viernes.scheduler.reminder_engine import reminder_engine
from viernes.telephony.sip_manager import sip_mgr

logger = logging.getLogger("viernes.web")

BASE_DIR = os.path.dirname(__file__)
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

app = FastAPI(title="V.I.E.R.N.E.S. HUD", description="Stark Industries AI Assistant Dashboard")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Montar archivos estáticos
os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(os.path.join(STATIC_DIR, "css"), exist_ok=True)
os.makedirs(os.path.join(STATIC_DIR, "js"), exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: Dict[str, Any]):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(connection)


ws_manager = ConnectionManager()


# Conectar el EventBus con el WebSocket broadcast
async def on_system_event(event: Event):
    await ws_manager.broadcast({
        "type": "event",
        "topic": event.topic,
        "data": event.data,
        "sender": event.sender,
        "timestamp": event.timestamp,
    })

bus.subscribe("*", on_system_event)


# Modelos Pydantic para endpoints REST
class WolRequest(BaseModel):
    target: str

class LightRequest(BaseModel):
    target: str
    action: str = "toggle"
    brightness: int = 100

class PromptRequest(BaseModel):
    prompt: str

class CallRequest(BaseModel):
    phone_number: str
    reason: str = "Llamada desde HUD"

class ReminderRequest(BaseModel):
    title: str
    time_iso: str
    is_alarm: bool = False


# Endpoints REST
@app.get("/", response_class=HTMLResponse)
async def get_dashboard(request: Request):
    return templates.TemplateResponse("hud.html", {"request": request, "title": "V.I.E.R.N.E.S. Stark HUD"})

@app.get("/api/status")
async def get_system_status():
    return SystemTelemetry.get_full_status()

@app.get("/api/devices")
async def get_devices():
    return list(device_mgr.devices.values())

@app.post("/api/scan")
async def trigger_network_scan():
    devices = await device_mgr.scan_and_update()
    return {"success": True, "count": len(devices), "devices": devices}

@app.post("/api/wol")
async def trigger_wol(req: WolRequest):
    return await device_mgr.execute_turn_on(req.target)

@app.post("/api/lights")
async def trigger_lights(req: LightRequest):
    return await device_mgr.execute_control_light(req.target, req.action, req.brightness)

@app.get("/api/emails")
async def get_emails():
    gmail = await gmail_client.get_unread_emails(max_results=5, only_important=True)
    zoho = zoho_client.get_unread_emails(max_results=5, only_important=True)
    return {"gmail": gmail, "zoho": zoho, "total": len(gmail) + len(zoho)}

@app.get("/api/github")
async def get_github_prs():
    return await github_monitor.get_pull_requests_summary()

@app.get("/api/telephony")
async def get_telephony_status():
    return sip_mgr.get_telephony_status()

@app.post("/api/call")
async def make_call(req: CallRequest):
    return await sip_mgr.originate_call(req.phone_number)

@app.get("/api/reminders")
async def get_reminders():
    return await reminder_engine.get_active_reminders()

@app.post("/api/reminders")
async def create_reminder(req: ReminderRequest):
    return await reminder_engine.add_reminder(req.title, req.time_iso, req.is_alarm)

@app.post("/api/prompt")
async def send_prompt(req: PromptRequest):
    response_text = await gemini_client.send_text_prompt(req.prompt)
    return {"success": True, "response": response_text}

@app.post("/api/wakeword/trigger")
async def trigger_voice():
    wakeword_detector.trigger_manually()
    return {"success": True, "message": "V.I.E.R.N.E.S. activada."}


# WebSocket en tiempo real para Streaming de Telemetría y Audio Waveform
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            # Enviar snapshot periódico de telemetría y nivel de audio
            telemetry = SystemTelemetry.get_full_status()
            telemetry["audio_rms"] = audio_pipeline.current_volume_rms
            telemetry["is_speaking"] = gemini_client.is_speaking
            telemetry["is_connected_ai"] = gemini_client.is_connected

            await websocket.send_json({
                "type": "telemetry",
                "data": telemetry
            })
            await asyncio.sleep(0.1) # 10 Hz refresh
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.debug(f"Desconexión de websocket: {e}")
        ws_manager.disconnect(websocket)
