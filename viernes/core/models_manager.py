"""
Gestor de Modelos de Gemini API y Live Flash para V.I.E.R.N.E.S.
Permite listar dinámicamente los modelos disponibles en Google AI Studio,
clasificando con precisión cuáles son aptos para Live Audio WebSocket (multimodal bidireccional)
vs generación estándar de texto/visión (REST).
"""

import os
import json
import urllib.request
import urllib.error
import logging
import asyncio
from typing import List, Dict, Any, Optional

logger = logging.getLogger("viernes.models")

# Modelos recomendados y catálogo base de fallback
RECOMMENDED_MODELS = [
    {
        "id": "models/gemini-2.5-flash",
        "clean_id": "gemini-2.5-flash",
        "displayName": "Gemini 2.5 Flash [⚡ LIVE AUDIO WS]",
        "raw_displayName": "Gemini 2.5 Flash",
        "description": "Modelo de última generación multimodal de ultra-baja latencia y alta velocidad.",
        "category": "live",
        "category_label": "⚡ Live Audio & Streaming (WebSocket)",
        "is_live_capable": True,
        "is_default": False
    },
    {
        "id": "models/gemini-2.0-flash",
        "clean_id": "gemini-2.0-flash",
        "displayName": "Gemini 2.0 Flash Standard [⚡ LIVE AUDIO WS]",
        "raw_displayName": "Gemini 2.0 Flash Standard",
        "description": "Modelo insignia para streaming multimodal bidireccional y function calling en tiempo real.",
        "is_live_capable": True,
        "is_default": False
    },
    {
        "id": "models/gemini-2.0-flash-exp",
        "clean_id": "gemini-2.0-flash-exp",
        "displayName": "Gemini 2.0 Flash Experimental [⚡ LIVE AUDIO WS]",
        "raw_displayName": "Gemini 2.0 Flash Experimental",
        "description": "Modelo experimental de streaming de voz audio-a-audio con soporte nativo de herramientas.",
        "is_live_capable": True,
        "is_default": True
    },
    {
        "id": "models/gemini-2.0-flash-realtime-exp",
        "clean_id": "gemini-2.0-flash-realtime-exp",
        "displayName": "Gemini 2.0 Flash Realtime Exp [⚡ LIVE AUDIO WS]",
        "raw_displayName": "Gemini 2.0 Flash Realtime Exp",
        "description": "Variante de latencia ultrabaja optimizada para interacciones continuas de audio.",
        "is_live_capable": True,
        "is_default": False
    },
    {
        "id": "models/gemini-2.5-pro",
        "clean_id": "gemini-2.5-pro",
        "displayName": "Gemini 2.5 Pro [🔬 PRO / REASONING]",
        "raw_displayName": "Gemini 2.5 Pro",
        "description": "Modelo avanzado de razonamiento profundo y contexto extendido (REST).",
        "is_live_capable": False,
        "is_default": False
    },
    {
        "id": "models/gemini-1.5-pro",
        "clean_id": "gemini-1.5-pro",
        "displayName": "Gemini 1.5 Pro [🔬 PRO / REASONING]",
        "raw_displayName": "Gemini 1.5 Pro",
        "description": "Modelo de razonamiento complejo con ventana de contexto de hasta 2M tokens.",
        "is_live_capable": False,
        "is_default": False
    },
    {
        "id": "models/gemini-1.5-flash",
        "clean_id": "gemini-1.5-flash",
        "displayName": "Gemini 1.5 Flash [📝 FLASH REST]",
        "raw_displayName": "Gemini 1.5 Flash",
        "description": "Modelo ágil y económico para tareas de texto y visión por REST.",
        "is_live_capable": False,
        "is_default": False
    },
    {
        "id": "models/gemini-2.0-flash-thinking-exp-01-21",
        "clean_id": "gemini-2.0-flash-thinking-exp-01-21",
        "displayName": "Gemini 2.0 Flash Thinking [🧠 THINKING]",
        "raw_displayName": "Gemini 2.0 Flash Thinking",
        "description": "Modelo con cadena de pensamiento explícita (Chain-of-Thought) para problemas lógicos complejos.",
        "is_live_capable": False,
        "is_default": False
    }
]


def is_live_audio_model(model_name: str, supported_methods: Optional[List[str]] = None) -> bool:
    """
    Determina con certeza si un modelo soporta la API WebSocket Multimodal Live (BidiGenerateContent).
    """
    methods = [m.lower() for m in (supported_methods or [])]
    name_lower = model_name.lower().replace("models/", "")

    if "bidigeneratecontent" in methods:
        return True

    if any(ex in name_lower for ex in ["thinking", "pro", "embed", "8b", "1.5", "1.0", "bison", "aqa", "imagen"]):
        return False

    if any(k in name_lower for k in ["2.0-flash", "2.5-flash", "realtime", "exp-1206"]):
        return True

    return False


def format_model_entry(rm: Dict[str, Any], active_model: str) -> Dict[str, Any]:
    """Formatea la información de un modelo devuelto por Google AI Studio."""
    m_name = rm.get("name", "")
    clean_id = m_name.replace("models/", "")
    raw_disp = rm.get("displayName") or clean_id
    methods = rm.get("supportedGenerationMethods", [])

    is_live = is_live_audio_model(m_name, methods)

    if is_live:
        category = "live"
        category_label = "⚡ Live Audio & Streaming (WebSocket)"
        badge = " [⚡ LIVE AUDIO WS]"
    elif "thinking" in clean_id.lower():
        category = "thinking"
        category_label = "🧠 Razonamiento (Chain-of-Thought)"
        badge = " [🧠 THINKING]"
    elif "pro" in clean_id.lower():
        category = "pro"
        category_label = "🔬 Razonamiento Profundo & Gran Contexto"
        badge = " [🔬 PRO / REASONING]"
    elif "flash" in clean_id.lower() and "8b" in clean_id.lower():
        category = "flash_lite"
        category_label = "⚡ Ultra Rápido / Ligero"
        badge = " [⚡ LITE REST]"
    elif "flash" in clean_id.lower():
        category = "flash_standard"
        category_label = "⚡ Rápido & Multimodal (REST)"
        badge = " [📝 FLASH REST]"
    elif "embed" in clean_id.lower():
        category = "embedding"
        category_label = "📊 Vector Embedding"
        badge = " [📊 EMBEDDING]"
    else:
        category = "standard"
        category_label = "🤖 Generación de Contenido"
        badge = " [🤖 TEXT/VISION]"

    is_active = (
        m_name == active_model or
        clean_id == active_model or
        clean_id == active_model.replace("models/", "")
    )

    return {
        "id": m_name,
        "clean_id": clean_id,
        "displayName": f"{raw_disp}{badge}",
        "raw_displayName": raw_disp,
        "description": rm.get("description", "Modelo oficial de Google Generative AI."),
        "category": category,
        "category_label": category_label,
        "is_live_capable": is_live,
        "is_active": is_active,
        "input_token_limit": rm.get("inputTokenLimit"),
        "output_token_limit": rm.get("outputTokenLimit"),
        "supported_generation_methods": methods
    }


def model_sort_priority(m: Dict[str, Any]) -> tuple:
    """Prioriza modelos Live Audio primero, luego 2.5/2.0 Pro, luego 1.5, etc."""
    cid = m.get("clean_id", "").lower()
    is_live = m.get("is_live_capable", False)

    if is_live:
        if "2.5" in cid:
            ver = 0
        elif "2.0-flash-exp" in cid:
            ver = 1
        elif "2.0-flash-realtime" in cid:
            ver = 2
        elif "2.0-flash" in cid:
            ver = 3
        else:
            ver = 4
        return (0, ver, cid)

    if "2.5-pro" in cid:
        return (1, 0, cid)
    if "2.5" in cid:
        return (1, 1, cid)
    if "2.0-pro" in cid:
        return (2, 0, cid)
    if "1.5-pro" in cid:
        return (3, 0, cid)
    if "1.5-flash" in cid and "8b" not in cid:
        return (3, 1, cid)
    if "1.5-flash-8b" in cid:
        return (3, 2, cid)
    if "thinking" in cid:
        return (4, 0, cid)

    return (5, 0, cid)


class GeminiModelsManager:
    def __init__(self):
        self.active_model = os.getenv("GEMINI_MODEL", "models/gemini-2.0-flash-exp")
        if not self.active_model.startswith("models/"):
            self.active_model = f"models/{self.active_model}"

    def _fetch_remote_models(self, api_key: str) -> List[Dict[str, Any]]:
        """Consulta la API de Google AI Studio con soporte para paginación completa."""
        all_models: List[Dict[str, Any]] = []
        page_token = None

        while True:
            url = f"https://generativelanguage.googleapis.com/v1beta/models?pageSize=100&key={api_key}"
            if page_token:
                url += f"&pageToken={page_token}"

            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "VIERNES-Assistant/2.0",
                    "Accept": "application/json"
                }
            )

            try:
                with urllib.request.urlopen(req, timeout=10) as response:
                    if response.status != 200:
                        break
                    data = json.loads(response.read().decode("utf-8"))
                    models = data.get("models", [])
                    all_models.extend(models)

                    page_token = data.get("nextPageToken")
                    if not page_token or len(models) == 0:
                        break
            except urllib.error.HTTPError as he:
                logger.warning(f"HTTPError consultando Google AI Studio Models API: {he.code} {he.reason}")
                break
            except Exception as ex:
                logger.warning(f"Error en comunicación con Google AI Studio Models API: {ex}")
                break

        return all_models

    async def list_available_models(self, api_key: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Lista todos los modelos disponibles en Google AI Studio clasificados por capacidades.
        """
        target_key = (api_key if api_key is not None else os.getenv("GEMINI_API_KEY", "")).strip()

        # Si no hay key configurada o es un placeholder
        if not target_key or target_key.startswith("AIzaSyYour") or "..." in target_key:
            catalog = []
            for m in RECOMMENDED_MODELS:
                m_copy = dict(m)
                m_copy["is_active"] = (
                    m_copy["id"] == self.active_model or
                    m_copy.get("clean_id") == self.active_model.replace("models/", "")
                )
                catalog.append(m_copy)
            return sorted(catalog, key=model_sort_priority)

        loop = asyncio.get_running_loop()
        try:
            raw_models = await loop.run_in_executor(None, self._fetch_remote_models, target_key)
            formatted = []

            for rm in raw_models:
                m_name = rm.get("name", "")
                methods = rm.get("supportedGenerationMethods", [])

                is_generative = (
                    "generateContent" in methods or
                    "bidiGenerateContent" in methods or
                    "gemini" in m_name.lower()
                )
                if not is_generative or "embedding" in m_name.lower():
                    continue

                formatted.append(format_model_entry(rm, self.active_model))

            if formatted:
                formatted.sort(key=model_sort_priority)
                logger.info(f"✓ {len(formatted)} modelos recuperados y clasificados desde Google AI Studio.")
                return formatted

            catalog = []
            for m in RECOMMENDED_MODELS:
                m_copy = dict(m)
                m_copy["is_active"] = (
                    m_copy["id"] == self.active_model or
                    m_copy.get("clean_id") == self.active_model.replace("models/", "")
                )
                catalog.append(m_copy)
            return sorted(catalog, key=model_sort_priority)

        except Exception as e:
            logger.warning(f"Error consultando modelos oficiales en Google AI Studio ({e}). Usando catálogo base.")
            catalog = []
            for m in RECOMMENDED_MODELS:
                m_copy = dict(m)
                m_copy["is_active"] = (
                    m_copy["id"] == self.active_model or
                    m_copy.get("clean_id") == self.active_model.replace("models/", "")
                )
                catalog.append(m_copy)
            return sorted(catalog, key=model_sort_priority)

    def set_active_model(self, model_id: str) -> Dict[str, Any]:
        """Cambia el modelo activo de Gemini en memoria, entorno y configuración."""
        if not model_id.startswith("models/"):
            model_id = f"models/{model_id}"
        self.active_model = model_id
        os.environ["GEMINI_MODEL"] = model_id

        # Sincronizar en caliente con el módulo config y gemini_client
        try:
            from viernes import config
            config.GEMINI_MODEL = model_id
        except Exception:
            pass

        try:
            from viernes.core.gemini_live import gemini_client
            gemini_client.model_name = model_id
        except Exception:
            pass

        logger.info(f"✓ Modelo Gemini Live cambiado a: {model_id}")
        return {
            "success": True,
            "active_model": model_id,
            "message": f"Modelo cambiado a '{model_id}'"
        }


models_manager = GeminiModelsManager()
