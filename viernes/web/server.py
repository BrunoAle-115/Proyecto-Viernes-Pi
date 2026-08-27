"""
Servidor Web FastAPI y Hub de WebSockets Blindado para V.I.E.R.N.E.S. 2.0.
Protección contra IDOR, XSS, Hijacking de WebSockets/WebRTC, Brute Force y Rate Limiting.
"""

import os
import json
import asyncio
import logging
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Depends, HTTPException, status, Response, Cookie
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel, Field, validator

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
from viernes.memory.vector_rag import vector_rag
from viernes.auth.manager import auth_mgr, DEFAULT_ADMIN_EMAIL
from viernes.auth.security import rate_limiter, auth_rate_limiter, sanitize_text, sanitize_ip_or_mac

logger = logging.getLogger("viernes.web")

BASE_DIR = os.path.dirname(__file__)
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(BASE_DIR)), ".env")

app = FastAPI(
    title="V.I.E.R.N.E.S. HUD",
    description="Stark Industries AI Assistant Dashboard 2.0 - Security Hardened",
    docs_url=None, # Deshabilitar Swagger UI público para evitar reconocimiento
    redoc_url=None
)
templates = Jinja2Templates(directory=TEMPLATES_DIR)


# --- MIDDLEWARE DE CABECERAS DE SEGURIDAD (Anti-XSS, Clickjacking, MIME Sniffing) ---
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if not path.startswith("/static") and path != "/favicon.ico":
            client_ip = request.client.host if request.client else "127.0.0.1"
            if not rate_limiter.is_allowed(client_ip):
                return JSONResponse(
                    status_code=429,
                    content={"error": "Too Many Requests. Rate limit exceeded por seguridad."}
                )

        response = await call_next(request)
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data:; "
            "connect-src 'self' ws: wss:; "
            "frame-ancestors 'none';"
        )
        return response


app.add_middleware(SecurityHeadersMiddleware)

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


async def on_system_event(event: Event):
    await ws_manager.broadcast({
        "type": "event",
        "topic": event.topic,
        "data": event.data,
        "sender": event.sender,
        "timestamp": event.timestamp,
    })

bus.subscribe("*", on_system_event)


from pydantic import BaseModel, Field, field_validator

# Modelos Pydantic con Sanitización y Validación Robusta
class LoginRequest(BaseModel):
    email: str = Field(..., max_length=120)
    password: str = Field(..., max_length=128)

class WolRequest(BaseModel):
    target: str = Field(..., max_length=60)

    @field_validator("target")
    @classmethod
    def sanitize_target(cls, v: str) -> str:
        return sanitize_ip_or_mac(v)

class LightRequest(BaseModel):
    target: str = Field(default="luz_wiz", max_length=60)
    action: str = Field(default="toggle", max_length=20)
    brightness: int = Field(default=100, ge=1, le=100)
    palette: Optional[str] = Field(default=None, max_length=40)

class AcRequest(BaseModel):
    target: str = Field(default="aire_ac", max_length=60)
    power: bool = Field(default=True)
    temperature: int = Field(default=22, ge=16, le=30)
    mode: str = Field(default="cool", max_length=20)
    fan_speed: str = Field(default="auto", max_length=20)

class FrutifantasticoRequest(BaseModel):
    track: str = Field(default="blinding_lights", max_length=50)
    light_ip: str = Field(default="192.168.100.15", max_length=40)
    tv_ip: str = Field(default="192.168.100.25", max_length=40)
    speaker_ip: str = Field(default="192.168.100.31", max_length=40)
    ac_ip: str = Field(default="192.168.100.20", max_length=40)

class CastRequest(BaseModel):
    target_ip: str = Field(default="192.168.100.25", max_length=40)
    command: str = Field(default="play_youtube", max_length=30)
    youtube_id: Optional[str] = Field(default="4NRXx6U8ABQ", max_length=50)

class PromptRequest(BaseModel):
    prompt: str = Field(..., max_length=1000)

    @field_validator("prompt")
    @classmethod
    def sanitize_prompt(cls, v: str) -> str:
        return sanitize_text(v)

class CallRequest(BaseModel):
    phone_number: str = Field(..., max_length=25)
    reason: str = Field(default="Llamada desde HUD", max_length=100)

class ReminderRequest(BaseModel):
    title: str = Field(..., max_length=150)
    time_iso: str = Field(..., max_length=40)
    is_alarm: bool = False

class MemoryRequest(BaseModel):
    category: str = Field(..., max_length=40)
    key_concept: str = Field(..., max_length=80)
    content: str = Field(..., max_length=1500)

class ModelSwitchRequest(BaseModel):
    model_id: str = Field(..., max_length=80)

class SettingsUpdateRequest(BaseModel):
    gemini_api_key: Optional[str] = None
    gemini_model: Optional[str] = None
    github_token: Optional[str] = None
    github_username: Optional[str] = None
    github_repos: Optional[str] = None
    zoho_email: Optional[str] = None
    zoho_password: Optional[str] = None
    sip_provider: Optional[str] = None
    default_city: Optional[str] = None


# Dependencia de Autenticación Centralizada (Anti-IDOR)
def get_current_user(session_token: Optional[str] = Cookie(default=None), request: Request = None):
    token = session_token
    if not token and request:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Autenticación requerida")

    payload = auth_mgr.validate_session(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sesión inválida o expirada")
    return payload


# --- RUTAS DE AUTENTICACIÓN ---
@app.post("/api/auth/login")
async def api_login(req: LoginRequest, request: Request, response: Response):
    client_ip = request.client.host if request.client else "127.0.0.1"
    logger.info(f"Intento de autenticación recibido desde {client_ip} para: {req.email}")

    # No bloquear IPs de LAN privada ni localhost
    is_lan = client_ip in ("127.0.0.1", "localhost", "::1") or client_ip.startswith("192.168.") or client_ip.startswith("10.")
    if not is_lan and not auth_rate_limiter.is_allowed(client_ip):
        raise HTTPException(status_code=429, detail="Demasiados intentos de acceso. Bloqueo temporal por 60 segundos.")

    token = auth_mgr.authenticate(req.email, req.password)
    if not token:
        logger.warning(f"❌ Autenticación rechazada para: {req.email}")
        raise HTTPException(status_code=400, detail="Contraseña o correo no válidos.")

    logger.info(f"✓ Acceso táctico concedido a: {req.email}")
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


# --- RUTAS PRINCIPALES DEL HUD (PROTEGIDAS CONTRA IDOR) ---
@app.get("/favicon.ico", include_in_schema=False)
async def get_favicon():
    fav_path = os.path.join(STATIC_DIR, "favicon.svg")
    if os.path.exists(fav_path):
        return FileResponse(fav_path, media_type="image/svg+xml")
    return Response(status_code=204)

@app.get("/", response_class=HTMLResponse)
async def get_dashboard(request: Request):
    return templates.TemplateResponse(request=request, name="hud.html", context={"title": "V.I.E.R.N.E.S. Stark HUD 2.0"})

@app.get("/api/status")
async def get_system_status():
    return SystemTelemetry.get_full_status()

@app.get("/api/devices")
async def get_devices(user: dict = Depends(get_current_user)):
    return list(device_mgr.devices.values())

@app.post("/api/scan")
async def trigger_network_scan(user: dict = Depends(get_current_user)):
    devices = await device_mgr.scan_and_update()
    return {"success": True, "count": len(devices), "devices": devices}

@app.post("/api/wol")
async def trigger_wol(req: WolRequest, user: dict = Depends(get_current_user)):
    return await device_mgr.execute_turn_on(req.target)

@app.post("/api/lights")
async def trigger_lights(req: LightRequest, user: dict = Depends(get_current_user)):
    return await device_mgr.execute_control_light(req.target, req.action, req.brightness, req.palette)

@app.get("/api/lights/status")
async def get_lights_status(target: str = "luz_wiz", user: dict = Depends(get_current_user)):
    return await device_mgr.execute_get_light_status(target)

@app.post("/api/ac")
async def trigger_ac(req: AcRequest, user: dict = Depends(get_current_user)):
    return await device_mgr.execute_control_ac(
        target_name_or_ip=req.target,
        power=req.power,
        target_temp=req.temperature,
        mode=req.mode,
        fan_speed=req.fan_speed
    )

@app.post("/api/macro/frutifantastico")
async def trigger_frutifantastico(req: FrutifantasticoRequest, user: dict = Depends(get_current_user)):
    from viernes.iot.party_macro import party_engine
    return await party_engine.trigger_frutifantastico_mode(
        light_ip=req.light_ip,
        tv_ip=req.tv_ip,
        speaker_ip=req.speaker_ip,
        ac_ip=req.ac_ip,
        track_key=req.track
    )

@app.post("/api/macro/frutifantastico/stop")
async def stop_frutifantastico(user: dict = Depends(get_current_user)):
    from viernes.iot.party_macro import party_engine
    return await party_engine.stop_party_mode()

@app.post("/api/android_tv")
async def trigger_android_tv(req: CastRequest, user: dict = Depends(get_current_user)):
    from viernes.iot.android_tv_cast import cast_controller
    if req.command == "play_youtube" and req.youtube_id:
        ok = await cast_controller.launch_youtube_video(req.target_ip, req.youtube_id)
        return {"success": ok, "message": f"Video ({req.youtube_id}) transmitido a Android TV / Cast."}
    else:
        return await cast_controller.send_media_command(req.target_ip, req.command)

@app.get("/api/emails")
async def get_emails(user: dict = Depends(get_current_user)):
    gmail = []
    zoho = []
    try:
        gmail = await asyncio.wait_for(gmail_client.get_unread_emails(max_results=5, only_important=True), timeout=2.0)
    except Exception:
        pass
    try:
        zoho = await asyncio.wait_for(asyncio.to_thread(zoho_client.get_unread_emails, max_results=5, only_important=True), timeout=2.0)
    except Exception:
        pass
    return {"gmail": gmail, "zoho": zoho, "total": len(gmail) + len(zoho)}

@app.get("/api/github")
async def get_github_prs(user: dict = Depends(get_current_user)):
    try:
        return await asyncio.wait_for(github_monitor.get_pull_requests_summary(), timeout=2.5)
    except Exception:
        return {"total_prs": 0, "prs": [], "pending_review_count": 0, "ready_for_merge_count": 0}

@app.get("/api/telephony")
async def get_telephony_status(user: dict = Depends(get_current_user)):
    return sip_mgr.get_telephony_status()

@app.post("/api/call")
async def make_call(req: CallRequest, user: dict = Depends(get_current_user)):
    return await sip_mgr.originate_call(req.phone_number)

@app.get("/api/reminders")
async def get_reminders(user: dict = Depends(get_current_user)):
    return await reminder_engine.get_active_reminders()

@app.post("/api/reminders")
async def create_reminder(req: ReminderRequest, user: dict = Depends(get_current_user)):
    return await reminder_engine.add_reminder(req.title, req.time_iso, req.is_alarm)

@app.post("/api/prompt")
async def send_prompt(req: PromptRequest, user: dict = Depends(get_current_user)):
    response_text = await gemini_client.send_text_prompt(req.prompt)
    return {"success": True, "response": response_text}

@app.post("/api/wakeword/trigger")
async def trigger_voice(user: dict = Depends(get_current_user)):
    wakeword_detector.trigger_manually()
    return {"success": True, "message": "V.I.E.R.N.E.S. activada."}


# --- RUTAS DE SERVICIOS (CLIMA, NOTICIAS, MODELOS Y VECTOR RAG) ---
@app.get("/api/news")
async def get_chile_news_api():
    news = await chile_news.get_top_news(limit=6)
    return {"news": news, "count": len(news)}

@app.get("/api/weather")
async def get_weather_api(city: str = "santiago"):
    return await weather_engine.get_forecast(city)

@app.get("/api/models")
async def get_gemini_models_api(user: dict = Depends(get_current_user)):
    models = await models_manager.list_available_models()
    return {"models": models, "active_model": models_manager.active_model}

@app.post("/api/models/active")
async def set_gemini_active_model(req: ModelSwitchRequest, user: dict = Depends(get_current_user)):
    return models_manager.set_active_model(req.model_id)

@app.get("/api/memory")
async def get_memories_api(user: dict = Depends(get_current_user)):
    memories = await vector_rag.get_all_vector_memories()
    return {"memories": memories, "count": len(memories)}

@app.post("/api/memory")
async def add_memory_api(req: MemoryRequest, user: dict = Depends(get_current_user)):
    return await vector_rag.insert_memory(req.category, req.key_concept, req.content, source="user_hud")

@app.get("/api/settings")
async def get_settings_api(user: dict = Depends(get_current_user)):
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

    # Escribir en .env
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


# --- WEBSOCKET BLINDADO (Anti-WebRTC / WebSocket Hijacking) ---
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: Optional[str] = None):
    # Validar autenticación de handshake en WebSocket
    auth_token = token or websocket.cookies.get("session_token")
    if not auth_token or not auth_mgr.validate_session(auth_token):
        # Rechazo de conexión no autorizada
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

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
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.debug(f"Desconexión de websocket: {e}")
        ws_manager.disconnect(websocket)
