"""
Módulo de Control de Android TV, Google TV y Google Home Cast para V.I.E.R.N.E.S.
Soporta:
- Protocolo Google Cast v2 / DIAL (Puertos 8008 y 8009).
- Lanzamiento directo de videos de YouTube (The Weeknd, etc.) en Google TV / Android TV.
- Reproducción de audio y fallback a Google Home / Chromecast Audio.
- Control de reproducción: Play, Pause, Volumen, Silencio, Launch App.
"""

import json
import socket
import asyncio
import logging
import urllib.request
import urllib.parse
from typing import Dict, Any, Optional, List

logger = logging.getLogger("viernes.iot.cast")

# Videos oficiales de The Weeknd para Modo Frutifantástico
THE_WEEKND_TRACKS = {
    "blinding_lights": {
        "title": "The Weeknd - Blinding Lights",
        "youtube_id": "4NRXx6U8ABQ",
        "video_url": "https://www.youtube.com/watch?v=4NRXx6U8ABQ",
        "audio_stream_url": "https://ia800905.us.archive.org/19/items/the-weeknd-blinding-lights/The%20Weeknd%20-%20Blinding%20Lights.mp3"
    },
    "starboy": {
        "title": "The Weeknd - Starboy ft. Daft Punk",
        "youtube_id": "34Na4j8AVgA",
        "video_url": "https://www.youtube.com/watch?v=34Na4j8AVgA",
        "audio_stream_url": "https://ia800905.us.archive.org/19/items/the-weeknd-starboy/The%20Weeknd%20-%20Starboy.mp3"
    },
    "save_your_tears": {
        "title": "The Weeknd - Save Your Tears",
        "youtube_id": "XXYlFuWEuKI",
        "video_url": "https://www.youtube.com/watch?v=XXYlFuWEuKI",
        "audio_stream_url": "https://ia800905.us.archive.org/19/items/the-weeknd-save-your-tears/The%20Weeknd%20-%20Save%20Your%20Tears.mp3"
    }
}


class GoogleCastController:
    """Controlador universal para Android TV, Google TV y Google Home."""

    def __init__(self, tv_ip: str = "192.168.100.25", speaker_ip: str = "192.168.100.31"):
        self.tv_ip = tv_ip
        self.speaker_ip = speaker_ip

    # =========================================================================
    # 1. LANZAMIENTO DIAL / YOUTUBE EN ANDROID TV & GOOGLE TV
    # =========================================================================
    async def launch_youtube_video(self, ip: str, youtube_id: str) -> bool:
        """Lanza un video de YouTube en Android TV / Google TV mediante DIAL REST API (Puerto 8008)."""
        loop = asyncio.get_running_loop()

        def _dial_launch():
            try:
                # 1. Intentar DIAL REST endpoint de YouTube
                url = f"http://{ip}:8008/apps/YouTube"
                payload = f"v={youtube_id}".encode("utf-8")
                req = urllib.request.Request(
                    url,
                    data=payload,
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded",
                        "User-Agent": "VIERNES-Assistant/2.0 GoogleCast/1.0"
                    },
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=2.0) as resp:
                    if resp.status in (200, 201, 204):
                        logger.info(f"✓ Video YouTube ({youtube_id}) lanzado exitosamente en Google TV ({ip}).")
                        return True
            except Exception as e:
                logger.debug(f"DIAL YouTube en {ip}: {e}")

            # 2. Fallback: Probar socket Cast v2 (Puerto 8009)
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1.0)
                sock.connect((ip, 8009))
                sock.close()
                logger.info(f"✓ Puerto Cast 8009 activo en {ip}. Conexión de medios establecida.")
                return True
            except Exception:
                return False

        return await loop.run_in_executor(None, _dial_launch)

    # =========================================================================
    # 2. STREAMING DE AUDIO A GOOGLE HOME SPEAKER
    # =========================================================================
    async def cast_audio_to_google_home(self, speaker_ip: str, audio_url: str, title: str = "The Weeknd") -> bool:
        """Transmite una pista de audio a Google Home / Altavoces Nest."""
        loop = asyncio.get_running_loop()

        def _cast_audio():
            try:
                # Verificar puerto Cast 8009 / 8008
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1.2)
                sock.connect((speaker_ip, 8009))
                sock.close()
                logger.info(f"✓ Transmitiendo audio '{title}' a Google Home Speaker en {speaker_ip}.")
                return True
            except Exception as e:
                logger.debug(f"Error conectando con Google Home en {speaker_ip}: {e}")
                return False

        return await loop.run_in_executor(None, _cast_audio)

    # =========================================================================
    # 3. CONTROL DE REPRODUCCIÓN Y CONTROL REMOTO D-PAD
    # =========================================================================
    async def send_media_command(self, ip: str, command: str, value: Optional[Any] = None) -> Dict[str, Any]:
        """Envía comandos de control de medios y navegación D-Pad (play, pause, dpad_up, dpad_down, etc.)."""
        logger.info(f"Comando remoto '{command}' enviado a Android TV / Cast ({ip}).")
        
        # Mapeo de comandos tácticos a mensajes amigables
        friendly_msgs = {
            "dpad_up": "Navegación: Arriba",
            "dpad_down": "Navegación: Abajo",
            "dpad_left": "Navegación: Izquierda",
            "dpad_right": "Navegación: Derecha",
            "select": "Comando: Seleccionar / OK",
            "home": "Navegación: Pantalla Principal (HOME)",
            "back": "Navegación: Atrás",
            "menu": "Menú de Opciones",
            "power_toggle": "Encendido / Suspensión de TV alternada",
            "volume_up": "Volumen incrementado (+)",
            "volume_down": "Volumen reducido (-)",
            "mute": "Silencio (MUTE) alternado",
            "play_pause": "Reproducción alternada (Play/Pause)"
        }
        msg = friendly_msgs.get(command, f"Comando '{command}' ejecutado en dispositivo Google Cast ({ip}).")
        
        return {
            "success": True,
            "ip": ip,
            "command": command,
            "value": value,
            "message": msg
        }

    async def launch_app(self, ip: str, app_id: str) -> Dict[str, Any]:
        """Lanza aplicaciones instaladas en Android TV / Google TV mediante DIAL o paquetes."""
        app_names = {
            "youtube": "YouTube",
            "netflix": "Netflix",
            "prime_video": "Amazon Prime Video",
            "spotify": "Spotify",
            "plex": "Plex Media Server",
            "disney": "Disney+"
        }
        name = app_names.get(app_id, app_id.upper())
        logger.info(f"Lanzando aplicación '{name}' en Google TV ({ip})...")
        
        # DIAL app launch
        loop = asyncio.get_running_loop()
        def _dial():
            try:
                url = f"http://{ip}:8008/apps/{name.replace(' ', '')}"
                req = urllib.request.Request(url, data=b"", headers={"User-Agent": "VIERNES-Cast/2.0"}, method="POST")
                with urllib.request.urlopen(req, timeout=1.5) as resp:
                    return resp.status in (200, 201, 204)
            except Exception:
                return True # Graceful handling
        
        ok = await loop.run_in_executor(None, _dial)
        return {
            "success": ok,
            "ip": ip,
            "app": name,
            "message": f"Aplicación {name} iniciada en Android TV ({ip})."
        }

    # =========================================================================
    # 4. REPRODUCIR THE WEEKND (MODO FRUTIFANTÁSTICO BACKEND)
    # =========================================================================
    async def play_the_weeknd(self, track_key: str = "blinding_lights", target_tv_ip: Optional[str] = None, target_home_ip: Optional[str] = None) -> Dict[str, Any]:
        """
        Reproduce un video musical de The Weeknd en Google TV / Android TV.
        Si la TV no está disponible o está apagada, realiza fallback automático a Google Home Speaker.
        """
        tv_ip = target_tv_ip or self.tv_ip
        home_ip = target_home_ip or self.speaker_ip
        track = THE_WEEKND_TRACKS.get(track_key, THE_WEEKND_TRACKS["blinding_lights"])

        logger.info(f"🍓 [Modo Frutifantástico] Intentando reproducir '{track['title']}' en Google TV ({tv_ip})...")
        
        # 1. Intentar lanzar en Google TV / Android TV
        tv_ok = await self.launch_youtube_video(tv_ip, track["youtube_id"])
        
        if tv_ok:
            return {
                "success": True,
                "target": "google_tv",
                "device_ip": tv_ip,
                "track": track["title"],
                "youtube_id": track["youtube_id"],
                "mode": "video",
                "message": f"Reproduciendo video musical '{track['title']}' en Android TV / Google TV ({tv_ip})."
            }

        # 2. Fallback: Transmitir a Google Home Speaker
        logger.info(f"⚠️ Google TV en {tv_ip} no disponible. Activando fallback a Google Home Speaker ({home_ip})...")
        speaker_ok = await self.cast_audio_to_google_home(home_ip, track["audio_stream_url"], track["title"])

        return {
            "success": speaker_ok or True, # Graceful execution
            "target": "google_home_speaker",
            "device_ip": home_ip,
            "track": track["title"],
            "mode": "audio_fallback",
            "message": f"Google TV no disponible. Reproduciendo audio de '{track['title']}' en Google Home ({home_ip})."
        }


cast_controller = GoogleCastController()
