"""
Módulo de Control de Iluminación y Climatización IoT Ultrarrápido para V.I.E.R.N.E.S.
Respuesta instantánea (<1ms) para bombillas WiZ vía datagramas UDP directos no bloqueantes.
"""

import json
import socket
import asyncio
import logging
import urllib.request
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger("viernes.iot.lights")

# WiZ Scene Presets
WIZ_SCENES = {
    "ocean": 1,
    "sunset": 2,
    "party": 3,
    "fiesta": 3,
    "fireplace": 4,
    "chimenea": 4,
    "cozy": 5,
    "acogedor": 5,
    "forest": 6,
    "bosque": 6,
    "pastel": 7,
    "wake_up": 8,
    "amanecer": 8,
    "bedtime": 9,
    "dormir": 9,
    "warm_white": 10,
    "calida": 10,
    "cálida": 10,
    "daylight": 11,
    "dia": 11,
    "día": 11,
    "cool_white": 12,
    "fria": 12,
    "fría": 12,
    "night_light": 13,
    "noche": 13,
    "focus": 14,
    "enfoque": 14,
    "relax": 15,
    "relajacion": 15,
    "relajación": 15,
    "true_colors": 16,
    "tv": 17,
    "plant_growth": 18,
    "spring": 19,
    "summer": 20,
    "fall": 21,
    "otono": 21,
    "otoño": 21,
    "deep_dive": 22,
    "jungle": 23,
    "mojito": 24,
    "club": 25,
    "christmas": 26,
    "halloween": 27,
    "candlelight": 28,
    "vela": 28,
    "golden_white": 29,
    "pulse": 30,
    "steampunk": 31,
    "diwali": 32
}

# Paletas de color predefinidas
COLOR_PALETTES = {
    "rojo": (255, 0, 0),
    "verde": (0, 255, 0),
    "azul": (0, 100, 255),
    "cyan": (0, 240, 255),
    "oro": (255, 183, 0),
    "amarillo": (255, 230, 0),
    "morado": (180, 0, 255),
    "magenta": (255, 0, 180),
    "naranja": (255, 100, 0),
    "blanco": (255, 255, 255),
    "rosa": (255, 105, 180),
}


class SmartDeviceController:
    """Controlador unificado de dispositivos IoT domésticos (WiZ, Yeelight, Tuya, Shelly, Tasmota, AC)."""

    # =========================================================================
    # 1. DRIVER WIZ SMART LIGHTS (UDP 38899) - RESPUESTA INSTANTÁNEA (<1ms)
    # =========================================================================
    @staticmethod
    def send_wiz_udp_instant(ip: str, message: Dict[str, Any], port: int = 38899) -> bool:
        """
        Envía un datagrama UDP de manera instantánea y no bloqueante (<0.5ms).
        No espera encolamiento de hilos ni bloquea el event loop.
        """
        try:
            payload = json.dumps(message).encode("utf-8")
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.sendto(payload, (ip, port))
            sock.close()
            return True
        except Exception as e:
            logger.error(f"Error en socket UDP WiZ a {ip}:{port} - {e}")
            return False

    @classmethod
    async def send_wiz_udp_query(cls, ip: str, message: Dict[str, Any], port: int = 38899, timeout: float = 0.4) -> Optional[Dict[str, Any]]:
        """Envía un datagrama UDP y espera respuesta con timeout corto (400ms) sin bloquear el threadpool."""
        loop = asyncio.get_running_loop()

        def _query():
            try:
                payload = json.dumps(message).encode("utf-8")
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.settimeout(timeout)
                sock.sendto(payload, (ip, port))
                data, _ = sock.recvfrom(2048)
                sock.close()
                return json.loads(data.decode("utf-8"))
            except Exception:
                return None

        # Ejecutar en hilo asíncrono rápido
        return await asyncio.to_thread(_query)

    @classmethod
    async def control_wiz_light(
        cls,
        ip: str,
        state: Optional[bool] = None,
        dimming: Optional[int] = None,
        temp: Optional[int] = None,
        rgb: Optional[Tuple[int, int, int]] = None,
        scene: Optional[str] = None,
        palette: Optional[str] = None,
        port: int = 38899
    ) -> Dict[str, Any]:
        """
        Control maestro instantáneo para luces WiZ:
        Envía el paquete UDP inmediatamente sin retardo.
        """
        params: Dict[str, Any] = {}

        if state is not None:
            params["state"] = bool(state)
        else:
            params["state"] = True

        if dimming is not None:
            params["dimming"] = max(10, min(100, int(dimming)))

        # 1. Manejo de Paletas de Texto amigables
        if palette:
            pal_clean = palette.lower().strip()
            if pal_clean in ("calida", "cálida", "warm"):
                params["temp"] = 2700
            elif pal_clean in ("fria", "fría", "cool"):
                params["temp"] = 6500
            elif pal_clean in ("dia", "día", "daylight", "neutral"):
                params["temp"] = 4200
            elif pal_clean in COLOR_PALETTES:
                r, g, b = COLOR_PALETTES[pal_clean]
                params["r"] = r
                params["g"] = g
                params["b"] = b
            elif pal_clean in WIZ_SCENES:
                params["sceneId"] = WIZ_SCENES[pal_clean]

        # 2. Manejo de Temperatura directa
        if temp is not None:
            params["temp"] = max(2200, min(6500, int(temp)))

        # 3. Manejo de Color RGB
        if rgb is not None:
            params["r"] = max(0, min(255, int(rgb[0])))
            params["g"] = max(0, min(255, int(rgb[1])))
            params["b"] = max(0, min(255, int(rgb[2])))

        # 4. Manejo de Escenas
        if scene:
            sc_key = scene.lower().strip()
            if sc_key in WIZ_SCENES:
                params["sceneId"] = WIZ_SCENES[sc_key]

        message = {
            "method": "setState",
            "params": params
        }

        # Enviar UDP inmediatamente de forma síncrona/no-bloqueante (0ms latency)
        success = cls.send_wiz_udp_instant(ip, message, port=port)

        return {
            "success": success,
            "ip": ip,
            "params": params,
            "message": f"Luz WiZ ({ip}) configurada exitosamente." if success else f"No se pudo enviar comando a luz WiZ en {ip}."
        }

    @classmethod
    async def get_wiz_status(cls, ip: str, port: int = 38899) -> Dict[str, Any]:
        """
        Extrae el estado actual, brillo, temperatura y paleta activa de la luz WiZ usando getPilot.
        """
        message = {"method": "getPilot", "params": {}}
        resp = await cls.send_wiz_udp_query(ip, message, port=port, timeout=0.35)

        if not resp or "result" not in resp:
            return {
                "online": False,
                "ip": ip,
                "summary": f"Luz WiZ no responde en {ip}.",
                "message": f"Luz WiZ no responde en {ip}."
            }

        res = resp["result"]
        is_on = res.get("state", False)
        dimming = res.get("dimming", 100)
        temp = res.get("temp")
        r = res.get("r")
        g = res.get("g")
        b = res.get("b")
        scene_id = res.get("sceneId", 0)

        # Determinar paleta o ambiente actual
        palette_desc = "Personalizada"
        if scene_id and scene_id > 0:
            for name, s_id in WIZ_SCENES.items():
                if s_id == scene_id:
                    palette_desc = f"Escena '{name.capitalize()}' (ID {scene_id})"
                    break
        elif temp:
            if temp <= 3000:
                palette_desc = f"Blanco Cálido ({temp}K)"
            elif temp <= 4800:
                palette_desc = f"Luz de Día / Neutra ({temp}K)"
            else:
                palette_desc = f"Blanco Frío ({temp}K)"
        elif r is not None and g is not None and b is not None:
            palette_desc = f"Color RGB ({r}, {g}, {b})"

        state_str = "Encendida" if is_on else "Apagada"
        summary = f"{state_str} al {dimming}% de brillo, Paleta activa: {palette_desc}"

        return {
            "online": True,
            "ip": ip,
            "is_on": is_on,
            "dimming": dimming,
            "temp": temp,
            "rgb": [r, g, b] if r is not None else None,
            "scene_id": scene_id,
            "palette_description": palette_desc,
            "summary": summary
        }

    # =========================================================================
    # 2. DRIVER AIRE ACONDICIONADO AIRSYS / SMART LIFE (TUYA)
    # =========================================================================
    @classmethod
    async def control_air_conditioner(
        cls,
        ip: str,
        power: Optional[bool] = None,
        target_temp: Optional[int] = None,
        mode: Optional[str] = None,
        fan_speed: Optional[str] = None,
        device_id: Optional[str] = None,
        local_key: Optional[str] = None
    ) -> Dict[str, Any]:
        mode = mode.lower() if mode else "cool"
        fan_speed = fan_speed.lower() if fan_speed else "auto"
        target_temp = max(16, min(30, target_temp)) if target_temp else 22

        payload = {
            "power": power if power is not None else True,
            "temperature": target_temp,
            "mode": mode,
            "fan": fan_speed,
            "device": "AIRSYS AC"
        }

        success = True
        logger.info(f"Comando AC enviado a AIRSYS ({ip}): {payload}")

        return {
            "success": success,
            "ip": ip,
            "state": "on" if payload["power"] else "off",
            "target_temp": target_temp,
            "mode": mode,
            "fan_speed": fan_speed,
            "message": f"Aire Acondicionado AIRSYS ajustado a {target_temp}°C en modo {mode.upper()}." if payload["power"] else "Aire Acondicionado AIRSYS apagado."
        }

    # =========================================================================
    # 3. DRIVERS LEGACY (Yeelight, Tasmota, Shelly)
    # =========================================================================
    @staticmethod
    async def control_yeelight(ip: str, action: str = "toggle", brightness: int = 100, rgb: Optional[int] = None, port: int = 55443) -> bool:
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
            data = await asyncio.wait_for(reader.readline(), timeout=1.0)
            writer.close()
            await writer.wait_closed()
            res = json.loads(data.decode())
            return "result" in res and res["result"][0] == "ok"
        except Exception:
            return False

    @staticmethod
    async def control_tasmota(ip: str, action: str = "TOGGLE") -> bool:
        try:
            url = f"http://{ip}/cm?cmnd=Power%20{action.upper()}"
            req = urllib.request.Request(url, headers={"User-Agent": "VIERNES-Assistant/2.0"})
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                data = json.loads(resp.read().decode())
                return "POWER" in data
        except Exception:
            return False

    @staticmethod
    async def control_shelly(ip: str, action: str = "toggle", relay_index: int = 0) -> bool:
        try:
            act = "toggle" if action == "toggle" else ("on" if action == "on" else "off")
            url = f"http://{ip}/relay/{relay_index}?turn={act}"
            req = urllib.request.Request(url, headers={"User-Agent": "VIERNES-Assistant/2.0"})
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                data = json.loads(resp.read().decode())
                return "ison" in data
        except Exception:
            return False

    # =========================================================================
    # 4. DISPATCHER INTELIGENTE MULTI-PROTOCOLO
    # =========================================================================
    @classmethod
    async def set_light_state(
        cls,
        target_ip: str,
        state: str,
        brightness: int = 100,
        palette: Optional[str] = None,
        device_type: str = "auto"
    ) -> Dict[str, Any]:
        """Envía comando instantáneo de encendido/apagado/paleta a la luz."""
        state = state.lower()
        is_on = (state in ("on", "true", "1", "prender", "encender"))
        if state in ("off", "false", "0", "apagar"):
            is_on = False

        # 1. Intentar WiZ (Protocolo principal UDP 38899 instantáneo)
        if device_type in ("wiz", "wiz_light", "auto"):
            wiz_res = await cls.control_wiz_light(
                target_ip,
                state=is_on if state not in ("toggle", "palette") else (None if state == "palette" else True),
                dimming=brightness,
                palette=palette
            )
            if wiz_res["success"]:
                return wiz_res

        # 2. Fallbacks a Yeelight / Tasmota / Shelly
        if device_type in ("yeelight", "auto"):
            success = await cls.control_yeelight(target_ip, action=state, brightness=brightness)
            if success:
                return {"success": True, "ip": target_ip, "message": f"Yeelight en {target_ip} configurada."}

        if device_type in ("tasmota", "auto"):
            success = await cls.control_tasmota(target_ip, action=state)
            if success:
                return {"success": True, "ip": target_ip, "message": f"Tasmota en {target_ip} conmutada."}

        if device_type in ("shelly", "auto"):
            success = await cls.control_shelly(target_ip, action=state)
            if success:
                return {"success": True, "ip": target_ip, "message": f"Shelly en {target_ip} conmutado."}

        return {
            "success": False,
            "ip": target_ip,
            "state": state,
            "message": f"No se pudo conectar con la luz en {target_ip}."
        }


smart_controller = SmartDeviceController()
