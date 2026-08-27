"""
V.I.E.R.N.E.S. - Despachador de Alertas Críticas y Llamadas Salientes Automatizadas
===================================================================================
Gestiona la originación de llamadas de emergencia a números chilenos con:
- Failover multi-carrier automatizado (Zadarma -> Redvoiss -> Twilio CL -> Net2Phone).
- Detección de respuesta y confirmación interactiva por DTMF / Voz.
- Reintentos inteligentes con backoff si el número da ocupado, no contesta o falla.
- Síntesis de voz dinámica y conexión al Core de IA para asistencia en vivo.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging
from typing import Dict, List, Optional

from .ari_client import ARIClient
from .chile_dialplan_validator import ChileDialplanValidator, PhoneNumberType

logger = logging.getLogger("VIERNES.AlertDispatcher")


class AlertPriority(Enum):
    CRITICAL = 1   # Emergencia de vida/seguridad (Reintento inmediato multi-canal)
    HIGH = 2       # Alerta de seguridad hogar / servidor caído
    NORMAL = 3     # Notificación informativa o recordatorio


class AlertCallState(Enum):
    PENDING = "pending"
    DIALING = "dialing"
    RINGING = "ringing"
    ANSWERED = "answered"
    ACKNOWLEDGED = "acknowledged"  # Confirmado por DTMF o voz
    FAILED = "failed"
    COMPLETED = "completed"


@dataclass
class AlertTask:
    alert_id: str
    target_number: str
    message_text: str
    priority: AlertPriority = AlertPriority.HIGH
    max_retries: int = 3
    retry_delay_seconds: int = 30
    current_retry: int = 0
    state: AlertCallState = AlertCallState.PENDING
    carrier_attempt_index: int = 0
    channel_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    acknowledged_at: Optional[datetime] = None
    last_error: Optional[str] = None


class AlertDispatcher:
    """
    Controlador de llamadas salientes de alerta para Chile.
    """

    # Orden de troncales para failover en Chile
    CARRIER_FAILOVER_CHAIN = [
        ("zadarma_endpoint", "Zadarma Chile"),
        ("redvoiss_endpoint", "Redvoiss Chile"),
        ("twilio_endpoint", "Twilio Elastic SIP CL"),
        ("net2phone_endpoint", "Net2Phone Chile"),
    ]

    def __init__(self, ari_client: ARIClient, caller_id_cl: str = "+56912345678"):
        self.ari = ari_client
        self.caller_id_cl = caller_id_cl
        self.alert_queue: asyncio.PriorityQueue[AlertTask] = asyncio.PriorityQueue()
        self.active_alerts: Dict[str, AlertTask] = {}
        self._is_running = False
        self._worker_task: Optional[asyncio.Task] = None

    async def start(self):
        """Inicia el despachador de alertas en segundo plano."""
        self._is_running = True
        self._worker_task = asyncio.create_task(self._process_queue())
        logger.info("🚨 Alert Dispatcher iniciado y listo para originar llamadas en Chile.")

    async def stop(self):
        """Detiene el despachador."""
        self._is_running = False
        if self._worker_task:
            self._worker_task.cancel()

    async def trigger_alert(
        self,
        alert_id: str,
        target_number: str,
        message_text: str,
        priority: AlertPriority = AlertPriority.HIGH,
        max_retries: int = 3,
    ) -> bool:
        """
        Registra y encola una nueva alerta saliente.
        """
        info = ChileDialplanValidator.analyze_number(target_number)
        if not info.is_valid:
            logger.error(f"❌ Número telefónico inválido para alerta: {target_number} ({info.description})")
            return False

        task = AlertTask(
            alert_id=alert_id,
            target_number=info.e164 or target_number,
            message_text=message_text,
            priority=priority,
            max_retries=max_retries,
        )
        self.active_alerts[alert_id] = task
        # El PriorityQueue ordena por tupla (prioridad_int, timestamp)
        await self.alert_queue.put((task.priority.value, datetime.utcnow(), task))
        logger.info(f"🚨 Alerta encolada ID={alert_id} para {task.target_number} (Prioridad: {priority.name})")
        return True

    async def _process_queue(self):
        """Bucle consumidor de la cola de alertas."""
        while self._is_running:
            try:
                _, _, task = await self.alert_queue.get()
                if task.state in (AlertCallState.ACKNOWLEDGED, AlertCallState.COMPLETED):
                    continue

                await self._execute_alert_call(task)
                self.alert_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error procesando cola de alertas: {e}", exc_info=True)
                await asyncio.sleep(1)

    async def _execute_alert_call(self, task: AlertTask):
        """Ejecuta el intento de llamada utilizando la troncal que corresponda en el failover."""
        trunk_endpoint, carrier_name = self.CARRIER_FAILOVER_CHAIN[task.carrier_attempt_index]
        sip_uri = ChileDialplanValidator.to_sip_uri(task.target_number, trunk_endpoint)

        logger.info(f"📞 Marcando alerta {task.alert_id} a {task.target_number} vía {carrier_name} ({sip_uri})...")
        task.state = AlertCallState.DIALING

        # Originar la llamada hacia la aplicación Stasis de V.I.E.R.N.E.S
        app_args = f"alert,{task.alert_id},{task.target_number}"
        variables = {
            "ALERT_ID": task.alert_id,
            "ALERT_TEXT": task.message_text,
            "ALERT_PRIORITY": task.priority.name,
        }

        channel = await self.ari.originate_call(
            endpoint=sip_uri,
            caller_id=self.caller_id_cl,
            app=self.ari.app_name,
            app_args=app_args,
            timeout=40,
            variables=variables,
        )

        if not channel:
            logger.warning(f"⚠️ Falló originación con {carrier_name} para alerta {task.alert_id}.")
            await self._handle_call_failure(task, f"Fallo al originar en {carrier_name}")
        else:
            task.channel_id = channel.get("id")
            logger.info(f"📡 Canal de alerta creado: {task.channel_id} para {task.target_number}")

    async def handle_dtmf_input(self, alert_id: str, digit: str):
        """Maneja las pulsaciones DTMF del usuario durante la llamada de alerta."""
        task = self.active_alerts.get(alert_id)
        if not task:
            return

        logger.info(f"🔢 DTMF recibido en alerta {alert_id}: Dígito '{digit}'")

        if digit == "1":
            # Acusar recibo de la alerta
            task.state = AlertCallState.ACKNOWLEDGED
            task.acknowledged_at = datetime.utcnow()
            logger.info(f"✅ Alerta {alert_id} confirmada exitosamente por el usuario.")
            
            # Reproducir confirmación en el canal si existe
            if task.channel_id:
                await self.ari.play_audio(task.channel_id, "sound:auth-thankyou")
                await asyncio.sleep(2)
                await self.ari.hangup_channel(task.channel_id)

    async def _handle_call_failure(self, task: AlertTask, error_reason: str):
        """Maneja el failover a la siguiente troncal o el reintento programado."""
        task.last_error = error_reason
        # Probar siguiente carrier en la cadena
        if task.carrier_attempt_index + 1 < len(self.CARRIER_FAILOVER_CHAIN):
            task.carrier_attempt_index += 1
            next_carrier = self.CARRIER_FAILOVER_CHAIN[task.carrier_attempt_index][1]
            logger.info(f"🔄 Failover activado para alerta {task.alert_id}. Probando con {next_carrier}...")
            await self.alert_queue.put((task.priority.value, datetime.utcnow(), task))
        else:
            # Se agotaron las troncales en este intento, verificar reintentos globales
            task.carrier_attempt_index = 0
            task.current_retry += 1

            if task.current_retry <= task.max_retries:
                logger.warning(
                    f"⏳ Reintentando alerta {task.alert_id} (Intento {task.current_retry}/{task.max_retries}) "
                    f"en {task.retry_delay_seconds}s..."
                )
                await asyncio.sleep(task.retry_delay_seconds)
                await self.alert_queue.put((task.priority.value, datetime.utcnow(), task))
            else:
                task.state = AlertCallState.FAILED
                logger.error(f"❌ Alerta {task.alert_id} falló definitivamente tras agotar todos los carriers y reintentos.")
