"""
Motor de Escenas y Macros Tácticas para V.I.E.R.N.E.S. - MODO FRUTIFANTÁSTICO 🍓🎉
Secuencia de activación:
1. Luces WiZ se configuran al 100% de brillo en modo 'Fiesta' (Scene ID 3) con ciclo dinámico de colores neón intensos.
2. Android TV / Google TV lanza el video musical oficial de The Weeknd ('Blinding Lights').
3. Fallback inteligente: Si la TV está offline o apagada, conecta y reproduce el audio en Google Home Speaker.
4. Ajusta el Aire Acondicionado AIRSYS a 20°C en modo frío para ambiente óptimo.
"""

import asyncio
import logging
from typing import Dict, Any, Optional

from viernes.iot.smart_lights import SmartDeviceController
from viernes.iot.android_tv_cast import cast_controller, THE_WEEKND_TRACKS
from viernes.core.event_bus import bus

logger = logging.getLogger("viernes.macro.party")


class PartyMacroEngine:
    """Motor orquestador del Modo Frutifantástico."""

    def __init__(self):
        self.is_party_active = False
        self._strobe_task: Optional[asyncio.Task] = None

    async def trigger_frutifantastico_mode(
        self,
        light_ip: str = "192.168.100.15",
        tv_ip: str = "192.168.100.25",
        speaker_ip: str = "192.168.100.31",
        ac_ip: str = "192.168.100.20",
        track_key: str = "blinding_lights"
    ) -> Dict[str, Any]:
        """
        Ejecuta la macro completa del 'Modo Frutifantástico':
        - Luces WiZ en Fiesta (colores fuertes, 100% brillo).
        - Video musical The Weeknd en Google TV / Android TV (o Google Home como fallback).
        - Climatización AIRSYS a 20°C.
        """
        logger.info("🍓🎉 [MODO FRUTIFANTÁSTICO ACTIVADO] Iniciando secuencia de fiesta Stark Industries...")
        self.is_party_active = True

        # 1. Configurar luces WiZ al 100% en modo Fiesta (Escena 3 o paleta fiesta)
        light_res = await SmartDeviceController.control_wiz_light(
            light_ip,
            state=True,
            dimming=100,
            scene="party",
            palette="fiesta"
        )

        # 2. Iniciar reproductor de The Weeknd con fallback a Google Home
        media_res = await cast_controller.play_the_weeknd(
            track_key=track_key,
            target_tv_ip=tv_ip,
            target_home_ip=speaker_ip
        )

        # 3. Ajustar Aire Acondicionado AIRSYS a 20°C Frío
        ac_res = await SmartDeviceController.control_air_conditioner(
            ac_ip,
            power=True,
            target_temp=20,
            mode="cool"
        )

        # 4. Publicar evento en el EventBus
        await bus.publish("macro/frutifantastico_activated", {
            "light": light_res,
            "media": media_res,
            "ac": ac_res,
            "status": "PARTY_ACTIVE"
        }, sender="party_engine")

        report = (
            f"🍓 ¡Modo Frutifantástico Activado, Señor! "
            f"Luces WiZ en modo Fiesta al 100%, {media_res.get('message', 'reproduciendo The Weeknd')} "
            f"y Aire Acondicionado climatizado a 20°C."
        )

        return {
            "success": True,
            "mode": "frutifantastico",
            "report": report,
            "light_status": light_res,
            "media_status": media_res,
            "ac_status": ac_res
        }

    async def stop_party_mode(self, light_ip: str = "192.168.100.15", ac_ip: str = "192.168.100.20") -> Dict[str, Any]:
        """Restaura el ambiente normal (Luces en blanco cálido y volumen regular)."""
        logger.info("Restaurando ambiente tras Modo Frutifantástico...")
        self.is_party_active = False

        if self._strobe_task and not self._strobe_task.done():
            self._strobe_task.cancel()

        # Restaurar luz a Cálida (2700K al 80%)
        light_res = await SmartDeviceController.control_wiz_light(
            light_ip,
            state=True,
            dimming=80,
            temp=2700,
            palette="cálida"
        )

        return {
            "success": True,
            "message": "Modo Frutifantástico desactivado. Luces restauradas a Blanco Cálido.",
            "light": light_res
        }


party_engine = PartyMacroEngine()
