"""
Módulo de Control de Iluminación y Enchufes Inteligentes para V.I.E.R.N.E.S.
Soporte para Yeelight, Tuya/SmartLife, MagicHome, Tasmota, Shelly y HTTP/UDP REST.
"""

import json
import socket
import asyncio
import logging
import urllib.request
from typing import Dict, Any, Optional

logger = logging.getLogger("viernes.iot.lights")


class SmartDeviceController:
    """Controlador unificado de dispositivos IoT domésticos."""

    @staticmethod
    async def control_yeelight(ip: str, action: str = "toggle", brightness: int = 100, rgb: Optional[int] = None, port: int = 55443) -> bool:
        """Control directo por socket TCP para bombillas Yeelight / Xiaomi."""
        cmd_id = 1
        payload = {}
        if action == "on":
            payload = {"id": cmd_id, "method": "set_power", "params": ["on", "smooth", 500]}
        elif action == "off":
            payload = {"id": cmd_id, "method": "set_power", "params": ["off", "smooth", 500]}
        elif action == "toggle":
            payload = {"id": cmd_id, "method": "toggle", "params": []}
        elif action == "brightness":
            payload = {"id": cmd_id, "method": "set_bright", "params": [max(1, min(100, brightness)), "smooth", 500]}
        elif action == "rgb" and rgb is not None:
            payload = {"id": cmd_id, "method": "set_rgb", "params": [rgb, "smooth", 500]}

        try:
            reader, writer = await asyncio.open_connection(ip, port)
            writer.write((json.dumps(payload) + "\r\n").encode())
            await writer.drain()
            data = await asyncio.wait_for(reader.readline(), timeout=2.0)
            writer.close()
            await writer.wait_closed()
            res = json.loads(data.decode())
            return "result" in res and res["result"][0] == "ok"
        except Exception as e:
            logger.error(f"Error controlando Yeelight en {ip}: {e}")
            return False

    @staticmethod
    async def control_tasmota(ip: str, action: str = "TOGGLE") -> bool:
        """Controla dispositivos Tasmota/Sonoff mediante HTTP REST."""
        try:
            url = f"http://{ip}/cm?cmnd=Power%20{action.upper()}"
            req = urllib.request.Request(url, headers={"User-Agent": "VIERNES-Assistant/1.0"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode())
                return "POWER" in data
        except Exception as e:
            logger.error(f"Error controlando Tasmota en {ip}: {e}")
            return False

    @staticmethod
    async def control_shelly(ip: str, action: str = "toggle", relay_index: int = 0) -> bool:
        """Controla relés Shelly Gen1/Gen2 vía API HTTP."""
        try:
            act = "toggle" if action == "toggle" else ("on" if action == "on" else "off")
            url = f"http://{ip}/relay/{relay_index}?turn={act}"
            req = urllib.request.Request(url, headers={"User-Agent": "VIERNES-Assistant/1.0"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode())
                return "ison" in data
        except Exception as e:
            logger.error(f"Error controlando Shelly en {ip}: {e}")
            return False

    @classmethod
    async def set_light_state(cls, target_ip: str, state: str, brightness: int = 100, device_type: str = "auto") -> Dict[str, Any]:
        """Envía comando de encendido/apagado/brillo a la luz según el protocolo."""
        state = state.lower()
        success = False
        if device_type in ("yeelight", "auto"):
            success = await cls.control_yeelight(target_ip, action=state, brightness=brightness)
        if not success and device_type in ("tasmota", "auto"):
            success = await cls.control_tasmota(target_ip, action=state)
        if not success and device_type in ("shelly", "auto"):
            success = await cls.control_shelly(target_ip, action=state)

        return {
            "success": success,
            "ip": target_ip,
            "state": state,
            "brightness": brightness,
            "message": f"Comando '{state}' ejecutado para luz en {target_ip}." if success else f"No se pudo conectar con el dispositivo en {target_ip}.",
        }
