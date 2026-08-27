"""
Tests automatizados exhaustivos para el Despachador de Herramientas (tools_registry.py).
Valida:
1. Cumplimiento de esquema OpenAPI / Gemini Schema en GEMINI_TOOL_DECLARATIONS.
2. Ejecución integral de las herramientas disponibles en ToolsDispatcher.
3. Manejo de herramientas desconocidas y errores de ejecución no controlados.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from viernes.core.tools_registry import ToolsDispatcher, GEMINI_TOOL_DECLARATIONS


def test_gemini_tool_declarations_schema_integrity():
    """Valida que todas las herramientas declaradas tengan esquema JSON válido para Gemini Live."""
    assert len(GEMINI_TOOL_DECLARATIONS) >= 15

    for tool in GEMINI_TOOL_DECLARATIONS:
        assert "name" in tool and isinstance(tool["name"], str)
        assert "description" in tool and len(tool["description"]) > 10
        assert "parameters" in tool
        params = tool["parameters"]
        assert params.get("type") == "OBJECT"
        assert "properties" in params and isinstance(params["properties"], dict)
        if "required" in params:
            assert isinstance(params["required"], list)
            for req in params["required"]:
                assert req in params["properties"], f"Campo requerido '{req}' no definido en propiedades de {tool['name']}"


def test_tools_dispatcher_hardware_and_iot_tools():
    """Valida las herramientas de hardware, WoL, luces WiZ y climatización AIRSYS."""
    async def _test():
        # 1. Wake-on-LAN
        res_wol = await ToolsDispatcher.execute_tool("turn_on_pc", {"device_name": "pc_principal"})
        assert res_wol.get("success") is True

        # 2. Control de luces WiZ
        res_light = await ToolsDispatcher.execute_tool("control_smart_light", {
            "target": "luz_wiz",
            "action": "palette",
            "palette": "relax",
            "brightness": 80
        })
        assert "params" in res_light

        # 3. Consulta de estado de luz WiZ (getPilot)
        with patch("viernes.iot.device_manager.device_mgr.execute_get_light_status", new_callable=AsyncMock) as mock_pilot:
            mock_pilot.return_value = {"online": True, "state": "on", "summary": "Luz WiZ encendida a 80% cálido."}
            res_palette = await ToolsDispatcher.execute_tool("get_smart_light_palette", {"target": "luz_wiz"})
            assert res_palette["success"] is True
            assert "80% cálido" in res_palette["voice_response"]

        # 4. Control de Aire Acondicionado AIRSYS
        res_ac = await ToolsDispatcher.execute_tool("control_air_conditioner", {
            "target": "aire_ac",
            "power": True,
            "temperature": 22,
            "mode": "cool",
            "fan_speed": "high"
        })
        assert res_ac["success"] is True
        assert res_ac["target_temp"] == 22

        # 5. Modo Frutifantástico
        res_party = await ToolsDispatcher.execute_tool("trigger_frutifantastico_mode", {"track": "blinding_lights"})
        assert res_party["success"] is True
        assert "Frutifantástico" in res_party["voice_response"]

        # 6. Android TV / Google Cast
        with patch("viernes.iot.android_tv_cast.cast_controller.launch_youtube_video", new_callable=AsyncMock) as mock_cast:
            mock_cast.return_value = True
            res_tv = await ToolsDispatcher.execute_tool("control_android_tv", {
                "command": "play_youtube",
                "youtube_id": "4NRXx6U8ABQ",
                "target_ip": "192.168.100.25"
            })
            assert res_tv["success"] is True

    asyncio.run(_test())


def test_tools_dispatcher_intelligence_and_info_tools():
    """Valida las herramientas de Noticias de Chile, Clima, RAG Personal, Telemetría y GitHub."""
    async def _test():
        # 1. Noticias de Chile
        res_news = await ToolsDispatcher.execute_tool("get_chile_news", {"limit": 3})
        assert res_news["success"] is True
        assert res_news["count"] >= 1
        assert "voice_summary" in res_news

        # 2. Clima y probabilidad de lluvia
        res_weather = await ToolsDispatcher.execute_tool("get_weather_forecast", {"city": "santiago"})
        assert res_weather["success"] is True
        assert "weather" in res_weather

        # 3. Memoria RAG Vectorial
        res_mem_store = await ToolsDispatcher.execute_tool("store_personal_memory", {
            "category": "preference",
            "key_concept": "editor_favorito",
            "content": "A Bruno le gusta desarrollar con Neovim y VS Code en Ubuntu."
        })
        assert res_mem_store["success"] is True

        res_mem_recall = await ToolsDispatcher.execute_tool("recall_personal_memory", {
            "query": "editor preferido de Bruno"
        })
        assert res_mem_recall["success"] is True

        # 4. Telemetría de la Raspberry Pi 5
        res_telem = await ToolsDispatcher.execute_tool("get_system_telemetry", {})
        assert "cpu" in res_telem
        assert "ram" in res_telem
        assert "local_ip" in res_telem

        # 5. Estado de Pull Requests en GitHub
        res_gh = await ToolsDispatcher.execute_tool("check_github_status", {})
        assert "total_prs" in res_gh or "prs" in res_gh

    asyncio.run(_test())


def test_tools_dispatcher_communications_and_scheduler():
    """Valida correo electrónico filtrado, alarmas/recordatorios y telefonía SIP."""
    async def _test():
        # 1. Correos importantes
        res_mail = await ToolsDispatcher.execute_tool("get_important_emails", {"source": "all"})
        assert res_mail["success"] is True
        assert "total_important" in res_mail

        # 2. Programación de recordatorio
        res_rem = await ToolsDispatcher.execute_tool("set_alarm_or_reminder", {
            "title": "Revisión de Seguridad",
            "time_iso": "2026-08-27T18:00:00",
            "is_alarm": False
        })
        assert res_rem["success"] is True

        # 3. Llamada telefónica SIP en Chile
        with patch("viernes.telephony.sip_manager.sip_mgr.originate_call", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = {"success": True, "call_id": "sip-call-777", "phone": "+56912345678"}
            res_sip = await ToolsDispatcher.execute_tool("make_phone_call", {
                "phone_number": "+56912345678",
                "reason": "Alerta crítica de laboratorio"
            })
            assert res_sip["success"] is True
            assert res_sip["call_id"] == "sip-call-777"

    asyncio.run(_test())


def test_tools_dispatcher_error_handling():
    """Valida el manejo seguro de herramientas inexistentes y captura de excepciones."""
    async def _test():
        # 1. Herramienta no reconocida
        res_unknown = await ToolsDispatcher.execute_tool("herramienta_fantasma_inexistente", {})
        assert res_unknown["success"] is False
        assert "no reconocida" in res_unknown["error"]

        # 2. Excepción interna en subsistema
        with patch("viernes.core.telemetry.SystemTelemetry.get_full_status", side_effect=RuntimeError("Fallo simulado en telemetría")):
            res_err = await ToolsDispatcher.execute_tool("get_system_telemetry", {})
            assert res_err["success"] is False
            assert "Fallo simulado en telemetría" in res_err["error"]

    asyncio.run(_test())
