"""
V.I.E.R.N.E.S. - Administrador de Llamadas y Sesiones de Telefonía Inteligente
==============================================================================
Orquesta el ciclo de vida completo de llamadas entrantes y salientes en Asterisk:
- Mapeo de eventos ARI (StasisStart, StasisEnd, ChannelDtmfReceived).
- Enrutamiento de llamadas entrantes al flujo conversacional con IA.
- Gestión de audio bidireccional con AudioSocket y VAD/Barge-in.
- Respuestas inteligentes contextualizadas en español chileno.
"""

import asyncio
from datetime import datetime
from enum import Enum
import logging
from typing import Any, Dict, Optional

from .alert_dispatcher import AlertDispatcher
from .ari_client import ARIClient
from .audiosocket_server import AudioSocketServer, AudioSocketSession
from .chile_dialplan_validator import ChileDialplanValidator, ChileanNumberInfo
from .vad_barge_in import VoiceActivityDetector

logger = logging.getLogger("VIERNES.CallManager")


class CallDirection(Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class CallSessionState(Enum):
    INITIALIZING = "initializing"
    CONNECTED = "connected"
    AI_TALKING = "ai_talking"
    USER_TALKING = "user_talking"
    IDLE = "idle"
    TERMINATED = "terminated"


class ActiveCallSession:
    """Mantiene el estado y contexto de una llamada telefónica individual."""

    def __init__(
        self,
        channel_id: str,
        direction: CallDirection,
        caller_number: str,
        dialed_number: str,
        caller_info: ChileanNumberInfo,
    ):
        self.channel_id = channel_id
        self.direction = direction
        self.caller_number = caller_number
        self.dialed_number = dialed_number
        self.caller_info = caller_info
        self.state = CallSessionState.INITIALIZING
        self.audiosocket_uuid: Optional[str] = None
        self.vad_detector: Optional[VoiceActivityDetector] = None
        self.created_at = datetime.utcnow()
        self.conversation_history: list = []
        self.alert_id: Optional[str] = None

    @property
    def duration_seconds(self) -> float:
        return (datetime.utcnow() - self.created_at).total_seconds()


class CallManager:
    """
    Gestor central de telefonía para V.I.E.R.N.E.S.
    """

    def __init__(
        self,
        ari_client: ARIClient,
        audiosocket_server: AudioSocketServer,
        alert_dispatcher: AlertDispatcher,
        ai_pipeline_handler: Optional[Any] = None,
    ):
        self.ari = ari_client
        self.audiosocket = audiosocket_server
        self.alert_dispatcher = alert_dispatcher
        self.ai_pipeline = ai_pipeline_handler
        self.active_calls: Dict[str, ActiveCallSession] = {}

        # Registrar manejadores de eventos ARI
        self.ari.register_event_handler("StasisStart", self._on_stasis_start)
        self.ari.register_event_handler("StasisEnd", self._on_stasis_end)
        self.ari.register_event_handler("ChannelDtmfReceived", self._on_dtmf_received)
        self.ari.register_event_handler("ChannelHangupRequest", self._on_hangup_request)

    async def _on_stasis_start(self, event: Dict[str, Any]):
        """Invocado cuando un canal ingresa a la aplicación Stasis de Asterisk."""
        channel = event.get("channel", {})
        channel_id = channel.get("id")
        caller_data = channel.get("caller", {})
        dialplan_data = channel.get("dialplan", {})
        args = event.get("args", [])

        caller_num = caller_data.get("number", "Unknown")
        exten = dialplan_data.get("exten", "unknown")
        
        info = ChileDialplanValidator.analyze_number(caller_num)

        logger.info(
            f"📞 [StasisStart] Canal {channel_id} | Desde: {caller_num} ({info.description}) | "
            f"Hacia: {exten} | Args: {args}"
        )

        direction = CallDirection.OUTBOUND if (args and args[0] == "alert") else CallDirection.INBOUND
        session = ActiveCallSession(
            channel_id=channel_id,
            direction=direction,
            caller_number=caller_num,
            dialed_number=exten,
            caller_info=info,
        )

        # Configurar detector VAD con soporte Barge-In
        vad = VoiceActivityDetector(
            on_speech_started=lambda: self._handle_speech_started(channel_id),
            on_speech_ended=lambda: self._handle_speech_ended(channel_id),
            on_barge_in=lambda: self._handle_barge_in(channel_id),
        )
        session.vad_detector = vad
        self.active_calls[channel_id] = session

        if direction == CallDirection.OUTBOUND and len(args) >= 2:
            # Flujo de llamada de alerta
            alert_id = args[1]
            session.alert_id = alert_id
            await self._handle_outbound_alert_session(session, alert_id)
        else:
            # Flujo de llamada entrante convencional
            await self._handle_inbound_call_session(session)

    async def _handle_inbound_call_session(self, session: ActiveCallSession):
        """Gestiona una llamada entrante de un usuario chileno hacia V.I.E.R.N.E.S."""
        channel_id = session.channel_id
        await self.ari.answer_channel(channel_id)
        session.state = CallSessionState.CONNECTED

        # Mensaje de bienvenida inicial en español chileno
        saludo = (
            "Hola. Soy V.I.E.R.N.E.S, tu asistente de inteligencia artificial. "
            "¿En qué te puedo ayudar hoy?"
        )
        logger.info(f"🎙️ V.I.E.R.N.E.S saludando en canal {channel_id}: '{saludo}'")
        
        if self.ai_pipeline and hasattr(self.ai_pipeline, "synthesize_and_stream"):
            session.state = CallSessionState.AI_TALKING
            if session.vad_detector:
                session.vad_detector.set_assistant_speaking(True)
            await self.ai_pipeline.synthesize_and_stream(channel_id, saludo)
            if session.vad_detector:
                session.vad_detector.set_assistant_speaking(False)
            session.state = CallSessionState.IDLE

    async def _handle_outbound_alert_session(self, session: ActiveCallSession, alert_id: str):
        """Gestiona la reproducción interactiva de una alerta."""
        channel_id = session.channel_id
        await self.ari.answer_channel(channel_id)
        session.state = CallSessionState.CONNECTED

        task = self.alert_dispatcher.active_alerts.get(alert_id)
        alert_msg = task.message_text if task else "Alerta de seguridad del sistema V.I.E.R.N.E.S."

        locucion = (
            f"Atención. Esta es una llamada de alerta de V.I.E.R.N.E.S. {alert_msg}. "
            f"Presione 1 en su teclado para confirmar recepción o hable para solicitar más detalles."
        )

        logger.info(f"🚨 Reproduciendo alerta en canal {channel_id}: '{locucion}'")
        if self.ai_pipeline and hasattr(self.ai_pipeline, "synthesize_and_stream"):
            session.state = CallSessionState.AI_TALKING
            await self.ai_pipeline.synthesize_and_stream(channel_id, locucion)
            session.state = CallSessionState.IDLE

    async def _on_dtmf_received(self, event: Dict[str, Any]):
        """Procesa dígitos DTMF marcados por el usuario."""
        channel = event.get("channel", {})
        channel_id = channel.get("id")
        digit = event.get("digit", "")
        session = self.active_calls.get(channel_id)

        if session and session.alert_id:
            await self.alert_dispatcher.handle_dtmf_input(session.alert_id, digit)
        else:
            logger.info(f"🔢 DTMF recibido en canal {channel_id}: '{digit}'")

    async def _on_stasis_end(self, event: Dict[str, Any]):
        """Canal salió de Stasis o colgó."""
        channel = event.get("channel", {})
        channel_id = channel.get("id")
        session = self.active_calls.pop(channel_id, None)

        if session:
            session.state = CallSessionState.TERMINATED
            logger.info(
                f"📴 [StasisEnd] Llamada {channel_id} finalizada. "
                f"Duración: {session.duration_seconds:.1f}s | Desde: {session.caller_number}"
            )

    async def _on_hangup_request(self, event: Dict[str, Any]):
        channel = event.get("channel", {})
        channel_id = channel.get("id")
        logger.debug(f"Petición de colgado en canal {channel_id}")

    def _handle_speech_started(self, channel_id: str):
        session = self.active_calls.get(channel_id)
        if session:
            session.state = CallSessionState.USER_TALKING

    def _handle_speech_ended(self, channel_id: str):
        session = self.active_calls.get(channel_id)
        if session and session.state == CallSessionState.USER_TALKING:
            session.state = CallSessionState.IDLE
            logger.debug(f"Usuario terminó de hablar en canal {channel_id}. Procesando con IA...")

    def _handle_barge_in(self, channel_id: str):
        session = self.active_calls.get(channel_id)
        if session and self.ai_pipeline and hasattr(self.ai_pipeline, "interrupt_playback"):
            logger.info(f"⚡ Ejecutando Barge-In en canal {channel_id}: Silenciando respuesta actual.")
            asyncio.create_task(self.ai_pipeline.interrupt_playback(channel_id))
