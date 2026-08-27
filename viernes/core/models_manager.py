"""
Gestor de Modelos de Gemini API y Live Flash para V.I.E.R.N.E.S.
Permite listar dinámicamente los modelos disponibles en Google AI Studio y conmutar el modelo activo.
"""

import os
import json
import urllib.request
import logging
import asyncio
from typing import List, Dict, Any, Optional

logger = logging.getLogger("viernes.models")

# Modelos recomendados y conocidos para Gemini Live y Streaming
RECOMMENDED_MODELS = [
    {
        "id": "models/gemini-2.0-flash-exp",
        "displayName": "Gemini 2.0 Flash (Live Audio-to-Audio / Dev Free Tier)",
        "description": "Modelo de streaming multimodal bidireccional de ultra-baja latencia para voz.",
        "is_live_capable": True,
        "is_default": True
    },
    {
        "id": "models/gemini-2.0-flash",
        "displayName": "Gemini 2.0 Flash Standard",
        "description": "Modelo de alto rendimiento y velocidad para tareas y function calling.",
        "is_live_capable": True,
        "is_default": False
    },
    {
        "id": "models/gemini-1.5-flash",
        "displayName": "Gemini 1.5 Flash",
        "description": "Modelo ligero y rápido para análisis y respuestas de texto.",
        "is_live_capable": False,
        "is_default": False
    },
    {
        "id": "models/gemini-1.5-pro",
        "displayName": "Gemini 1.5 Pro",
        "description": "Modelo de razonamiento profundo y contexto ultra-largo.",
        "is_live_capable": False,
        "is_default": False
    }
]


class GeminiModelsManager:
    def __init__(self):
        self.active_model = os.getenv("GEMINI_MODEL", "models/gemini-2.0-flash-exp")

    def _fetch_remote_models(self, api_key: str) -> List[Dict[str, Any]]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        req = urllib.request.Request(url, headers={"User-Agent": "VIERNES-Assistant/2.0"})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            return data.get("models", [])

    async def list_available_models(self, api_key: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lista todos los modelos oficiales disponibles consultando a la API de Google AI Studio."""
        target_key = (api_key or os.getenv("GEMINI_API_KEY", "")).strip()
        if not target_key or target_key.startswith("AIzaSyYour") or target_key.startswith("AIzaSy..."):
            # Si no hay key válida, retornar catálogo base con selector activo
            for m in RECOMMENDED_MODELS:
                m["is_active"] = (m["id"] == self.active_model)
            return RECOMMENDED_MODELS

        loop = asyncio.get_running_loop()
        try:
            raw_models = await loop.run_in_executor(None, self._fetch_remote_models, target_key)
            formatted = []
            for rm in raw_models:
                m_name = rm.get("name", "")
                if "gemini" in m_name.lower():
                    clean_id = m_name.replace("models/", "")
                    disp_name = rm.get("displayName") or clean_id
                    is_live = "flash" in m_name.lower() or "2.0" in m_name.lower() or "exp" in m_name.lower()
                    formatted.append({
                        "id": m_name,
                        "clean_id": clean_id,
                        "displayName": f"{disp_name} ({clean_id})",
                        "description": rm.get("description", "Modelo oficial de Google AI Studio."),
                        "is_live_capable": is_live,
                        "is_active": (m_name == self.active_model or clean_id == self.active_model.replace("models/", "")),
                        "supported_generation_methods": rm.get("supportedGenerationMethods", [])
                    })
            if formatted:
                logger.info(f"✓ {len(formatted)} modelos oficiales recuperados de Google AI Studio.")
                return formatted
            return RECOMMENDED_MODELS
        except Exception as e:
            logger.warning(f"Error consultando modelos oficiales en Google AI Studio ({e}). Usando catálogo base.")
            for m in RECOMMENDED_MODELS:
                m["is_active"] = (m["id"] == self.active_model)
            return RECOMMENDED_MODELS

    def set_active_model(self, model_id: str) -> Dict[str, Any]:
        """Cambia el modelo activo de Gemini en memoria."""
        if not model_id.startswith("models/"):
            model_id = f"models/{model_id}"
        self.active_model = model_id
        os.environ["GEMINI_MODEL"] = model_id
        logger.info(f"Modelo Gemini Live cambiado a: {model_id}")
        return {"success": True, "active_model": model_id, "message": f"Modelo cambiado a '{model_id}'"}


models_manager = GeminiModelsManager()
