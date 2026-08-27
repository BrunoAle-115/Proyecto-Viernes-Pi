"""
V.I.E.R.N.E.S. - Servicio Central de Telefonía SIP / Asterisk para Chile
========================================================================
Punto de entrada principal del subsistema telefónico.
Conecta Asterisk (ARI/AMI/AudioSocket) con los motores de Inteligencia Artificial:
- Reconocimiento de Voz (STT).
- Modelo de Lenguaje / Asistente V.I.E.R.N.E.S (LLM).
- Síntesis de Voz (TTS) en español chileno.
- Despacho de alertas de emergencia telefónicas en Chile.
"""

import asyncio
import logging
import os
import signal
import sys
from typing import Optional

from .alert_dispatcher import AlertDispatcher, AlertPriority
from .ari_client import ARIClient
from .audiosocket_server import AudioSocketServer, AudioSocketSession
from .call_manager import CallManager
from .chile_dialplan_validator import ChileDialplanValidator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("VIERNES.TelephonyService")


class MockAIPipelineHandler:
    """
    Pipeline de Inteligencia Artificial para V.I.E.R.N.E.S.
    En producción se conecta a OpenAI/Gemini/Local LLM + Whisper STT + Piper/ElevenLabs TTS.
    """

    def __init__(self, audiosocket_server: AudioSocketServer, ari_client: ARIClient):
        self.audiosocket = audiosocket_server
        self.ari = ari_client
        self._interrupted_channels = set()

    async def process_user_speech(self, channel_id: str, transcript_text: str):
        """Procesa la transcripción del usuario con el LLM de V.I.E.R.N.E.S."""
        logger.info(f"🧠 [LLM Input] Canal {channel_id}: '{transcript_text}'")
        
        # Respuesta simulada contextualizada para Chile
        respuesta = (
            f"Entendido. He procesado tu solicitud sobre '{transcript_text}'. "
            f"Los sistemas de monitoreo en Santiago y regiones se encuentran operando con total normalidad."
        )
        await self.synthesize_and_stream(channel_id, respuesta)

    async def synthesize_and_stream(self, channel_id: str, text_to_speak: str):
        """Sintetiza texto a voz y lo transmite al canal telefónico."""
        logger.info(f"🔊 [TTS Output] Canal {channel_id}: '{text_to_speak}'")
        # En Asterisk ARI podemos reproducir tonos, audios precargados o streaming AudioSocket
        # Para demostración de audio en Asterisk:
        await self.ari.play_audio(channel_id, "sound:beep")

    async def interrupt_playback(self, channel_id: str):
        """Detiene de inmediato la salida de audio ante interrupción del usuario (Barge-In)."""
        logger.info(f"🛑 [Barge-In] Cancelando reproducción activa en canal {channel_id}")
        self._interrupted_channels.add(channel_id)


class ViernesTelephonyService:
    """
    Servicio de control y orquestación telefónica V.I.E.R.N.E.S.
    """

    def __init__(
        self,
        ari_url: str = os.getenv("ARI_URL", "http://127.0.0.1:8088/ari"),
        ari_ws_url: str = os.getenv("ARI_WS_URL", "ws://127.0.0.1:8088/ari/events"),
        ari_user: str = os.getenv("ARI_USER", "viernes-ari-user"),
        ari_password: str = os.getenv("ARI_PASSWORD", "ViernesSecretPass2026"),
        audiosocket_port: int = int(os.getenv("AUDIOSOCKET_PORT", "9099")),
        caller_id_cl: str = os.getenv("CALLER_ID_CL", "+56912345678"),
    ):
        self.ari = ARIClient(
            base_url=ari_url,
            ws_url=ari_ws_url,
            username=ari_user,
            password=ari_password,
            app_name="viernes-voice",
        )
        self.audiosocket = AudioSocketServer(
            host="0.0.0.0",
            port=audiosocket_port,
            on_session_start=self._on_audio_session_start,
            on_audio_received=self._on_audio_chunk_received,
            on_session_end=self._on_audio_session_end,
        )
        self.alert_dispatcher = AlertDispatcher(self.ari, caller_id_cl=caller_id_cl)
        self.ai_pipeline = MockAIPipelineHandler(self.audiosocket, self.ari)
        self.call_manager = CallManager(
            ari_client=self.ari,
            audiosocket_server=self.audiosocket,
            alert_dispatcher=self.alert_dispatcher,
            ai_pipeline_handler=self.ai_pipeline,
        )
        self._is_running = False

    async def _on_audio_session_start(self, session: AudioSocketSession):
        logger.info(f"🎙️ Sesión AudioSocket en vivo establecida: {session.session_uuid}")

    async def _on_audio_chunk_received(self, session_uuid: str, pcm_data: bytes):
        """Recepción de paquetes PCM 16-bit desde Asterisk para VAD y STT."""
        # Se envía al VAD activo de la llamada correspondiente
        pass

    async def _on_audio_session_end(self, session_uuid: str):
        logger.info(f"🎙️ Sesión AudioSocket finalizada: {session_uuid}")

    async def start(self):
        """Inicializa todos los servicios asíncronos."""
        logger.info("=======================================================")
        logger.info("   INICIANDO SISTEMA DE TELEFONÍA SIP V.I.E.R.N.E.S    ")
        logger.info("   Región: Chile (+56) | Troncales: Zadarma/Redvoiss/Twilio/Net2Phone")
        logger.info("=======================================================")

        self._is_running = True
        await self.audiosocket.start()
        await self.ari.start()
        await self.alert_dispatcher.start()
        logger.info("✅ Todos los subsistemas telefónicos inicializados correctamente.")

    async def stop(self):
        """Detención ordenada de servicios."""
        logger.info("Deteniendo servicios de telefonía V.I.E.R.N.E.S...")
        self._is_running = False
        await self.alert_dispatcher.stop()
        await self.ari.stop()
        await self.audiosocket.stop()
        logger.info("👋 Subsistema telefónico detenido con éxito.")

    async def send_emergency_alert(self, target_number: str, alert_message: str, priority: AlertPriority = AlertPriority.HIGH) -> bool:
        """API de alto nivel para disparar una llamada de alerta telefónica en Chile."""
        alert_id = f"alert-{os.urandom(4).hex()}"
        return await self.alert_dispatcher.trigger_alert(
            alert_id=alert_id,
            target_number=target_number,
            message_text=alert_message,
            priority=priority,
        )


async def main():
    service = ViernesTelephonyService()
    await service.start()

    # Mantener el servicio corriendo
    stop_event = asyncio.Event()

    def _signal_handler():
        logger.info("Señal de interrupción recibida.")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:
            # Soporte en Windows
            pass

    try:
        await stop_event.wait()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        await service.stop()


if __name__ == "__main__":
    asyncio.run(main())
