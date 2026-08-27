"""
Tests de Telemetría y Monitoreo de Hardware para Raspberry Pi 5 (telemetry.py).
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import patch, mock_open
from viernes.core.telemetry import SystemTelemetry


def test_telemetry_snapshot_keys():
    status = SystemTelemetry.get_full_status()
    assert "timestamp" in status
    assert "hostname" in status
    assert "local_ip" in status
    assert "cpu" in status
    assert "ram" in status
    assert "swap" in status
    assert "disk" in status
    assert "throttling" in status
    assert "cooling" in status
    assert "network" in status
    assert "model" in status
    assert "Raspberry Pi 5" in status["model"]


def test_throttling_bitmask_decoder():
    # Simulamos vcgencmd devolviendo throttled=0x50005 (0x1 | 0x4 | 0x10000 | 0x40000)
    # 0x1: Under-voltage now
    # 0x4: Currently throttled
    # 0x10000: Under-voltage occurred
    # 0x40000: Throttling occurred
    with patch.object(SystemTelemetry, "_run_vcgencmd", return_value="throttled=0x50005"):
        res = SystemTelemetry.get_throttling_status()
        assert res["has_vcgencmd"] is True
        assert res["realtime"]["under_voltage"] is True
        assert res["realtime"]["currently_throttled"] is True
        assert res["historical"]["under_voltage_occurred"] is True
        assert res["historical"]["throttling_occurred"] is True
        assert res["health"] == "CRITICAL_THROTTLED"

    # Caso óptimo: throttled=0x0
    with patch.object(SystemTelemetry, "_run_vcgencmd", return_value="throttled=0x0"):
        res = SystemTelemetry.get_throttling_status()
        assert res["has_vcgencmd"] is True
        assert res["health"] == "OPTIMAL"
        assert res["realtime"]["currently_throttled"] is False


def test_cpu_temp_vcgencmd_fallback():
    # Caso 1: vcgencmd disponible
    with patch.object(SystemTelemetry, "_run_vcgencmd", return_value="temp=58.4'C"):
        temp = SystemTelemetry.get_cpu_temp()
        assert temp == 58.4

    # Caso 2: fallback sysfs
    with patch.object(SystemTelemetry, "_run_vcgencmd", return_value=None):
        with patch("os.path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data="62500\n")):
                temp = SystemTelemetry.get_cpu_temp()
                assert temp == 62.5
