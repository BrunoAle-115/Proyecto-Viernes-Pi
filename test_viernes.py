"""
Tests y verificación de esquemas y herramientas de V.I.E.R.N.E.S.
"""

import asyncio
import json
from viernes.tools_schema import GEMINI_TOOLS_DECLARATIONS, get_gemini_tools_payload
from viernes.tools_executor import dispatch_tool_call
from viernes.prompts import VIERNES_SYSTEM_PROMPT


def test_schemas_and_dispatch():
    async def _test():
        payload = get_gemini_tools_payload()
        assert len(payload) == 1
        funcs = payload[0]["functionDeclarations"]
        assert len(funcs) == 5
        names = [f["name"] for f in funcs]
        assert "wake_on_lan" in names
        assert "control_lights" in names
        assert "manage_alarms_timers" in names
        assert "check_emails" in names
        assert "github_operations" in names

        # Probar serialización JSON del setup
        json_str = json.dumps(payload)
        assert len(json_str) > 0

        # Test Wake-on-LAN
        res_wol = await dispatch_tool_call("wake_on_lan", {"mac_address": "00:11:22:33:44:55", "device_alias": "Taller"})
        assert res_wol["status"] == "success"

        # Test Lights
        res_light = await dispatch_tool_call("control_lights", {"action": "set_brightness", "room_or_device": "laboratorio", "brightness_pct": 50})
        assert res_light["status"] == "success"

        # Test Timers
        res_timer = await dispatch_tool_call("manage_alarms_timers", {"action": "set_timer", "duration_seconds": 60, "label": "Despliegue"})
        assert res_timer["status"] == "success"

        # Test Email
        res_email = await dispatch_tool_call("check_emails", {"folder": "INBOX", "unread_only": True, "limit": 2})
        assert res_email["status"] == "success"

        # Test GitHub
        res_gh = await dispatch_tool_call("github_operations", {"action": "get_repo_status", "repo": "StarkEnterprises/VIERNES-Core"})
        assert res_gh["status"] == "success"

        # Verificando System Prompt
        assert "V.I.E.R.N.E.S" in VIERNES_SYSTEM_PROMPT

    asyncio.run(_test())


if __name__ == "__main__":
    test_schemas_and_dispatch()
