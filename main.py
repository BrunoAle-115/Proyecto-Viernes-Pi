"""
Punto de entrada principal para V.I.E.R.N.E.S. (Gemini Multimodal Live Voice Assistant).
"""

import asyncio
import logging
import signal
import sys
from viernes import config
from viernes.live_client import ViernesLiveClient
from viernes.audio_stream import AudioStreamManager

# Configuración de Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("VIERNES.Main")

BANNER = r"""
======================================================================
  __      __   ___  ______  _____   _   _   ______   _____ 
  \ \    / /  |_ _| |  ____||  __ \ | \ | | |  ____| / ____|
   \ \  / /    | |  | |__   | |__) ||  \| | | |__   | (___  
    \ \/ /     | |  |  __|  |  _  / | . ` | |  __|   \___ \ 
     \  /     _| |_ | |____ | | \ \ | |\  | | |____  ____) |
      \/     |_____||______||_|  \_\|_| \_| |______||_____/ 
                                                            
      Voz Inteligente Electrónica Remota y Nodo de Enlace Sensorial
      Potenciado por Gemini 2.0 Flash Multimodal Live API (WebSockets)
======================================================================
"""


def main():
    print(BANNER)
    logger.info("Iniciando subsistemas de V.I.E.R.N.E.S...")
    logger.info(f"Modelo: {config.GEMINI_MODEL} | Voz: {config.VOICE_NAME}")
    logger.info(f"Entrada Audio: {config.AUDIO_INPUT_SAMPLE_RATE} Hz (PCM 16-bit LE)")
    logger.info(f"Salida Audio: {config.AUDIO_OUTPUT_SAMPLE_RATE} Hz (PCM 16-bit LE)")

    audio_manager = AudioStreamManager()
    client = ViernesLiveClient(audio_manager=audio_manager)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def shutdown_handler():
        logger.info("Recibida señal de apagado. Cerrando V.I.E.R.N.E.S de forma segura...")
        loop.create_task(client.close())

    # Registrar señales para apagado limpio en sistemas compatibles
    if sys.platform != "win32":
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, shutdown_handler)

    try:
        loop.run_until_complete(client.run())
    except KeyboardInterrupt:
        logger.info("Interrupción por teclado detectada.")
    finally:
        loop.run_until_complete(client.close())
        loop.close()
        logger.info("V.I.E.R.N.E.S desconectada.")


if __name__ == "__main__":
    main()
