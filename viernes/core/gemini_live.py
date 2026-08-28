"""
Cliente de Gemini Multimodal Live API para V.I.E.R.N.E.S.
Streaming bidireccional por WebSockets de audio PCM con Function Calling, Barge-in,
Keep-Alive y Reconexión Automática Resiliente.
"""

import os
import json
import time
import base64
import asyncio
import logging
import websockets
from typing import Optional, Dict, Any, List, Union
from datetime import datetime

from viernes.core.tools_registry import GEMINI_TOOL_DECLARATIONS, ToolsDispatcher
from viernes.core.models_manager import models_manager
from viernes.core.audio_pipeline import audio_pipeline
from viernes.core.event_bus import bus

logger = logging.getLogger("viernes.gemini_live")

VIERNES_SYSTEM_PROMPT = """Eres V.I.E.R.N.E.S. (F.R.I.D.A.Y.), la asistente táctica y leal de Stark Industries en la Raspberry Pi 5 de Don Bruno en Santiago de Chile.

DIRECTIVAS CRÍTICAS DE VOZ Y COMPORTAMIENTO:
1. IDIOMA Y SALIDA DE VOZ EXCLUSIVA:
   - Habla SIEMPRE en Español de Chile de forma elegante, táctica, natural y directa.
   - NUNCA hables en inglés.
   - NUNCA vocalices tus pensamientos, razonamientos, intenciones ni reflexiones internas. ESTÁ ESTRICTAMENTE PROHIBIDO decir frases como "**Interpreting User Intent**", "**Acknowledging**", "**Offering Assistance**", "I have determined", "Today is indeed Friday", o monólogos en tercera persona. Pronuncia ÚNICA Y EXCLUSIVAMENTE tu respuesta operativa final dirigida a Bruno.
2. CONCISIÓN OPERATIVA:
   - Responde en máximo 1 o 2 oraciones breves, operativas y al grano.
   - NUNCA pronuncies asteriscos, markdown, viñetas, tablas, emojis ni código fuente al hablar.
3. IDENTIDAD Y TRATO:
   - Trata a Bruno con respeto táctico: 'Señor', 'Jefe' o 'Don Bruno'.
   - Ingenio Stark sutil, leal, eficiente y sin adulaciones vacías.
4. HERRAMIENTAS:
   - Invoca herramientas de inmediato para: luces WiZ, aire acondicionado, Android TV del Living, Wake-on-LAN de PC, correos Gmail/Zoho, recordatorios y memoria semántica Vector RAG.
   - Tras ejecutar una herramienta, confirma brevemente por voz con naturalidad."""

GEMINI_LIVE_URL = "wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1alpha.GenerativeService.BidiGenerateContent"
DEFAULT_FALLBACK_MODEL = "models/gemini-2.5-flash-native-audio-latest"

LIVE_CAPABLE_MODELS = {
    "models/gemini-2.5-flash-native-audio-latest",
    "models/gemini-2.5-flash-native-audio-preview-12-2025",
    "models/gemini-2.0-flash-exp",
    "models/gemini-2.0-flash-realtime-exp"
}


class DirectAudioStreamer:
    """
    Puente de streaming directo de latencia sub-1ms para Gemini Live.
    - Envío inmediato de frames PCM 16kHz sin acumuladores de tiempo artificiales.
    - Purga atómica de cola (Barge-in / Anti-Bufferbloat).
    """
    def __init__(self, ws_send_coro, max_queue_size: int = 4):
        self.ws_send_coro = ws_send_coro
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue_size)
        self._worker_task: Optional[asyncio.Task] = None
        self._running = False

    def start(self):
        if self._running:
            return
        self._running = True
        self.purge()
        self._worker_task = asyncio.create_task(self._stream_worker())

    async def stop(self):
        self._running = False
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        self.purge()

    def purge(self):
        """Descarta todo audio acumulado instantáneamente (Anti-Lag)."""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
                self._queue.task_done()
            except Exception:
                break

    def reset(self):
        """Alias de purge para compatibilidad con eventos de barge-in."""
        self.purge()

    async def push_chunk(self, b64_pcm: str):
        """Encola el frame descartando frames viejos si hay retraso de red (Zero-Lag guarantee)."""
        if not self._running or not b64_pcm:
            return
        if self._queue.full():
            try:
                self._queue.get_nowait()
                self._queue.task_done()
            except Exception:
                pass
        try:
            self._queue.put_nowait(b64_pcm)
        except Exception:
            pass

    async def push_pcm(self, pcm_bytes: bytes):
        if not pcm_bytes:
            return
        b64_data = base64.b64encode(pcm_bytes).decode("utf-8")
        await self.push_chunk(b64_data)

    async def _stream_worker(self):
        while self._running:
            try:
                b64_pcm = await self._queue.get()
                await self.ws_send_coro(b64_pcm)
                self._queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"Error en DirectAudioStreamer: {e}")
                await asyncio.sleep(0.002)


AudioChunkPacer = DirectAudioStreamer


class GeminiLiveClient:
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        # Obtener modelo dinámicamente sin hardcoding
        initial_model = model or os.getenv("GEMINI_MODEL", DEFAULT_FALLBACK_MODEL)
        if not initial_model.startswith("models/"):
            initial_model = f"models/{initial_model}"
        self.model = initial_model
        self.model_name = initial_model
        self.ws = None
        self.ws_lock = asyncio.Lock()
        self.is_connected = False
        self.is_speaking = False
        self._should_run = True
        self._listen_task: Optional[asyncio.Task] = None
        self._send_audio_task: Optional[asyncio.Task] = None
        self._supervisor_task: Optional[asyncio.Task] = None
        self.streamer = DirectAudioStreamer(ws_send_coro=self.send_b64_audio_direct)
        self.pacer = self.streamer

    @property
    def active_live_model(self) -> str:
        """Devuelve el modelo normalizado para Live WebSocket con fallback a 2.5-native-audio si el modelo no soporta audio bidi."""
        m = getattr(self, "model", None) or getattr(self, "model_name", None) or models_manager.active_model or os.getenv("GEMINI_MODEL", DEFAULT_FALLBACK_MODEL)
        if not m:
            m = DEFAULT_FALLBACK_MODEL
        if not m.startswith("models/"):
            m = f"models/{m}"

        if m not in LIVE_CAPABLE_MODELS:
            logger.info(f"ℹ️ Modelo '{m}' configurado. En canal de voz interactiva WebSocket se utiliza '{DEFAULT_FALLBACK_MODEL}'.")
            return DEFAULT_FALLBACK_MODEL

        return m

    def _build_setup_message(self) -> dict:
        """Construye el payload exacto de inicialización acorde al protocolo Gemini Live."""
        return {
            "setup": {
                "model": self.active_live_model,
                "generationConfig": {
                    "responseModalities": ["AUDIO"],
                    "speechConfig": {
                        "voiceConfig": {
                            "prebuiltVoiceConfig": {
                                "voiceName": os.getenv("VOICE_NAME", "Aoede")
                            }
                        }
                    },
                    "temperature": 0.4
                },
                "systemInstruction": {
                    "parts": [{"text": VIERNES_SYSTEM_PROMPT}]
                },
                "tools": [
                    {"functionDeclarations": GEMINI_TOOL_DECLARATIONS}
                ]
            }
        }

    async def connect(self) -> bool:
        """Inicia el supervisor de conexión en segundo plano."""
        key = self.api_key or os.getenv("GEMINI_API_KEY", "")
        if not key or key.startswith("AIzaSyYour"):
            logger.warning("GEMINI_API_KEY no configurada. V.I.E.R.N.E.S. operará en modo local para desarrollo.")
            return False

        if not self._supervisor_task or self._supervisor_task.done():
            self._should_run = True
            self._supervisor_task = asyncio.create_task(self._connection_supervisor())
        return True

    async def _connection_supervisor(self):
        """Mantiene la sesión de Gemini Live activa con reconexión automática y backoff."""
        retry_delay = 2
        max_delay = 30

        while self._should_run:
            key = self.api_key or os.getenv("GEMINI_API_KEY", "")
            if not key or key.startswith("AIzaSyYour"):
                await asyncio.sleep(5)
                continue

            url = f"{GEMINI_LIVE_URL}?key={key}"
            try:
                target_model = self.active_live_model
                logger.info(f"Conectando a Gemini Live API ({target_model})...")
                async with websockets.connect(
                    url,
                    ping_interval=20,
                    ping_timeout=20,
                    compression=None,
                    max_size=10 * 1024 * 1024
                ) as ws:
                    self.ws = ws
                    self.is_connected = True
                    self.streamer.start()
                    retry_delay = 2
                    logger.info("✓ Conexión WebSocket establecida con Gemini Live.")

                    # 1. Enviar Setup Handshake
                    setup_payload = self._build_setup_message()
                    async with self.ws_lock:
                        await self.ws.send(json.dumps(setup_payload))
                    logger.info(f"Setup inicial de Gemini Live enviado ({target_model}). Esperando confirmación...")

                    # 2. Esperar confirmación estricta de setupComplete antes de transmitir
                    first_msg_raw = await self.ws.recv()
                    first_msg = json.loads(first_msg_raw)
                    if "setupComplete" in first_msg:
                        logger.info("🟢 [Gemini Live] Sesión inicializada con éxito (setupComplete recibido).")
                    else:
                        logger.warning(f"Respuesta inicial al setup: {first_msg}")

                    await bus.publish("ai/connected", {"model": target_model}, sender="gemini_live")

                    # 3. Iniciar tareas concurrentes de envío y recepción
                    self._listen_task = asyncio.create_task(self._receive_loop())
                    self._send_audio_task = asyncio.create_task(self._send_audio_loop())

                    done, pending = await asyncio.wait(
                        [self._listen_task, self._send_audio_task],
                        return_when=asyncio.FIRST_COMPLETED
                    )

                    for task in pending:
                        if not task.done():
                            task.cancel()

            except (websockets.exceptions.ConnectionClosedError, websockets.exceptions.ConnectionClosedOK, websockets.exceptions.ConnectionClosed) as e:
                close_code = getattr(e, "code", None)
                close_reason = getattr(e, "reason", "") or str(e)
                logger.warning(f"Conexión WebSocket cerrada con Gemini Live (código {close_code}: {close_reason}).")

                # Detección de Error 1008 (Policy Violation / Modelo incompatible con bidi audio)
                is_1008 = close_code == 1008 or "1008" in str(close_reason) or "policy" in str(close_reason).lower()
                if is_1008 and target_model != DEFAULT_FALLBACK_MODEL:
                    logger.warning(f"⚠️ Error 1008 en {target_model}. Conmutando de inmediato al modelo certificado '{DEFAULT_FALLBACK_MODEL}'.")
                    self.model = DEFAULT_FALLBACK_MODEL
                    self.model_name = DEFAULT_FALLBACK_MODEL
                    retry_delay = 0.5
                    await bus.publish("ai/error", {
                        "error": f"Error 1008 en '{target_model}'. Fallback automático a '{DEFAULT_FALLBACK_MODEL}'.",
                        "fallback": DEFAULT_FALLBACK_MODEL
                    }, sender="gemini_live")
                else:
                    await bus.publish("ai/disconnected", {"code": close_code, "reason": close_reason}, sender="gemini_live")
            except Exception as e:
                logger.error(f"Error en sesión Gemini Live: {e}")
            finally:
                self.is_connected = False
                self.ws = None
                self.is_speaking = False
                await self.streamer.stop()

            if self._should_run:
                logger.info(f"Reintentando conexión con Gemini Live en {retry_delay} segundos...")
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, max_delay)

    async def _receive_loop(self):
        """Procesa mensajes entrantes, audio PCM 24kHz, barge-in y Function Calling."""
        try:
            while self.is_connected and self.ws:
                msg_raw = await self.ws.recv()
                msg = json.loads(msg_raw)

                # 1. Procesar contenido del servidor (Audio / Texto / Control)
                server_content = msg.get("serverContent")
                if server_content:
                    model_turn = server_content.get("modelTurn")
                    if model_turn:
                        parts = model_turn.get("parts", [])
                        for part in parts:
                            inline_data = part.get("inlineData")
                            if inline_data and inline_data.get("mimeType", "").startswith("audio/pcm"):
                                b64_pcm = inline_data.get("data", "")
                                pcm_bytes = base64.b64decode(b64_pcm)
                                await audio_pipeline.play_pcm_chunk(pcm_bytes)
                                await bus.publish("ai/audio_chunk", {
                                    "data": b64_pcm,
                                    "mimeType": inline_data.get("mimeType", "audio/pcm;rate=24000")
                                }, sender="gemini_live")
                                self.is_speaking = True

                            text = part.get("text")
                            if text:
                                logger.info(f"V.I.E.R.N.E.S: {text}")
                                await bus.publish("ai/text_response", {"text": text}, sender="gemini_live")

                    # Detección de Barge-in (Interrupción por el usuario)
                    if server_content.get("interrupted"):
                        logger.info("🛑 [Barge-in] Interrupción detectada. Vaciando buffer de audio.")
                        self.is_speaking = False
                        self.pacer.reset()
                        audio_pipeline.interrupt_playback()
                        await bus.publish("ai/interrupted", {}, sender="gemini_live")

                    if server_content.get("turnComplete"):
                        self.is_speaking = False
                        await bus.publish("ai/turn_complete", {}, sender="gemini_live")

                # 2. Manejo de Tool Calls (Function Calling)
                tool_call = msg.get("toolCall")
                if tool_call:
                    asyncio.create_task(self._handle_tool_call(tool_call))

                # 3. Cancelación de llamadas a herramientas
                tool_cancellation = msg.get("toolCallCancellation")
                if tool_cancellation:
                    logger.warning(f"Llamadas a herramientas canceladas por Gemini: {tool_cancellation}")

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error en receive_loop de Gemini Live: {e}")
            raise

    async def _send_audio_loop(self):
        """Transmite continuamente el audio PCM 16kHz del micrófono local hacia Gemini Live (Zero-Wait)."""
        try:
            while self.is_connected and self.ws:
                pcm_frame = await audio_pipeline.audio_queue_in.get()
                if pcm_frame and len(pcm_frame) > 0:
                    await self.send_audio_chunk_direct(pcm_frame)
                audio_pipeline.audio_queue_in.task_done()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error en send_audio_loop de Gemini Live: {e}")

    async def send_b64_audio_direct(self, b64_pcm: str):
        """
        Zero-Wait Direct Streaming: Serialización directa en sub-1ms y transmisión
        thread-safe sobre el WebSocket sin buffering ni encolamiento artificial.
        """
        if not self.is_connected or not self.ws or not b64_pcm:
            return

        payload = f'{{"realtimeInput":{{"mediaChunks":[{{"mimeType":"audio/pcm;rate=16000","data":"{b64_pcm}"}}]}}}}'
        try:
            async with self.ws_lock:
                if self.ws and self.is_connected:
                    await self.ws.send(payload)
        except Exception as ex:
            logger.debug(f"Error transmitiendo mediaChunk zero-wait a Gemini: {ex}")

    async def send_audio_chunk_direct(self, pcm_data: bytes):
        """Convierte PCM16 crudo a Base64 y lo envía instantáneamente sin esperas."""
        if not pcm_data:
            return
        b64_pcm = base64.b64encode(pcm_data).decode("ascii")
        await self.send_b64_audio_direct(b64_pcm)

    async def feed_b64_audio_chunk(self, b64_pcm: str):
        """
        Ruta Rápida: Passthrough directo para audio Base64 proveniente del WebSocket Web HUD.
        Elimina la decodificación y re-codificación redundante.
        """
        if not self.is_connected:
            await self.connect()
        await self.send_b64_audio_direct(b64_pcm)

    async def feed_audio_chunk(self, audio_data: Union[bytes, str]):
        """Reenvía audio PCM (bytes crudos o str Base64) con transmisión inmediata."""
        if isinstance(audio_data, str):
            await self.feed_b64_audio_chunk(audio_data)
        elif isinstance(audio_data, (bytes, bytearray)):
            if not self.is_connected:
                await self.connect()
            await self.send_audio_chunk_direct(bytes(audio_data))

    async def _handle_tool_call(self, tool_call: dict):
        """Ejecuta herramientas concurrentemente y responde de forma thread-safe con el esquema exacto de BidiGenerateContent."""
        function_calls = tool_call.get("functionCalls", [])
        if not function_calls:
            return

        async def _run_single_tool(fc):
            call_id = fc.get("id")
            name = fc.get("name")
            args = fc.get("args", {})
            logger.info(f"⚡ [Gemini Tool Call] Invocando: {name} (ID: {call_id}) con args: {args}")
            try:
                result = await asyncio.wait_for(ToolsDispatcher.execute_tool(name, args), timeout=2.5)
            except asyncio.TimeoutError:
                logger.warning(f"Timeout en herramienta {name} tras 2.5s.")
                result = {"status": "timeout", "message": f"Herramienta {name} excedió tiempo límite."}
            except Exception as ex:
                logger.error(f"Error ejecutando herramienta {name}: {ex}")
                result = {"status": "error", "message": str(ex)}

            return {
                "id": call_id,
                "name": name,
                "response": {"output": result}
            }

        responses = await asyncio.gather(*[_run_single_tool(fc) for fc in function_calls])
        tool_response_msg = {
            "toolResponse": {
                "functionResponses": list(responses)
            }
        }
        if self.is_connected and self.ws:
            try:
                payload = json.dumps(tool_response_msg, default=str)
                async with self.ws_lock:
                    if self.is_connected and self.ws:
                        await self.ws.send(payload)
                logger.info(f"📤 [Tool Response] {len(responses)} resultados enviados a Gemini Live.")
            except Exception as e:
                logger.error(f"Error enviando toolResponse a Gemini Live: {e}")

    async def _generate_content_rest(self, prompt: str, context_hint: str = "") -> Optional[str]:
        """Ejecuta inferencia directa con la API oficial de Google Gemini con soporte para Function Calling."""
        import urllib.request
        api_key = self.api_key or os.getenv("GEMINI_API_KEY", "")
        if not api_key or api_key.startswith("AIzaSyYour"):
            return None

        # Resolver modelo activo respetando la elección del usuario (sin overrides)
        raw_model = models_manager.active_model or os.getenv("GEMINI_MODEL", "models/gemini-2.0-flash-exp")
        active_model = raw_model.replace("models/", "").strip()
        if not active_model:
            active_model = "gemini-2.0-flash-exp"

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{active_model}:generateContent?key={api_key}"

        system_text = VIERNES_SYSTEM_PROMPT
        if context_hint:
            system_text += f"\n\nContexto relevante de la memoria del usuario:\n{context_hint}"

        tools_payload = [{"functionDeclarations": GEMINI_TOOL_DECLARATIONS}]

        request_body = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}]
                }
            ],
            "systemInstruction": {
                "parts": [{"text": system_text}]
            },
            "tools": tools_payload,
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 800
            }
        }

        loop = asyncio.get_running_loop()

        def _do_post(body_dict):
            req_data = json.dumps(body_dict).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=req_data,
                headers={"Content-Type": "application/json", "User-Agent": "VIERNES-AI-Agent/2.0"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=12) as response:
                return json.loads(response.read().decode("utf-8"))

        try:
            resp_data = await loop.run_in_executor(None, _do_post, request_body)
            candidates = resp_data.get("candidates", [])
            if not candidates:
                return None

            content = candidates[0].get("content", {})
            parts = content.get("parts", [])

            func_call = None
            text_reply = ""
            for p in parts:
                if "functionCall" in p:
                    func_call = p["functionCall"]
                elif "text" in p:
                    text_reply += p["text"]

            if func_call:
                fn_name = func_call.get("name")
                fn_args = func_call.get("args", {})
                logger.info(f"⚡ Gemini Function Calling invocado desde Web: {fn_name}({fn_args})")
                tool_result = await ToolsDispatcher.execute_tool(fn_name, fn_args)
                logger.info(f"✓ Resultado de ejecución de {fn_name}: {tool_result}")

                # Enviar resultado de vuelta al modelo para sintetizar respuesta natural
                followup_body = {
                    "contents": [
                        {"role": "user", "parts": [{"text": prompt}]},
                        {"role": "model", "parts": [{"functionCall": func_call}]},
                        {
                            "role": "user",
                            "parts": [
                                {
                                    "functionResponse": {
                                        "name": fn_name,
                                        "response": {"result": tool_result}
                                    }
                                }
                            ]
                        }
                    ],
                    "systemInstruction": {"parts": [{"text": system_text}]},
                    "tools": tools_payload
                }

                followup_resp = await loop.run_in_executor(None, _do_post, followup_body)
                fc_candidates = followup_resp.get("candidates", [])
                if fc_candidates:
                    fc_parts = fc_candidates[0].get("content", {}).get("parts", [])
                    final_text = "".join(p.get("text", "") for p in fc_parts).strip()
                    if final_text:
                        return final_text

                return tool_result.get("message") or tool_result.get("voice_summary") or tool_result.get("summary") or "Comando ejecutado exitosamente, señor."

            if text_reply:
                return text_reply.strip()

        except Exception as e:
            logger.warning(f"Error en consulta REST a Gemini AI ({e}). Recurriendo a ejecutor local.")
            return None

    async def send_text_prompt(self, prompt: str) -> str:
        """Permite enviar comandos de texto o voz a través del Dashboard HUD con Vector RAG e IA real."""
        from viernes.memory.vector_rag import vector_rag, AutoMemoryFeeder

        logger.info(f"Usuario (HUD Web): {prompt}")
        await bus.publish("user/text_prompt", {"text": prompt}, sender="hud")

        # 1. Normalizar prompt retirando prefijo de wakeword
        clean_prompt = prompt.strip()
        prompt_lower = clean_prompt.lower()
        for prefix in ["oye viernes,", "oye viernes", "hey viernes,", "hey viernes", "okey viernes", "viernes,", "viernes"]:
            if prompt_lower.startswith(prefix):
                clean_prompt = clean_prompt[len(prefix):].strip(" ,:.-")
                break

        if not clean_prompt:
            return "A su servicio, señor Bruno. ¿En qué puedo colaborar hoy?"

        # 2. Auto-feed de memoria en segundo plano
        asyncio.create_task(AutoMemoryFeeder.analyze_and_auto_feed(clean_prompt))

        # 3. Recuperación semántica de recuerdos vectoriales relevantes
        relevant_memories = await vector_rag.query_semantic_search(clean_prompt, top_k=2)
        context_hint = ""
        if relevant_memories:
            context_hint = "; ".join([m["content"] for m in relevant_memories])

        # 4. Intentar procesar con el modelo de IA Gemini real de Google conectado
        gemini_ai_response = await self._generate_content_rest(clean_prompt, context_hint)
        if gemini_ai_response:
            return gemini_ai_response

        # 5. Fallback local vía ToolsDispatcher si no hay conexión a Internet o clave inválida
        p_low = clean_prompt.lower()

        if any(w in p_low for w in ["hora", "qué hora es", "fecha", "qué día es"]):
            now = datetime.now()
            return f"Son las {now.strftime('%H:%M')} del {now.strftime('%d de %B de %Y')}."

        if any(w in p_low for w in ["hola", "buenos días", "buenas tardes", "cómo estás"]):
            return "Hola Bruno. Todos los sistemas de V.I.E.R.N.E.S. están operativos y a su disposición."

        if "enciende" in p_low and ("pc" in p_low or "computador" in p_low or "tarro" in p_low):
            res = await ToolsDispatcher.execute_tool("turn_on_pc", {"device_name": "pc_principal"})
            return res.get("message", "Comando Wake-on-LAN enviado para encender el equipo principal.")

        if "frutifantastico" in p_low or "fiesta" in p_low:
            res = await ToolsDispatcher.execute_tool("trigger_frutifantastico_mode", {})
            return res.get("report", "Modo Frutifantástico activado.")

        if any(w in p_low for w in ["luz", "luces", "apaga", "prende"]):
            action = "off" if "apaga" in p_low else "on"
            res = await ToolsDispatcher.execute_tool("control_smart_light", {"target": "luz", "action": action})
            return res.get("message", "Luces actualizadas.")

        if any(w in p_low for w in ["noticia", "noticias", "titular"]):
            res = await ToolsDispatcher.execute_tool("get_chile_news", {"limit": 3})
            return res.get("voice_summary", "Noticias de Chile obtenidas.")

        if any(w in p_low for w in ["clima", "temperatura", "lluvia", "llover", "pronóstico"]):
            res = await ToolsDispatcher.execute_tool("get_weather_forecast", {"city": "santiago"})
            return res.get("voice_summary", "Pronóstico del clima obtenido.")

        if any(w in p_low for w in ["correo", "email", "mails"]):
            res = await ToolsDispatcher.execute_tool("get_important_emails", {"source": "all"})
            return res.get("summary", "Bandeja de entrada revisada.")

        if "github" in p_low or "pr" in p_low:
            res = await ToolsDispatcher.execute_tool("check_github_status", {})
            return res.get("summary", "Estado de PRs verificado.")

        if "escanea" in p_low or "red" in p_low:
            res = await ToolsDispatcher.execute_tool("scan_local_network", {})
            return f"Escaneo completado. Se encontraron {res.get('count', 0)} dispositivos."

        if "recuerda" in p_low or "guarda" in p_low:
            note_id = int(time.time()) % 10000
            res = await ToolsDispatcher.execute_tool("store_personal_memory", {
                "category": "note",
                "key_concept": f"nota_{note_id}",
                "content": clean_prompt
            })
            return res.get("message", "Recuerdo almacenado en la base de datos vectorial.")

        return f"A su servicio, señor Bruno. Entendido: {clean_prompt}"

    async def close(self):
        """Cierra la conexión de forma limpia."""
        self._should_run = False
        self.is_connected = False
        if self._listen_task and not self._listen_task.done():
            self._listen_task.cancel()
        if self._send_audio_task and not self._send_audio_task.done():
            self._send_audio_task.cancel()
        if self._supervisor_task and not self._supervisor_task.done():
            self._supervisor_task.cancel()
        if self.ws:
            await self.ws.close()
        logger.info("Cliente Gemini Live desconectado.")


gemini_client = GeminiLiveClient()
