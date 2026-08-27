"""
V.I.E.R.N.E.S. - Entrypoint Principal del Asistente de IA para Raspberry Pi 5.
"""

import os
import sys
import asyncio
import logging
import uvicorn
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
load_dotenv()

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

    # 6. Publicar evento de sistema en línea
    await bus.publish("system/ready", {
        "status": "ONLINE",
        "ip": SystemTelemetry.get_local_ip(),
        "telemetry": SystemTelemetry.get_full_status()
    }, sender="main")

    logger.info("V.I.E.R.N.E.S. completamente en línea y lista para recibir instrucciones.")


def main():
    """Función de arranque."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Arrancar tareas de fondo del asistente
    loop.create_task(start_assistant())

    # Iniciar servidor Web HUD con Uvicorn
    host = os.getenv("WEB_HOST", "0.0.0.0")
    port = int(os.getenv("WEB_PORT", 8080))
    config = uvicorn.Config(app, host=host, port=port, log_level="warning", loop="asyncio")
    server = uvicorn.Server(config)

    logger.info(f"Dashboard HUD disponible en: http://localhost:{port} (o http://<IP_PI5>:{port})")
    try:
        loop.run_until_complete(server.serve())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Apagando V.I.E.R.N.E.S. de forma segura...")
        loop.run_until_complete(audio_pipeline.stop())
        loop.run_until_complete(gemini_client.close())


if __name__ == "__main__":
    main()
