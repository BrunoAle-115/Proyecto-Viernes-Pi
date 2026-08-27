"""
V.I.E.R.N.E.S. - Entrypoint Principal del Asistente de IA para Raspberry Pi 5.
"""

import os
import sys
import asyncio
import logging

# Garantizar que el directorio raíz del proyecto esté en sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import uvicorn
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

# Configurar Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("viernes.core")

from viernes.core.event_bus import bus
from viernes.core.telemetry import SystemTelemetry
from viernes.core.audio_pipeline import audio_pipeline
from viernes.core.gemini_live import gemini_client
from viernes.iot.device_manager import device_mgr
from viernes.telephony.sip_manager import sip_mgr
from viernes.scheduler.reminder_engine import reminder_engine
from viernes.web.server import app


async def periodic_network_scanner():
    """Ejecuta escaneos de red periódicos para mantener actualizado el inventario y estado."""
    logger.info("Iniciando escáner periódico de red en segundo plano...")
    while True:
        try:
            await device_mgr.scan_and_update()
        except Exception as e:
            logger.error(f"Error en escáner periódico de red: {e}")
        await asyncio.sleep(300) # Cada 5 minutos


async def start_assistant():
    """Inicia todos los subsistemas del framework V.I.E.R.N.E.S."""
    logger.info("=" * 60)
    logger.info("  V.I.E.R.N.E.S. - TACTICAL AI SYSTEM INICIALIZANDO...")
    logger.info("  Hardware: Raspberry Pi 5 (ARM64) // Stark Industries")
    logger.info("=" * 60)

    # 1. Inicializar base de datos y recordatorios
    await reminder_engine.initialize()

    # 2. Inicializar subsistema SIP
    await sip_mgr.connect()

    # 3. Escaneo inicial de red
    asyncio.create_task(device_mgr.scan_and_update())

    # 4. Iniciar escáner periódico
    asyncio.create_task(periodic_network_scanner())

    # 5. Iniciar pipeline de audio y conexión con Gemini Live
    await audio_pipeline.start()
    asyncio.create_task(gemini_client.connect())

    # Manejador de Wake Word / Activación por voz continua (Ever-Listen)
    async def on_wakeword_detected(event):
        data_val = getattr(event, 'data', event)
        logger.info(f"🎙️ [Ever-Listen] Activación por voz recibida ({data_val}). Canal de voz listo.")
        if not gemini_client.is_connected:
            asyncio.create_task(gemini_client.connect())

    bus.subscribe("wakeword/detected", on_wakeword_detected)

    # 6. Publicar evento de sistema en línea
    await bus.publish("system/ready", {
        "status": "ONLINE",
        "ip": SystemTelemetry.get_local_ip(),
        "telemetry": SystemTelemetry.get_full_status()
    }, sender="main")

    logger.info("V.I.E.R.N.E.S. completamente en línea y lista para recibir instrucciones.")


def main():
    """Función de arranque con Auto-Switching de Puertos y soporte HTTPS (Secure Contexts)."""
    from viernes.core.port_manager import port_manager
    from viernes.core.ssl_manager import ssl_mgr

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Auditar servicios coexistentes (Pi-hole, Asterisk, Tailscale)
    audit = port_manager.check_system_services_collision()
    logger.info(f"Auditoría de Servicios Pi 5: {audit}")

    # Arrancar tareas de fondo del asistente
    loop.create_task(start_assistant())

    # Iniciar servidor Web HUD con Auto-Switching si el puerto 9090 estuviera ocupado
    host = os.getenv("WEB_HOST", "0.0.0.0")
    requested_port = int(os.getenv("WEB_PORT", 9090))
    port = port_manager.get_available_port(requested_port, fallback_range=15, service_name="WebHUD")

    enable_ssl = os.getenv("ENABLE_SSL", "true").lower() in ("true", "1", "yes")
    cert_file, key_file = (None, None)
    if enable_ssl:
        cert_file, key_file = ssl_mgr.get_ssl_files()

    uvicorn_kwargs = {
        "app": app,
        "host": host,
        "port": port,
        "log_level": "warning",
        "loop": "asyncio"
    }

    if cert_file and key_file:
        uvicorn_kwargs["ssl_keyfile"] = key_file
        uvicorn_kwargs["ssl_certfile"] = cert_file
        logger.info("🔒 [HTTPS] Modo Seguro Activo: Soporte nativo para Micrófono Web y SpeechRecognition.")
        logger.info(f"Dashboard HUD seguro disponible en: https://localhost:{port} (o https://192.168.100.43:{port})")
    else:
        logger.info(f"Dashboard HUD disponible en: http://localhost:{port} (o http://<IP_PI5>:{port})")

    config = uvicorn.Config(**uvicorn_kwargs)
    server = uvicorn.Server(config)

    try:
        loop.run_until_complete(server.serve())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Apagando V.I.E.R.N.E.S. de forma segura...")
        loop.run_until_complete(audio_pipeline.stop())
        loop.run_until_complete(gemini_client.close())


if __name__ == "__main__":
    main()
