"""
Telemetría de Hardware y Sistema en Tiempo Real para Raspberry Pi 5 y entornos de desarrollo.
"""

import os
import time
import socket
import psutil
import logging
from typing import Dict, Any

logger = logging.getLogger("viernes.telemetry")

START_TIME = time.time()


class SystemTelemetry:
    @staticmethod
    def get_cpu_temp() -> float:
        """Obtiene la temperatura de la CPU en grados Celsius (Raspberry Pi 5 / Linux)."""
        # Método 1: Sysfs de Linux / Raspberry Pi
        thermal_path = "/sys/class/thermal/thermal_zone0/temp"
        if os.path.exists(thermal_path):
            try:
                with open(thermal_path, "r") as f:
                    temp_raw = f.read().strip()
                    return round(float(temp_raw) / 1000.0, 1)
            except Exception:
                pass

        # Método 2: psutil sensors_temperatures
        try:
            temps = psutil.sensors_temperatures()
            if temps:
                for name, entries in temps.items():
                    if entries:
                        return round(entries[0].current, 1)
        except Exception:
            pass

        return 42.5 # Valor simulado si se ejecuta en Windows/Mac sin sensores expuestos

    @staticmethod
    def get_local_ip() -> str:
        """Determina la IP local primaria del dispositivo."""
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # No envía tráfico real, solo resuelve ruta
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
        except Exception:
            ip = "127.0.0.1"
        finally:
            s.close()
        return ip

    @classmethod
    def get_full_status(cls) -> Dict[str, Any]:
        """Retorna un snapshot completo de telemetría del sistema para el HUD."""
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        uptime_seconds = int(time.time() - START_TIME)

        return {
            "timestamp": time.time(),
            "hostname": socket.gethostname(),
            "local_ip": cls.get_local_ip(),
            "cpu": {
                "percent": psutil.cpu_percent(interval=None),
                "cores": psutil.cpu_count(logical=True),
                "temperature_c": cls.get_cpu_temp(),
                "freq_mhz": psutil.cpu_freq().current if psutil.cpu_freq() else 2400.0,
            },
            "ram": {
                "total_mb": round(mem.total / (1024 * 1024), 1),
                "used_mb": round(mem.used / (1024 * 1024), 1),
                "percent": mem.percent,
            },
            "disk": {
                "total_gb": round(disk.total / (1024 * 1024 * 1024), 1),
                "free_gb": round(disk.free / (1024 * 1024 * 1024), 1),
                "percent": disk.percent,
            },
            "uptime": {
                "seconds": uptime_seconds,
                "formatted": f"{uptime_seconds // 3600:02d}:{(uptime_seconds % 3600) // 60:02d}:{uptime_seconds % 60:02d}",
            },
            "model": "Raspberry Pi 5 (8GB ARM64)",
            "ai_status": "ONLINE",
            "voice_state": "LISTENING",
        }
