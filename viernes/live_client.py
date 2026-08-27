"""
Cliente WebSocket bidireccional de baja latencia para Gemini Multimodal Live API.
Gestiona la sesión en tiempo real, streaming PCM de audio, interrupciones (barge-in)
y la ejecución automática del ciclo de Function Calling.
"""

import asyncio
import base64
import json
import logging
from typing import Optional
import websockets

from viernes import config
from viernes.prompts import VIERNES_SYSTEM_PROMPT
from viernes.tools_schema import get_gemini_tools_payload
from viernes.tools_executor import dispatch_tool_call
from viernes.audio_stream import AudioStreamManager

logger = logging.getLogger("VIERNES.LiveClient")


class ViernesLiveClient:
    """Cliente principal WebSocket para la interacción por voz en tiempo real con Gemini Live API."""

    def __init__(self, audio_manager: Optional[AudioStreamManager] = None):
        self.audio_manager = audio_manager or AudioStreamManager()
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.is_connected = False
        self._running_tasks = []

    def _build_setup_message(self) -> dict:
        """Construye el mensaje de configuración inicial para la sesión Live."""
        return {
            "setup": {
                "model": config.GEMINI_MODEL,
                "generationConfig": {
                    "responseModalities": ["AUDIO"],
                    "speechConfig": {
                        "voiceConfig": {
                            "prebuiltVoiceConfig": {
                                "voiceName": config.VOICE_NAME
                            }
                        }
                    }
                },
                "systemInstruction": {
                    "parts": [
                        {
                            "text": VIERNES_SYSTEM_PROMPT
                        }
                    ]
                },
                "tools": get_gemini_tools_payload()
            }
        }

    async def connect(self):
        """Establece la conexión WebSocket segura con la API de Gemini Live."""
        if not config.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY no está configurada. Por favor agregue su clave en el archivo .env")

        uri = f"{config.GEMINI_WS_URL}?key={config.GEMINI_API_KEY}"
        logger.info(f"[LiveClient] Conectando a Gemini Live API ({config.GEMINI_MODEL})...")

        # Conexión WebSocket con compresión deshabilitada para latencia ultra baja
        self.websocket = await websockets.connect(
            uri,
            ping_interval=20,
            ping_timeout=20,
            compression=None,
            max_size=10 * 1024 * 1024
        )
        self.is_connected = True
        logger.info("[LiveClient] Conexión WebSocket establecida exitosamente.")

        # 1. Enviar mensaje de Setup
        setup_payload = self._build_setup_message()
        await self.websocket.send(json.dumps(setup_payload))
        logger.info("[LiveClient] Payload de inicialización enviado a Gemini.")

        # 2. Esperar confirmación de Setup del servidor
        first_resp_raw = await self.websocket.recv()
        first_resp = json.loads(first_resp_raw)
        if "setupComplete" in first_resp:
            logger.info("🟢 [LiveClient] Sesión inicializada por Gemini. Sistema V.I.E.R.N.E.S en línea y listo.")
        else:
            logger.warning(f"[LiveClient] Respuesta inesperada tras setup: {first_resp}")

    async def _send_audio_loop(self):
        """Bucle continuo: captura trozos PCM 16kHz del micrófono y los envía a Gemini."""
        logger.info("[LiveClient] Bucle de transmisión de audio hacia Gemini activo.")
        try:
            while self.is_connected and self.websocket:
                # Obtener trozo de audio (PCM 16kHz Mono 16-bit LE)
                pcm_chunk = await self.audio_manager.get_input_chunk()
                if not pcm_chunk:
                    continue

                b64_audio = base64.b64encode(pcm_chunk).decode("utf-8")
                msg = {
                    "realtimeInput": {
                        "mediaChunks": [
                            {
                                "mimeType": config.AUDIO_INPUT_MIME,
                                "data": b64_audio
                            }
                        ]
                    }
                }
                await self.websocket.send(json.dumps(msg))
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"[LiveClient] Error en bucle de envío de audio: {e}")

    async def _handle_tool_call(self, tool_call_data: dict):
        """Procesa una llamada a función emitida por Gemini y envía la respuesta del tool."""
        function_calls = tool_call_data.get("functionCalls", [])
        function_responses = []

        for call in function_calls:
            call_id = call.get("id", "")
            name = call.get("name", "")
            args = call.get("args", {})

            logger.info(f"⚡ [Tool Call Recibido] ID={call_id} | Función={name}")
            # Ejecutar la herramienta en el dispatcher
            result = await dispatch_tool_call(name, args)

            function_responses.append({
                "id": call_id,
                "response": {
                    "output": result
                }
            })

        # Responder al WebSocket con las respuestas de las funciones
        tool_response_msg = {
            "toolResponse": {
                "functionResponses": function_responses
            }
        }
        await self.websocket.send(json.dumps(tool_response_msg))
        logger.info(f"📤 [Tool Response Enviado] Se enviaron {len(function_responses)} resultados de herramientas a Gemini.")

    async def _receive_loop(self):
        """Bucle continuo: procesa respuestas de audio, eventos de interrupción y llamadas a herramientas."""
        logger.info("[LiveClient] Bucle de recepción de eventos de Gemini activo.")
        try:
            async for raw_msg in self.websocket:
                msg = json.loads(raw_msg)

                # 1. Procesar contenido del servidor (audio / texto)
                server_content = msg.get("serverContent")
                if server_content:
                    # Detección de Interrupción (Barge-in del usuario)
                    if server_content.get("interrupted"):
                        logger.info("⚡ [Barge-in] El usuario ha interrumpido a V.I.E.R.N.E.S.")
                        self.audio_manager.interrupt_playback()

                    # Turno del modelo (partes de audio)
                    model_turn = server_content.get("modelTurn")
                    if model_turn:
                        parts = model_turn.get("parts", [])
                        for part in parts:
                            inline_data = part.get("inlineData")
                            if inline_data and "data" in inline_data:
                                mime = inline_data.get("mimeType", "")
                                # Audio PCM 24kHz
                                if "audio" in mime or mime.startswith("audio/pcm"):
                                    pcm_bytes = base64.b64decode(inline_data["data"])
                                    self.audio_manager.put_output_chunk(pcm_bytes)
                            
                            # Si el modelo envía texto de transcripción
                            if "text" in part and part["text"].strip():
                                logger.info(f"💬 [V.I.E.R.N.E.S]: {part['text'].strip()}")

                    if server_content.get("turnComplete"):
                        logger.debug("[LiveClient] Turno de habla del modelo completado.")

                # 2. Procesar llamadas a herramientas (Function Calling)
                tool_call = msg.get("toolCall")
                if tool_call:
                    asyncio.create_task(self._handle_tool_call(tool_call))

                # 3. Cancelación de llamadas a herramientas
                tool_cancellation = msg.get("toolCallCancellation")
                if tool_cancellation:
                    logger.warning(f"[LiveClient] Llamadas a herramientas canceladas por el servidor: {tool_cancellation}")

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"[LiveClient] Error en bucle de recepción: {e}")

    async def run(self):
        """Inicia el cliente, dispositivos de audio y los bucles concurrentes."""
        loop = asyncio.get_running_loop()
        self.audio_manager.start(loop)

        try:
            await self.connect()
            # Lanzar tareas concurrentes para streaming bidireccional
            send_task = asyncio.create_task(self._send_audio_loop())
            recv_task = asyncio.create_task(self._receive_loop())
            self._running_tasks = [send_task, recv_task]

            await asyncio.gather(send_task, recv_task)

        except Exception as e:
            logger.error(f"[LiveClient] Excepción durante la ejecución: {e}")
        finally:
            await self.close()

    async def close(self):
        """Cierre ordenado de conexiones y recursos."""
        self.is_connected = False
        for task in self._running_tasks:
            if not task.done():
                task.cancel()

        if self.websocket:
            await self.websocket.close()
            logger.info("[LiveClient] Conexión WebSocket cerrada.")

        self.audio_manager.stop()
