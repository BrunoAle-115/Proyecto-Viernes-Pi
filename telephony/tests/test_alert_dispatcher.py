import sys
from pathlib import Path

import asyncio
from unittest.mock import AsyncMock, MagicMock
import pytest
from telephony.telephony_engine.alert_dispatcher import AlertDispatcher, AlertPriority, AlertCallState


def test_alert_enqueue_and_validation():
    async def _run():
        mock_ari = MagicMock()
        mock_ari.app_name = "viernes-voice"
        mock_ari.originate_call = AsyncMock(return_value={"id": "mock_chan_123"})
        mock_ari.play_audio = AsyncMock(return_value="play_1")
        mock_ari.hangup_channel = AsyncMock(return_value=True)

        dispatcher = AlertDispatcher(mock_ari, caller_id_cl="+56912345678")

        # Intentar encolar con número inválido
        success_invalid = await dispatcher.trigger_alert("alt-1", "123", "Alerta test")
        assert success_invalid is False

        # Encolar número móvil chileno válido
        success_valid = await dispatcher.trigger_alert("alt-2", "+56987654321", "Alerta intrusión")
        assert success_valid is True
        assert "alt-2" in dispatcher.active_alerts

        # Probar recepción de DTMF '1' (acuse de recibo)
        task = dispatcher.active_alerts["alt-2"]
        task.channel_id = "mock_chan_123"
        await dispatcher.handle_dtmf_input("alt-2", "1")

        assert task.state == AlertCallState.ACKNOWLEDGED
        assert task.acknowledged_at is not None
        mock_ari.play_audio.assert_awaited()

    asyncio.run(_run())
