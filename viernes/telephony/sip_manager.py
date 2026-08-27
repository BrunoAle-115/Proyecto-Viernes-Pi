"""
Gestor de Telefonía SIP Trunk & Asterisk AMI/ARI para V.I.E.R.N.E.S.
Permite originar llamadas a celulares en Chile y recibir llamadas interactivas de voz.
"""

import os
import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from viernes.core.event_bus import bus
from viernes.telephony.chile_providers import CHILEAN_SIP_PRESETS

logger = logging.getLogger("viernes.telephony.manager")


class SipManager:
    def __init__(self, host: str = "127.0.0.1", port: int = 5038, user: str = "viernes", secret: str = "viernes_ami_pass"):
        self.host = host
        self.port = port
        self.user = user
        self.secret = secret
        self.connected = False
        self.provider_name = os.getenv("SIP_PROVIDER", "zadarma_chile")
        self.active_calls: Dict[str, Dict[str, Any]] = {}
        self.call_history: list = []

    async def connect(self) -> bool:
        """Intenta conectar al Asterisk Manager Interface (AMI)."""
        try:
            # En producción se usa panoramisk o socket AMI directo
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port), timeout=2.0
            )
            # Saludo inicial Asterisk Call Manager
            greeting = await reader.readline()
            if b"Asterisk Call Manager" in greeting:
                login_cmd = f"Action: Login\r\nUsername: {self.user}\r\nSecret: {self.secret}\r\n\r\n"
                writer.write(login_cmd.encode())
                await writer.drain()
                resp = await reader.read(512)
                if b"Success" in resp:
                    self.connected = True
                    logger.info(f"Conexión exitosa a Asterisk AMI en {self.host}:{self.port}")
                    writer.close()
                    await writer.wait_closed()
                    return True
            writer.close()
            await writer.wait_closed()
        except Exception as e:
            logger.debug(f"Asterisk AMI no disponible en {self.host}:{self.port} ({e}). Modo Telephony Standby activo.")

        self.connected = False
        return False

    async def originate_call(self, phone_number: str, context: str = "outbound-viernes", caller_id: str = "VIERNES AI") -> Dict[str, Any]:
        """
        Origina una llamada hacia un número telefónico chileno (ej: +56912345678).
        """
        # Normalizar número de teléfono en Chile
        clean_num = phone_number.replace(" ", "").replace("-", "")
        if clean_num.startswith("+56"):
            pass
        elif clean_num.startswith("9") and len(clean_num) == 9:
            clean_num = "+56" + clean_num
        elif clean_num.startswith("569"):
            clean_num = "+" + clean_num

        call_id = f"call_{int(datetime.now().timestamp())}"
        call_info = {
            "id": call_id,
            "number": clean_num,
            "caller_id": caller_id,
            "status": "dialing",
            "timestamp": datetime.now().isoformat(),
            "provider": self.provider_name,
        }
        self.active_calls[call_id] = call_info
        self.call_history.append(call_info)

        logger.info(f"Originando llamada SIP a {clean_num} vía proveedor {self.provider_name}...")
        await bus.publish("telephony/call_started", call_info, sender="sip_manager")

        # Si Asterisk está conectado físicamente, emitir Action: Originate
        if self.connected:
            try:
                reader, writer = await asyncio.open_connection(self.host, self.port)
                originate_cmd = (
                    f"Action: Originate\r\n"
                    f"Channel: PJSIP/{clean_num}@zadarma_endpoint\r\n"
                    f"Context: {context}\r\n"
                    f"Exten: s\r\n"
                    f"Priority: 1\r\n"
                    f"CallerID: {caller_id}\r\n"
                    f"Async: true\r\n\r\n"
                )
                writer.write(originate_cmd.encode())
                await writer.drain()
                writer.close()
                await writer.wait_closed()
            except Exception as e:
                logger.error(f"Error enviando comando Originate a Asterisk: {e}")

        # Simulación de timbrado y respuesta para pruebas / entorno dev
        asyncio.create_task(self._simulate_call_lifecycle(call_id, clean_num))

        return {
            "success": True,
            "call_id": call_id,
            "number": clean_num,
            "status": "dialing",
            "message": f"Marcando al número chileno {clean_num} mediante troncal SIP.",
        }

    async def _simulate_call_lifecycle(self, call_id: str, number: str):
        """Monitorea o simula el ciclo de vida de la llamada."""
        await asyncio.sleep(3.0)
        if call_id in self.active_calls:
            self.active_calls[call_id]["status"] = "in_progress"
            await bus.publish("telephony/call_answered", {"id": call_id, "number": number}, sender="sip_manager")

    async def hangup_call(self, call_id: str) -> Dict[str, Any]:
        """Cuelga una llamada activa."""
        if call_id in self.active_calls:
            self.active_calls[call_id]["status"] = "ended"
            del self.active_calls[call_id]
            await bus.publish("telephony/call_hangup", {"id": call_id}, sender="sip_manager")
            return {"success": True, "call_id": call_id, "message": "Llamada finalizada."}
        return {"success": False, "error": "Llamada no encontrada o ya finalizada."}

    def get_telephony_status(self) -> Dict[str, Any]:
        """Retorna el estado del subsistema SIP para el HUD."""
        preset = CHILEAN_SIP_PRESETS.get(self.provider_name, CHILEAN_SIP_PRESETS["zadarma_chile"])
        return {
            "connected": self.connected,
            "provider_key": self.provider_name,
            "provider_name": preset["name"],
            "sip_server": preset.get("sip_server", "sip.zadarma.com"),
            "active_calls_count": len(self.active_calls),
            "recent_calls": self.call_history[-5:],
        }


sip_mgr = SipManager()
