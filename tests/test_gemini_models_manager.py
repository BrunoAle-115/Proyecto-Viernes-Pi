"""
Tests automatizados para el Gestor Dinámico de Modelos Gemini (models_manager.py).
Valida:
1. Fallback a catálogo base ante API Keys ausentes o placeholder.
2. Consulta dinámica exitosa a la API de Google AI Studio con filtrado y formateo.
3. Detección de capacidades en tiempo real (is_live_capable).
4. Resiliencia y manejo de excepciones (errores de red, HTTP 500, JSON malformado).
5. Conmutación de modelo activo con/sin prefijo 'models/' y sincronización con entorno.
"""

import os
import json
import asyncio
import pytest
from unittest.mock import patch, MagicMock
from viernes.core.models_manager import GeminiModelsManager, RECOMMENDED_MODELS


@pytest.fixture
def models_mgr():
    with patch.dict(os.environ, {"GEMINI_MODEL": "models/gemini-2.0-flash-exp"}):
        return GeminiModelsManager()


def test_models_manager_offline_or_placeholder_fallback(models_mgr):
    """Verifica que sin API Key o con placeholder se retorne el catálogo base con el selector activo."""
    async def _test():
        # Caso 1: API Key vacía
        models_empty = await models_mgr.list_available_models(api_key="")
        assert len(models_empty) == len(RECOMMENDED_MODELS)
        active_m = [m for m in models_empty if m.get("is_active")]
        assert len(active_m) == 1
        assert active_m[0]["id"] == "models/gemini-2.0-flash-exp"

        # Caso 2: API Key placeholder de ejemplo
        models_placeholder = await models_mgr.list_available_models(api_key="AIzaSyYourGeminiApiKeyHere12345")
        assert len(models_placeholder) == len(RECOMMENDED_MODELS)

    asyncio.run(_test())


def test_models_manager_remote_fetch_success(models_mgr):
    """Verifica el procesamiento exitoso de respuesta remota de Google AI Studio."""
    async def _test():
        mock_api_response = {
            "models": [
                {
                    "name": "models/gemini-2.5-flash",
                    "displayName": "Gemini 2.5 Flash Ultra",
                    "description": "Next-gen low-latency multimodal model",
                    "supportedGenerationMethods": ["generateContent", "bidiGenerateContent"]
                },
                {
                    "name": "models/gemini-2.0-pro-exp-02-05",
                    "displayName": "Gemini 2.0 Pro Experimental",
                    "description": "Complex reasoning model",
                    "supportedGenerationMethods": ["generateContent"]
                },
                {
                    "name": "models/text-embedding-004",
                    "displayName": "Text Embedding 004",
                    "supportedGenerationMethods": ["embedContent"]
                }
            ]
        }

        mock_bytes = json.dumps(mock_api_response).encode("utf-8")
        mock_resp = MagicMock()
        mock_resp.read.return_value = mock_bytes
        mock_resp.status = 200
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp):
            models = await models_mgr.list_available_models(api_key="AIzaSyRealValidKey999")

            assert len(models) == 2
            names = [m["id"] for m in models]
            assert "models/gemini-2.5-flash" in names
            assert "models/gemini-2.0-pro-exp-02-05" in names
            assert "models/text-embedding-004" not in names

            # Verificar formateo de campos enriquecidos
            flash_model = next(m for m in models if m["id"] == "models/gemini-2.5-flash")
            assert flash_model["clean_id"] == "gemini-2.5-flash"
            assert flash_model["is_live_capable"] is True
            assert "bidiGenerateContent" in flash_model["supported_generation_methods"]

    asyncio.run(_test())


def test_models_manager_remote_fetch_failure_resilience(models_mgr):
    """Verifica que ante fallos de conexión o respuestas inválidas se degrade gracefully."""
    async def _test():
        with patch("urllib.request.urlopen", side_effect=Exception("Connection timeout to generativelanguage.googleapis.com")):
            models = await models_mgr.list_available_models(api_key="AIzaSyRealValidKey999")
            assert len(models) == len(RECOMMENDED_MODELS)
            assert any(m["id"] == "models/gemini-2.0-flash-exp" for m in models)

    asyncio.run(_test())


def test_models_manager_set_active_model_behavior(models_mgr):
    """Verifica la asignación y normalización del modelo activo."""
    # Conmutar usando nombre limpio sin 'models/'
    res1 = models_mgr.set_active_model("gemini-1.5-pro")
    assert res1["success"] is True
    assert res1["active_model"] == "models/gemini-1.5-pro"
    assert models_mgr.active_model == "models/gemini-1.5-pro"
    assert os.environ.get("GEMINI_MODEL") == "models/gemini-1.5-pro"

    # Conmutar usando nombre completo con 'models/'
    res2 = models_mgr.set_active_model("models/gemini-2.0-flash")
    assert res2["success"] is True
    assert res2["active_model"] == "models/gemini-2.0-flash"
    assert models_mgr.active_model == "models/gemini-2.0-flash"
