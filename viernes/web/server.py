"""
Servidor Web FastAPI y Hub de WebSockets para el Dashboard HUD de V.I.E.R.N.E.S.
Incluye Autenticación Robusta, Portal de Configuración .env, Noticias, Clima y Mini-RAG.
"""

import os
import json
import asyncio
import logging
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Depends, HTTPException, status, Response, Cookie
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel

from viernes.core.telemetry import SystemTelemetry
from viernes.core.event_bus import bus, Event
from viernes.core.tools_registry import ToolsDispatcher
from viernes.core.gemini_live import gemini_client
from viernes.core.audio_pipeline import audio_pipeline
from viernes.core.wake_word import wakeword_detector
from viernes.core.models_manager import models_manager
from viernes.iot.device_manager import device_mgr
from viernes.mail.gmail_client import gmail_client
from viernes.mail.zoho_client import zoho_client
from viernes.integrations.github_monitor import github_monitor
from viernes.scheduler.reminder_engine import reminder_engine
from viernes.telephony.sip_manager import sip_mgr
from viernes.services.news_chile import chile_news
from viernes.services.weather_engine import weather_engine
from viernes.memory.mini_rag import personal_rag
from viernes.auth.manager import auth_mgr, DEFAULT_ADMIN_EMAIL

logger = logging.getLogger("viernes.web")

BASE_DIR = os.path.dirname(__file__)
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(BASE_DIR)), ".env")

app = FastAPI(title="V.I.E.R.N.E.S. HUD", description="Stark Industries AI Assistant Dashboard 2.0")
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


# Modelos Pydantic
class LoginRequest(BaseModel):
    email: str
    password: str

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

class MemoryRequest(BaseModel):
    category: str
    key_concept: str
    content: str

class ModelSwitchRequest(BaseModel):
    model_id: str

class SettingsUpdateRequest(BaseModel):
    gemini_api_key: Optional[str] = None
    gemini_model: Optional[str] = None
    github_token: Optional[str] = None
    github_username: Optional[str] = None
    github_repos: Optional[str] = None
    zoho_email: Optional[str] = None
    zoho_password: Optional[str] = None
    sip_provider: Optional[str] = None
    sip_username: Optional[str] = None
    sip_password: Optional[str] = None
    default_city: Optional[str] = None


# Dependencia de Autenticación
def get_current_user(session_token: Optional[str] = Cookie(default=None), request: Request = None):
    # Buscar en Cookie o en Header Authorization
    token = session_token
    if not token and request:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No autenticado")

    payload = auth_mgr.validate_session(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sesión inválida o expirada")
    return payload


# --- RUTAS DE AUTENTICACIÓN ---
@app.post("/api/auth/login")
async def api_login(req: LoginRequest, response: Response):
    token = auth_mgr.authenticate(req.email, req.password)
    if not token:
        raise HTTPException(status_code=400, detail="Credenciales incorrectas")

    # Set HTTP-Only secure session cookie
    response.set_cookie(
        key="session_token",
        value=token,
        httponly=True,
        max_age=86400 * 7,
        samesite="lax"
    )
    return {"success": True, "token": token, "email": req.email.lower()}

@app.post("/api/auth/logout")
async def api_logout(response: Response):
    response.delete_cookie("session_token")
    return {"success": True, "message": "Sesión cerrada"}

@app.get("/api/auth/me")
async def api_auth_me(user: dict = Depends(get_current_user)):
    return {"authenticated": True, "user": user}


# --- RUTAS PRINCIPALES DEL HUD ---
@app.get("/", response_class=HTMLResponse)
async def get_dashboard(request: Request):
    return templates.TemplateResponse("hud.html", {"request": request, "title": "V.I.E.R.N.E.S. Stark HUD 2.0"})

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


# --- NUEVAS RUTAS: NOTICIAS, CLIMA, MODELOS, MEMORIA & CONFIGURACIÓN ---
@app.get("/api/news")
async def get_chile_news_api():
    news = await chile_news.get_top_news(limit=6)
    return {"news": news, "count": len(news)}

@app.get("/api/weather")
async def get_weather_api(city: str = "santiago"):
    return await weather_engine.get_forecast(city)

@app.get("/api/models")
async def get_gemini_models_api():
    models = await models_manager.list_available_models()
    return {"models": models, "active_model": models_manager.active_model}

@app.post("/api/models/active")
async def set_gemini_active_model(req: ModelSwitchRequest):
    return models_manager.set_active_model(req.model_id)

@app.get("/api/memory")
async def get_memories_api():
    memories = await personal_rag.get_all_memories()
    return {"memories": memories, "count": len(memories)}

@app.post("/api/memory")
async def add_memory_api(req: MemoryRequest):
    return await personal_rag.store_memory(req.category, req.key_concept, req.content)

@app.get("/api/settings")
async def get_settings_api(user: dict = Depends(get_current_user)):
    """Retorna las variables configuradas de forma segura (con llaves parcialmente enmascaradas)."""
    raw_key = os.getenv("GEMINI_API_KEY", "")
    masked_key = raw_key[:6] + "..." + raw_key[-4:] if len(raw_key) > 10 else ""

    raw_gh = os.getenv("GITHUB_TOKEN", "")
    masked_gh = raw_gh[:6] + "..." + raw_gh[-4:] if len(raw_gh) > 10 else ""

    return {
        "gemini_api_key_masked": masked_key,
        "gemini_model": models_manager.active_model,
        "github_username": os.getenv("GITHUB_USERNAME", "BrunoAle-115"),
        "github_token_masked": masked_gh,
        "github_repos": os.getenv("GITHUB_REPOS", "BrunoAle-115/Proyecto-Viernes-Pi"),
        "zoho_email": os.getenv("ZOHO_EMAIL_USER", os.getenv("ZOHO_EMAIL", "")),
        "sip_provider": os.getenv("SIP_PROVIDER", "zadarma_chile"),
        "sip_did_number": os.getenv("SIP_DID_NUMBER", "+56912345678"),
        "default_city": os.getenv("DEFAULT_CITY", "santiago"),
        "web_port": int(os.getenv("WEB_PORT", 9090))
    }

@app.post("/api/settings")
async def update_settings_api(req: SettingsUpdateRequest, user: dict = Depends(get_current_user)):
    """Actualiza variables de configuración en memoria y en el archivo .env de forma persistente."""
    updates = {}
    if req.gemini_api_key and not req.gemini_api_key.startswith("AIzaSy..."):
        os.environ["GEMINI_API_KEY"] = req.gemini_api_key
        gemini_client.api_key = req.gemini_api_key
        updates["GEMINI_API_KEY"] = f'"{req.gemini_api_key}"'

    if req.gemini_model:
        models_manager.set_active_model(req.gemini_model)
        updates["GEMINI_MODEL"] = f'"{req.gemini_model}"'

    if req.github_token and not req.github_token.startswith("ghp_..."):
        os.environ["GITHUB_TOKEN"] = req.github_token
        updates["GITHUB_TOKEN"] = f'"{req.github_token}"'

    if req.github_username:
        os.environ["GITHUB_USERNAME"] = req.github_username
        updates["GITHUB_USERNAME"] = f'"{req.github_username}"'

    if req.github_repos:
        os.environ["GITHUB_REPOS"] = f'"{req.github_repos}"'
        updates["GITHUB_REPOS"] = f'"{req.github_repos}"'

    if req.zoho_email:
        os.environ["ZOHO_EMAIL"] = req.zoho_email
        updates["ZOHO_EMAIL"] = f'"{req.zoho_email}"'

    if req.zoho_password and not req.zoho_password.startswith("your_"):
        os.environ["ZOHO_PASSWORD"] = req.zoho_password
        updates["ZOHO_PASSWORD"] = f'"{req.zoho_password}"'

    if req.sip_provider:
        os.environ["SIP_PROVIDER"] = req.sip_provider
        sip_mgr.provider_name = req.sip_provider
        updates["SIP_PROVIDER"] = f'"{req.sip_provider}"'

    # Escribir o actualizar en .env
    if os.path.exists(ENV_PATH) and updates:
        try:
            with open(ENV_PATH, "r", encoding="utf-8") as f:
                lines = f.readlines()

            new_lines = []
            applied_keys = set()
            for line in lines:
                matched = False
                for k, v in updates.items():
                    if line.strip().startswith(f"{k}="):
                        new_lines.append(f"{k}={v}\n")
                        applied_keys.add(k)
                        matched = True
                        break
                if not matched:
                    new_lines.append(line)

            for k, v in updates.items():
                if k not in applied_keys:
                    new_lines.append(f"{k}={v}\n")

            with open(ENV_PATH, "w", encoding="utf-8") as f:
                f.writelines(new_lines)

            logger.info("Archivo .env actualizado exitosamente desde el Dashboard.")
        except Exception as e:
            logger.error(f"Error escribiendo en .env: {e}")

    return {"success": True, "message": "Configuraciones actualizadas y guardadas en .env."}


# --- WEBSOCKET DE TELEMETRÍA Y AUDIO WAVEFORM ---
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            telemetry = SystemTelemetry.get_full_status()
            telemetry["audio_rms"] = audio_pipeline.current_volume_rms
            telemetry["is_speaking"] = gemini_client.is_speaking
            telemetry["is_connected_ai"] = gemini_client.is_connected
            telemetry["active_model"] = models_manager.active_model

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
