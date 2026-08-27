"""
Cliente de Gemini Multimodal Live API para V.I.E.R.N.E.S.
Streaming bidireccional por WebSockets de audio PCM con Function Calling y personalidad de Iron Man.
"""

import os
import json
import base64
import asyncio
import logging
import websockets
from typing import Optional, Dict, Any, Callable
from viernes.core.tools_registry import GEMINI_TOOL_DECLARATIONS, ToolsDispatcher
from viernes.core.audio_pipeline import audio_pipeline
from viernes.core.event_bus import bus

logger = logging.getLogger("viernes.gemini_live")

VIERNES_SYSTEM_PROMPT = """
Eres V.I.E.R.N.E.S. (Viernes Intelligent Entity & Realtime Network Environment System), la asistente de inteligencia artificial táctica y personal de Stark Industries instalada en una Raspberry Pi 5.
Personalidad y directrices:
1. Tratas al usuario como "Señor" o "Jefe". Eres leal, altamente competente, eficiente, concisa y con un sutil ingenio elegante.
2. Tus respuestas son habladas por voz: Sé directa, natural y fluida. NO uses markdown complejo, asteriscos ni listas con viñetas largas en tus respuestas de audio.
3. Tienes control total sobre los sistemas del hogar y la red:
   - Si el usuario te pide encender su computador, invoca la herramienta 'turn_on_pc'.
   - Si te pide apagar o encender las luces, invoca 'control_smart_light'.
   - Si pregunta por sus correos, invoca 'get_important_emails' y destaca solo lo urgente.
   - Si pregunta por sus PRs o GitHub, invoca 'check_github_status'.
   - Si pide una alarma o recordatorio, invoca 'set_alarm_or_reminder'.
   - Si pide una llamada, invoca 'make_phone_call'.
   - Si pide el informe del día, invoca 'get_morning_briefing'.
4. Cuando ejecutes una herramienta, informa brevemente al usuario de la acción tomada como un asistente de combate de alta tecnología.
"""

GEMINI_LIVE_URL = "wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1alpha.GenerativeService.BidiGenerateContent"


class GeminiLiveClient:
    def __init__(self, api_key: Optional[str] = None, model: str = "models/gemini-2.0-flash-exp"):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.model = model
        self.ws = None
        self.is_connected = False
        self.is_speaking = False
        self.listen_task = None
        self.send_audio_task = None

    async def connect(self) -> bool:
        """Establece conexión WebSocket con Gemini Multimodal Live API."""
        if not self.api_key or self.api_key.startswith("AIzaSyYour"):
            logger.warning("GEMINI_API_KEY no configurada. V.I.E.R.N.E.S. operará en modo simulado para desarrollo.")
            return False

        url = f"{GEMINI_LIVE_URL}?key={self.api_key}"
        try:
            self.ws = await websockets.connect(url, max_size=10 * 1024 * 1024)
            self.is_connected = True
            logger.info("Conexión WebSocket establecida con Gemini Live API.")

            # Enviar configuración inicial (Handshake de Setup)
            await self._send_setup_payload()

            # Iniciar bucles de recepción y envío
            self.listen_task = asyncio.create_task(self._receive_loop())
            self.send_audio_task = asyncio.create_task(self._send_audio_loop())

            await bus.publish("ai/connected", {"model": self.model}, sender="gemini_live")
            return True
        except Exception as e:
            logger.error(f"Error conectando con Gemini Live API: {e}")
            self.is_connected = False
            return False

    async def _send_setup_payload(self):
        """Envía el handshake de configuración del asistente, herramientas y voz."""
        setup_msg = {
            "setup": {
                "model": self.model,
                "generationConfig": {
                    "responseModalities": ["AUDIO"],
                    "speechConfig": {
                        "voiceConfig": {
                            "prebuiltVoiceConfig": {
                                "voiceName": "Aoede" # Voz femenina sofisticada
                            }
                        }
                    },
                    "temperature": 0.6,
                },
                "systemInstruction": {
                    "parts": [{"text": VIERNES_SYSTEM_PROMPT}]
                },
                "tools": [
                    {"functionDeclarations": GEMINI_TOOL_DECLARATIONS}
                ]
            }
        }
        await self.ws.send(json.dumps(setup_msg))
        logger.info("Setup inicial de Gemini Live enviado con éxito.")

    async def _receive_loop(self):
        """Escucha continua de mensajes, audio y llamadas a funciones desde Gemini Live."""
        try:
            while self.is_connected and self.ws:
                msg_raw = await self.ws.recv()
                msg = json.loads(msg_raw)

                server_content = msg.get("serverContent")
                if server_content:
                    model_turn = server_content.get("modelTurn")
                    if model_turn:
                        parts = model_turn.get("parts", [])
                        for part in parts:
                            # 1. Fragmentos de Audio PCM (24kHz)
                            inline_data = part.get("inlineData")
                            if inline_data and inline_data.get("mimeType", "").startswith("audio/pcm"):
                                pcm_bytes = base64.b64decode(inline_data.get("data", ""))
                                await audio_pipeline.play_pcm_chunk(pcm_bytes)
                                self.is_speaking = True

                            # 2. Fragmentos de Texto (si aplica)
                            text = part.get("text")
                            if text:
                                logger.info(f"V.I.E.R.N.E.S: {text}")
                                await bus.publish("ai/text_response", {"text": text}, sender="gemini_live")

                    # Detección de interrupción (Barge-in)
                    if server_content.get("interrupted"):
                        logger.info("Interrupción detectada por usuario. Vaciando buffer de audio.")
                        self.is_speaking = False
                        # Vaciar cola de audio pendiente
                        while not audio_pipeline.audio_queue_out.empty():
                            try:
                                audio_pipeline.audio_queue_out.get_nowait()
                                audio_pipeline.audio_queue_out.task_done()
                            except Exception:
                                break

                    if server_content.get("turnComplete"):
                        self.is_speaking = False

                # 3. Manejo de Tool Calls / Function Calling
                tool_call = msg.get("toolCall")
                if tool_call:
                    function_calls = tool_call.get("functionCalls", [])
                    responses = []
                    for fc in function_calls:
                        call_id = fc.get("id")
                        name = fc.get("name")
                        args = fc.get("args", {})
                        logger.info(f"Gemini invoca Tool: {name} (ID: {call_id})")

                        # Ejecutar acción real
                        result = await ToolsDispatcher.execute_tool(name, args)
                        responses.append({
                            "id": call_id,
                            "name": name,
                            "response": {"output": result}
                        })

                    # Enviar respuesta de vuelta a Gemini Live
                    tool_response_msg = {
                        "toolResponse": {
                            "functionResponses": responses
                        }
                    }
                    await self.ws.send(json.dumps(tool_response_msg))

        except websockets.exceptions.ConnectionClosed:
            logger.warning("Conexión WebSocket cerrada con Gemini Live.")
        except Exception as e:
            logger.error(f"Error en receive_loop de Gemini Live: {e}")
        finally:
            self.is_connected = False

    async def _send_audio_loop(self):
        """Envía continuamente el audio del micrófono (PCM 16kHz) a Gemini Live."""
        try:
            while self.is_connected and self.ws:
                pcm_data = await audio_pipeline.audio_queue_in.get()
                if pcm_data:
                    b64_audio = base64.b64encode(pcm_data).decode("utf-8")
                    realtime_msg = {
                        "realtimeInput": {
                            "mediaChunks": [
                                {
                                    "mimeType": "audio/pcm;rate=16000",
                                    "data": b64_audio
                                }
                            ]
                        }
                    }
                    await self.ws.send(json.dumps(realtime_msg))
                audio_pipeline.audio_queue_in.task_done()
        except Exception as e:
            logger.debug(f"Error enviando audio a Gemini Live: {e}")

    async def _generate_content_rest(self, prompt: str, context_hint: str = "") -> Optional[str]:
        """Ejecuta inferencia directa con la API oficial de Google Gemini con soporte para Function Calling."""
        import urllib.request
        api_key = self.api_key or os.getenv("GEMINI_API_KEY", "")
        if not api_key or api_key.startswith("AIzaSyYour"):
            return None

        # Resolver modelo activo
        active_model = models_manager.active_model.replace("models/", "")
        if not active_model or "exp" in active_model:
            active_model = "gemini-2.0-flash"

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

        # 1. Auto-feed de memoria en segundo plano
        asyncio.create_task(AutoMemoryFeeder.analyze_and_auto_feed(prompt))

        # 2. Recuperación semántica de recuerdos vectoriales relevantes
        relevant_memories = await vector_rag.query_semantic_search(prompt, top_k=2)
        context_hint = ""
        if relevant_memories:
            context_hint = "; ".join([m["content"] for m in relevant_memories])

        # 3. Intentar procesar con el modelo de IA Gemini real de Google conectado
        gemini_ai_response = await self._generate_content_rest(prompt, context_hint)
        if gemini_ai_response:
            return gemini_ai_response

        # 4. Fallback local vía ToolsDispatcher si no hay conexión a Internet o clave inválida
        prompt_low = prompt.lower()
        if "enciende" in prompt_low and ("pc" in prompt_low or "computador" in prompt_low or "tarro" in prompt_low):
            res = await ToolsDispatcher.execute_tool("turn_on_pc", {"device_name": "pc_principal"})
            return res.get("message", "Comando WoL enviado.")

        if "frutifantastico" in prompt_low or "fiesta" in prompt_low:
            res = await ToolsDispatcher.execute_tool("trigger_frutifantastico_mode", {})
            return res.get("report", "Modo Frutifantástico activado.")

        if "luz" in prompt_low or "luces" in prompt_low or "apaga" in prompt_low or "prende" in prompt_low:
            action = "off" if "apaga" in prompt_low else "on"
            res = await ToolsDispatcher.execute_tool("control_smart_light", {"target": "luz", "action": action})
            return res.get("message", "Luces actualizadas.")

        if "noticia" in prompt_low or "noticias" in prompt_low or "titular" in prompt_low:
            res = await ToolsDispatcher.execute_tool("get_chile_news", {"limit": 3})
            return res.get("voice_summary", "Noticias de Chile obtenidas.")

        if "clima" in prompt_low or "temperatura" in prompt_low or "lluvia" in prompt_low or "llover" in prompt_low:
            res = await ToolsDispatcher.execute_tool("get_weather_forecast", {"city": "santiago"})
            return res.get("voice_summary", "Pronóstico del clima obtenido.")

        if "correo" in prompt_low or "email" in prompt_low:
            res = await ToolsDispatcher.execute_tool("get_important_emails", {"source": "all"})
            return res.get("summary", "Bandeja de entrada revisada.")

        if "github" in prompt_low or "pr" in prompt_low:
            res = await ToolsDispatcher.execute_tool("check_github_status", {})
            return res.get("summary", "Estado de PRs verificado.")

        if "escanea" in prompt_low or "red" in prompt_low:
            res = await ToolsDispatcher.execute_tool("scan_local_network", {})
            return f"Escaneo completado. Se encontraron {res.get('count', 0)} dispositivos."

        if "recuerda" in prompt_low or "guarda" in prompt_low:
            res = await ToolsDispatcher.execute_tool("store_personal_memory", {
                "category": "note",
                "key_concept": f"nota_{int(asyncio.get_event_loop().time()) % 10000}",
                "content": prompt
            })
            return res.get("message", "Recuerdo almacenado en la base de datos vectorial.")

        return f"A su servicio, señor Bruno. Entendido: {prompt}"

    async def close(self):
        """Cierra la conexión de forma limpia."""
        self.is_connected = False
        if self.ws:
            await self.ws.close()
        logger.info("Cliente Gemini Live desconectado.")


gemini_client = GeminiLiveClient()
