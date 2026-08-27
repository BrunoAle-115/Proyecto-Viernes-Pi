"""
V.I.E.R.N.E.S. - Cliente Asíncrono Asterisk REST Interface (ARI) y Stasis WebSocket
=====================================================================================
Permite el control programático total de canales, puentes de audio, reproducción,
originación de llamadas y recepción de eventos en tiempo real.
"""

import asyncio
import json
import logging
from typing import Any, Callable, Coroutine, Dict, List, Optional
import aiohttp

logger = logging.getLogger("VIERNES.ARI")


class ARIClient:
    """
    Cliente asíncrono para Asterisk REST Interface (ARI).
    """

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8088/ari",
        ws_url: str = "ws://127.0.0.1:8088/ari/events",
        username: str = "viernes-ari-user",
        password: str = "ViernesSecretPass2026",
        app_name: str = "viernes-voice",
    ):
        self.base_url = base_url.rstrip("/")
        self.ws_url = ws_url
        self.username = username
        self.password = password
        self.app_name = app_name

        self._session: Optional[aiohttp.ClientSession] = None
        self._ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self._is_running = False
        self._event_handlers: Dict[str, List[Callable[[Dict[str, Any]], Coroutine]]] = {}

    def register_event_handler(self, event_type: str, handler: Callable[[Dict[str, Any]], Coroutine]):
        """Registra una función callback para un tipo de evento ARI (ej: StasisStart, ChannelDtmfReceived)."""
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)

    async def _get_auth_header(self) -> aiohttp.BasicAuth:
        return aiohttp.BasicAuth(self.username, self.password)

    async def start(self):
        """Inicia la sesión HTTP y el WebSocket de escucha de eventos Stasis."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(auth=await self._get_auth_header())

        self._is_running = True
        asyncio.create_task(self._websocket_loop())
        logger.info(f" Conectado a Asterisk ARI en {self.base_url} (App: {self.app_name})")

    async def stop(self):
        """Cierra la conexión WebSocket y la sesión HTTP."""
        self._is_running = False
        if self._ws and not self._ws.closed:
            await self._ws.close()
        if self._session and not self._session.closed:
            await self._session.close()
        logger.info(" ARI Client detenido.")

    async def _websocket_loop(self):
        """Bucle de reconexión y escucha de eventos ARI WebSocket."""
        auth_param = f"api_key={self.username}:{self.password}"
        subscribe_param = f"app={self.app_name}&subscribeAll=true"
        full_ws_url = f"{self.ws_url}?{auth_param}&{subscribe_param}"

        while self._is_running:
            try:
                logger.info(f"🔗 Conectando WebSocket ARI a {self.ws_url}...")
                async with self._session.ws_connect(full_ws_url) as ws:
                    self._ws = ws
                    logger.info(f"✅ WebSocket ARI conectado para Stasis App: '{self.app_name}'")
                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            try:
                                data = json.loads(msg.data)
                                await self._dispatch_event(data)
                            except Exception as e:
                                logger.error(f"Error procesando mensaje ARI: {e}")
                        elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                            break
            except Exception as e:
                logger.warning(f"⚠️ Error en conexión WebSocket ARI: {e}. Reintentando en 3s...")
                await asyncio.sleep(3)

    async def _dispatch_event(self, event_data: Dict[str, Any]):
        """Despacha el evento recibido a los manejadores registrados."""
        event_type = event_data.get("type", "Unknown")
        handlers = self._event_handlers.get(event_type, [])
        wildcard_handlers = self._event_handlers.get("*", [])

        for handler in handlers + wildcard_handlers:
            try:
                await handler(event_data)
            except Exception as e:
                logger.error(f"Error en manejador de evento ARI {event_type}: {e}", exc_info=True)

    # --------------------------------------------------------------------------
    # MÉTODOS REST: CONTROL DE CANALES Y LLAMADAS
    # --------------------------------------------------------------------------
    async def answer_channel(self, channel_id: str) -> bool:
        """Descolgar/Contestar un canal entrante."""
        url = f"{self.base_url}/channels/{channel_id}/answer"
        try:
            async with self._session.post(url) as resp:
                return resp.status in (200, 204)
        except Exception as e:
            logger.error(f"Error contestando canal {channel_id}: {e}")
            return False

    async def hangup_channel(self, channel_id: str, reason: str = "normal") -> bool:
        """Colgar un canal."""
        url = f"{self.base_url}/channels/{channel_id}"
        params = {"reason": reason}
        try:
            async with self._session.delete(url, params=params) as resp:
                return resp.status in (200, 204)
        except Exception as e:
            logger.error(f"Error colgando canal {channel_id}: {e}")
            return False

    async def originate_call(
        self,
        endpoint: str,
        caller_id: str,
        app: Optional[str] = None,
        app_args: Optional[str] = None,
        context: Optional[str] = None,
        extension: Optional[str] = None,
        priority: int = 1,
        timeout: int = 45,
        variables: Optional[Dict[str, str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Origina una llamada saliente (usado para alertas de emergencia o llamadas del asistente).
        """
        url = f"{self.base_url}/channels"
        payload: Dict[str, Any] = {
            "endpoint": endpoint,
            "callerId": caller_id,
            "timeout": timeout,
        }

        if app:
            payload["app"] = app or self.app_name
            if app_args:
                payload["appArgs"] = app_args
        elif context and extension:
            payload["context"] = context
            payload["extension"] = extension
            payload["priority"] = priority

        if variables:
            payload["variables"] = variables

        try:
            async with self._session.post(url, json=payload) as resp:
                if resp.status in (200, 201):
                    data = await resp.json()
                    logger.info(f"📞 Llamada originada exitosamente con ID: {data.get('id')} hacia {endpoint}")
                    return data
                else:
                    err_text = await resp.text()
                    logger.error(f"Error al originar llamada a {endpoint} (HTTP {resp.status}): {err_text}")
                    return None
        except Exception as e:
            logger.error(f"Excepción originando llamada: {e}")
            return None

    async def play_audio(self, channel_id: str, media_uri: str) -> Optional[str]:
        """
        Reproduce un audio o sonido en el canal (ej: 'sound:hello-world' o 'recording:alert123').
        Retorna el playback_id generado.
        """
        url = f"{self.base_url}/channels/{channel_id}/play"
        payload = {"media": media_uri}
        try:
            async with self._session.post(url, json=payload) as resp:
                if resp.status in (200, 201):
                    data = await resp.json()
                    return data.get("id")
        except Exception as e:
            logger.error(f"Error reproduciendo audio en canal {channel_id}: {e}")
        return None

    async def stop_playback(self, playback_id: str) -> bool:
        """Detiene una reproducción activa en un canal."""
        url = f"{self.base_url}/playbacks/{playback_id}"
        try:
            async with self._session.delete(url) as resp:
                return resp.status in (200, 204)
        except Exception as e:
            logger.error(f"Error deteniendo playback {playback_id}: {e}")
            return False

    async def create_bridge(self, bridge_type: str = "mixing", name: str = "viernes_bridge") -> Optional[str]:
        """Crea un puente de audio (Bridge) para mezclar o conectar canales."""
        url = f"{self.base_url}/bridges"
        payload = {"type": bridge_type, "name": name}
        try:
            async with self._session.post(url, json=payload) as resp:
                if resp.status in (200, 201):
                    data = await resp.json()
                    return data.get("id")
        except Exception as e:
            logger.error(f"Error creando bridge: {e}")
        return None

    async def add_channel_to_bridge(self, bridge_id: str, channel_id: str) -> bool:
        """Añade un canal a un puente de audio."""
        url = f"{self.base_url}/bridges/{bridge_id}/addChannel"
        params = {"channel": channel_id}
        try:
            async with self._session.post(url, params=params) as resp:
                return resp.status in (200, 204)
        except Exception as e:
            logger.error(f"Error agregando canal {channel_id} a bridge {bridge_id}: {e}")
            return False

    async def create_external_media_channel(
        self,
        external_host: str,
        format_str: str = "slin16",
        encapsulation: str = "rtp",
        transport: str = "udp",
    ) -> Optional[Dict[str, Any]]:
        """
        Crea un canal ExternalMedia en Asterisk para transmitir/recibir audio RTP directo a un socket UDP de IA.
        """
        url = f"{self.base_url}/channels/externalMedia"
        payload = {
            "app": self.app_name,
            "external_host": external_host,
            "format": format_str,
            "encapsulation": encapsulation,
            "transport": transport,
        }
        try:
            async with self._session.post(url, json=payload) as resp:
                if resp.status in (200, 201):
                    return await resp.json()
                else:
                    logger.error(f"ExternalMedia error HTTP {resp.status}: {await resp.text()}")
        except Exception as e:
            logger.error(f"Error creando canal externalMedia: {e}")
        return None
