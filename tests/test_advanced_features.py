"""
Tests de Verificación de Capacidades Avanzadas de V.I.E.R.N.E.S. 2.0
(Autenticación, Recuperación CLI, Clima, Noticias, Mini-RAG y Gestor de Modelos).
"""

import sys
import tempfile
import shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import asyncio
from viernes.auth.manager import AuthManager, DEFAULT_ADMIN_EMAIL, DEFAULT_ADMIN_PASSWORD_RAW
from viernes.services.weather_engine import WeatherEngine
from viernes.services.news_chile import ChileNewsEngine
from viernes.memory.mini_rag import PersonalRAG
from viernes.core.models_manager import GeminiModelsManager
from viernes.core.tools_registry import ToolsDispatcher


def test_auth_and_cli_password_recovery():
    temp_dir = tempfile.mkdtemp()
    test_db = str(Path(temp_dir) / "test_users.db")

    try:
        mgr = AuthManager(db_path=test_db)

        # 1. Login exitoso con credenciales sembradas
        token = mgr.authenticate(DEFAULT_ADMIN_EMAIL, DEFAULT_ADMIN_PASSWORD_RAW)
        assert token is not None
        assert len(token) > 20

        # 2. Login fallido con password erróneo
        bad_token = mgr.authenticate(DEFAULT_ADMIN_EMAIL, "clave_incorrecta")
        assert bad_token is None

        # 3. Recuperación de contraseña exclusiva por CLI
        reset_ok = mgr.reset_password(DEFAULT_ADMIN_EMAIL, "nueva_pass_cli_2026_stark")
        assert reset_ok is True

        # 4. Probar nuevo login
        new_token = mgr.authenticate(DEFAULT_ADMIN_EMAIL, "nueva_pass_cli_2026_stark")
        assert new_token is not None
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_weather_engine_and_rain():
    async def _test():
        forecast = await WeatherEngine.get_forecast("santiago")
        assert "current_temp" in forecast
        assert "city" in forecast
        assert "will_rain" in forecast
        assert "hourly" in forecast

        voice_summary = await WeatherEngine.get_voice_weather_summary("santiago")
        assert "Santiago" in voice_summary

    asyncio.run(_test())


def test_chile_news_engine():
    async def _test():
        news = await ChileNewsEngine.get_top_news(limit=3)
        assert len(news) >= 1
        assert "title" in news[0]
        assert "source" in news[0]

        voice_briefing = await ChileNewsEngine.get_voice_news_briefing()
        assert len(voice_briefing) > 10

    asyncio.run(_test())


def test_mini_rag_personal_memory():
    async def _test():
        temp_dir = tempfile.mkdtemp()
        test_mem_db = str(Path(temp_dir) / "test_memory.db")

        try:
            rag = PersonalRAG(db_path=test_mem_db)

            # Guardar memoria
            res = await rag.store_memory(
                category="preference",
                key_concept="cafe_favorito",
                content="A Bruno le gusta el café espresso doble sin azúcar por la mañana."
            )
            assert res["success"] is True

            # Recuperar memoria
            recalled = await rag.recall_memories("café")
            assert len(recalled) >= 1
            assert "espresso doble" in recalled[0]["content"]
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    asyncio.run(_test())


def test_gemini_models_manager():
    async def _test():
        mgr = GeminiModelsManager()
        models = await mgr.list_available_models()
        assert len(models) >= 1
        assert any("gemini-2.0-flash" in m["id"] for m in models)

        # Conmutar modelo
        switch_res = mgr.set_active_model("models/gemini-2.0-flash")
        assert switch_res["success"] is True
        assert mgr.active_model == "models/gemini-2.0-flash"

    asyncio.run(_test())


def test_advanced_tools_dispatcher():
    async def _test():
        # Test tool noticias
        res_news = await ToolsDispatcher.execute_tool("get_chile_news", {"limit": 2})
        assert res_news["success"] is True

        # Test tool clima
        res_weather = await ToolsDispatcher.execute_tool("get_weather_forecast", {"city": "santiago"})
        assert res_weather["success"] is True

        # Test tool memoria RAG
        res_mem = await ToolsDispatcher.execute_tool("store_personal_memory", {
            "category": "routine",
            "key_concept": "gym_time",
            "content": "Bruno va al gimnasio de lunes a jueves a las 19:00."
        })
        assert res_mem["success"] is True

        # Test tool WiZ con paleta
        res_wiz = await ToolsDispatcher.execute_tool("control_smart_light", {
            "target": "luz_wiz",
            "action": "palette",
            "palette": "cálida",
            "brightness": 80
        })
        assert "params" in res_wiz
        assert res_wiz["params"]["temp"] == 2700

        # Test tool AC AIRSYS
        res_ac = await ToolsDispatcher.execute_tool("control_air_conditioner", {
            "target": "aire_ac",
            "power": True,
            "temperature": 21,
            "mode": "cool"
        })
        assert res_ac["success"] is True
        assert res_ac["target_temp"] == 21

    asyncio.run(_test())


def test_wiz_light_and_palette_control():
    from viernes.iot.smart_lights import SmartDeviceController, WIZ_SCENES, COLOR_PALETTES

    async def _test():
        # 1. Probar paleta cálida (temp 2700K)
        res_warm = await SmartDeviceController.control_wiz_light("192.168.100.15", palette="cálida", dimming=75)
        assert res_warm["params"]["temp"] == 2700
        assert res_warm["params"]["dimming"] == 75

        # 2. Probar paleta fría (temp 6500K)
        res_cool = await SmartDeviceController.control_wiz_light("192.168.100.15", palette="fría")
        assert res_cool["params"]["temp"] == 6500

        # 3. Probar escena relax / fiesta
        res_relax = await SmartDeviceController.control_wiz_light("192.168.100.15", palette="relax")
        assert res_relax["params"]["sceneId"] == WIZ_SCENES["relax"]

        # 4. Probar color RGB (rojo)
        res_red = await SmartDeviceController.control_wiz_light("192.168.100.15", palette="rojo")
        assert res_red["params"]["r"] == 255
        assert res_red["params"]["g"] == 0

    asyncio.run(_test())


def test_airsys_ac_control():
    from viernes.iot.smart_lights import SmartDeviceController

    async def _test():
        res = await SmartDeviceController.control_air_conditioner(
            "192.168.100.20", power=True, target_temp=23, mode="cool", fan_speed="auto"
        )
        assert res["success"] is True
        assert res["target_temp"] == 23
        assert res["mode"] == "cool"
        assert "AIRSYS" in res["message"]

    asyncio.run(_test())


def test_dynamic_subnet_detection():
    from viernes.iot.network_scanner import NetworkScanner
    scanner = NetworkScanner()
    subnet = scanner.detect_active_subnet()
    assert "/24" in subnet
    assert subnet.count(".") == 3

