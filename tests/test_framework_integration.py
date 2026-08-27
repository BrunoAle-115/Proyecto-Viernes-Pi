import asyncio
from datetime import datetime
import unittest

try:
    import pytest
except ImportError:
    class _MockPytest:
        class mark:
            @staticmethod
            def asyncio(f):
                return f
    pytest = _MockPytest()

from viernes.core.event_bus import bus, Event
from viernes.core.telemetry import SystemTelemetry
from viernes.core.tools_registry import ToolsDispatcher
from viernes.iot.network_scanner import NetworkScanner
from viernes.iot.wake_on_lan import WakeOnLanManager
from viernes.mail.ai_triage import EmailTriageEngine
from viernes.integrations.github_monitor import GitHubMonitor
from viernes.scheduler.reminder_engine import ReminderEngine
from viernes.telephony.sip_manager import SipManager


def test_event_bus():
    async def _test():
        received_events = []

        async def sample_listener(ev: Event):
            received_events.append(ev.data)

        bus.subscribe("test/topic", sample_listener)
        await bus.publish("test/topic", {"message": "Stark Labs Online"}, sender="pytest")
        await asyncio.sleep(0.05)

        assert len(received_events) == 1
        assert received_events[0]["message"] == "Stark Labs Online"

    asyncio.run(_test())


def test_telemetry():
    status = SystemTelemetry.get_full_status()
    assert "cpu" in status
    assert "ram" in status
    assert "local_ip" in status
    assert status["ai_status"] == "ONLINE"


def test_email_triage_promotions_and_spam():
    raw_emails = [
        {
            "sender": "ofertas@tienda.com",
            "subject": "¡50% de DESCUENTO en tecnología por Cyber Monday!",
            "snippet": "No te pierdas esta oferta única. Descuento imperdible.",
        },
        {
            "sender": "newsletter@marketing.cl",
            "subject": "Resumen semanal de noticias",
            "snippet": "Descubre las novedades de la semana. Unsubscribe aquí.",
        },
        {
            "sender": "cliente.empresa@gmail.com",
            "subject": "Urgente: Aprobación de presupuesto para producción",
            "snippet": "Hola Bruno, adjunto el contrato y factura para transferir el pago hoy.",
        },
    ]

    important = EmailTriageEngine.filter_important_emails(raw_emails)
    assert len(important) == 1
    assert "cliente.empresa" in important[0]["sender"]
    assert important[0]["triage"]["priority"] == "HIGH"


def test_wol_magic_packet_generation():
    wol = WakeOnLanManager()
    mac = "00:11:22:33:44:55"
    packet = wol._create_magic_packet(mac)
    assert len(packet) == 102
    assert packet.startswith(b"\xff" * 6)
    assert packet.count(bytes.fromhex("001122334455")) == 16


def test_tools_dispatcher_execution():
    async def _test():
        # Test Telemetría vía Dispatcher
        telemetry_res = await ToolsDispatcher.execute_tool("get_system_telemetry", {})
        assert "cpu" in telemetry_res
        assert "uptime" in telemetry_res

        # Test WoL Dispatcher con auto-resolución
        wol_res = await ToolsDispatcher.execute_tool("turn_on_pc", {"device_name": "pc_principal"})
        assert wol_res["success"] is True

        # Test Email Dispatcher
        mail_res = await ToolsDispatcher.execute_tool("get_important_emails", {"source": "all"})
        assert "total_important" in mail_res

    asyncio.run(_test())


def test_scheduler_add_alarm():
    async def _test():
        sched = ReminderEngine(db_path="data/test_viernes.db")
        res = await sched.add_reminder(
            title="Reunión de Arquitectura",
            remind_time="2026-08-27T10:00:00",
            is_alarm=False,
        )
        assert res["success"] is True
        assert res["title"] == "Reunión de Arquitectura"

    asyncio.run(_test())
