"""
Telemetría de Hardware y Sistema en Tiempo Real para Raspberry Pi 5 y entornos de desarrollo.
Optimizado para arquitectura BCM2712 (ARM Cortex-A76), detección de Thermal Throttling,
monitoreo de vcgencmd, gestión de Swap/RAM y métricas de conectividad de red.
"""

import os
import time
import socket
import psutil
import logging
import subprocess
import shutil
from typing import Dict, Any, Optional

logger = logging.getLogger("viernes.telemetry")

START_TIME = time.time()


class SystemTelemetry:
    @staticmethod
    def _run_vcgencmd(command: str) -> Optional[str]:
        """Ejecuta un comando vcgencmd de forma segura en Raspberry Pi OS."""
        if not shutil.which("vcgencmd"):
            return None
        try:
            res = subprocess.run(
                ["vcgencmd", command],
                capture_output=True,
                text=True,
                timeout=0.6,
                check=False
            )
            if res.returncode == 0:
                return res.stdout.strip()
        except Exception as e:
            logger.debug(f"vcgencmd {command} fallo: {e}")
        return None

    @classmethod
    def get_cpu_temp(cls) -> float:
        """
        Obtiene la temperatura del SoC en grados Celsius.
        Prioriza:
        1. vcgencmd measure_temp (Firmware VideoCore / PMIC Raspberry Pi 5)
        2. Sysfs thermal_zone0
        3. psutil sensors_temperatures
        4. Simulado para entornos de desarrollo (Windows/Mac)
        """
        # Método 1: vcgencmd measure_temp (e.g. "temp=47.5'C")
        vc_out = cls._run_vcgencmd("measure_temp")
        if vc_out and "temp=" in vc_out:
            try:
                raw = vc_out.replace("temp=", "").replace("'C", "").strip()
                return round(float(raw), 1)
            except Exception:
                pass

        # Método 2: Sysfs de Linux / Raspberry Pi 5 (/sys/class/thermal/thermal_zone0/temp)
        thermal_path = "/sys/class/thermal/thermal_zone0/temp"
        if os.path.exists(thermal_path):
            try:
                with open(thermal_path, "r") as f:
                    temp_raw = f.read().strip()
                    return round(float(temp_raw) / 1000.0, 1)
            except Exception:
                pass

        # Método 3: psutil sensors_temperatures
        try:
            temps = psutil.sensors_temperatures()
            if temps:
                for name, entries in temps.items():
                    if entries:
                        return round(entries[0].current, 1)
        except Exception:
            pass

        return 42.5  # Valor de laboratorio simulado para entornos host sin sensor térmico directo

    @classmethod
    def get_throttling_status(cls) -> Dict[str, Any]:
        """
        Consulta y decodifica el bitmask de vcgencmd get_throttled en Raspberry Pi.
        Detecta subtensión (Under-voltage), estrangulamiento térmico (Thermal Throttling)
        y soft temperature limits (80°C en Pi 5).
        """
        vc_out = cls._run_vcgencmd("get_throttled")
        raw_code = 0
        has_vcgencmd = False

        if vc_out and "throttled=" in vc_out:
            try:
                hex_str = vc_out.replace("throttled=", "").strip()
                raw_code = int(hex_str, 16)
                has_vcgencmd = True
            except Exception:
                pass

        # Decodificación estándar de flags de Raspberry Pi OS
        # Estado en tiempo real:
        under_voltage_now = bool(raw_code & 0x1)
        arm_freq_capped_now = bool(raw_code & 0x2)
        throttled_now = bool(raw_code & 0x4)
        soft_temp_limit_now = bool(raw_code & 0x8)

        # Registro histórico acumulado desde el encendido:
        under_voltage_occurred = bool(raw_code & 0x10000)
        arm_freq_capped_occurred = bool(raw_code & 0x20000)
        throttled_occurred = bool(raw_code & 0x40000)
        soft_temp_limit_occurred = bool(raw_code & 0x80000)

        # Estado global resumido
        if throttled_now:
            health = "CRITICAL_THROTTLED"
        elif soft_temp_limit_now:
            health = "WARNING_SOFT_TEMP_LIMIT"
        elif under_voltage_now:
            health = "CRITICAL_UNDERVOLTAGE"
        elif arm_freq_capped_now:
            health = "WARNING_FREQ_CAPPED"
        elif throttled_occurred or soft_temp_limit_occurred:
            health = "WARNING_THROTTLED_IN_PAST"
        elif under_voltage_occurred:
            health = "WARNING_UNDERVOLTAGE_IN_PAST"
        else:
            health = "OPTIMAL"

        return {
            "has_vcgencmd": has_vcgencmd,
            "raw_hex": hex(raw_code),
            "health": health,
            "realtime": {
                "under_voltage": under_voltage_now,
                "arm_frequency_capped": arm_freq_capped_now,
                "currently_throttled": throttled_now,
                "soft_temp_limit_active": soft_temp_limit_now,
            },
            "historical": {
                "under_voltage_occurred": under_voltage_occurred,
                "arm_frequency_capped_occurred": arm_freq_capped_occurred,
                "throttling_occurred": throttled_occurred,
                "soft_temp_limit_occurred": soft_temp_limit_occurred,
            }
        }

    @classmethod
    def get_cpu_freq_and_volts(cls) -> Dict[str, Any]:
        """Obtiene la frecuencia real en MHz de los cores Cortex-A76 y voltaje del SoC."""
        freq_mhz = 2400.0  # Frecuencia nominal base Raspberry Pi 5
        voltage_v = 0.85

        # Frecuencia via sysfs (/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq)
        cur_freq_path = "/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq"
        if os.path.exists(cur_freq_path):
            try:
                with open(cur_freq_path, "r") as f:
                    freq_mhz = round(float(f.read().strip()) / 1000.0, 1)
            except Exception:
                pass
        else:
            # Fallback psutil
            try:
                cpu_f = psutil.cpu_freq()
                if cpu_f and cpu_f.current > 0:
                    freq_mhz = round(cpu_f.current, 1)
            except Exception:
                pass

        # Frecuencia via vcgencmd measure_clock arm
        vc_clock = cls._run_vcgencmd("measure_clock arm")
        if vc_clock and "frequency(" in vc_clock:
            try:
                raw_hz = vc_clock.split("=")[-1].strip()
                freq_mhz = round(float(raw_hz) / 1_000_000.0, 1)
            except Exception:
                pass

        # Voltaje via vcgencmd measure_volts core
        vc_volts = cls._run_vcgencmd("measure_volts core")
        if vc_volts and "volt=" in vc_volts:
            try:
                raw_v = vc_volts.replace("volt=", "").replace("V", "").strip()
                voltage_v = round(float(raw_v), 3)
            except Exception:
                pass

        return {
            "freq_mhz": freq_mhz,
            "voltage_v": voltage_v
        }

    @staticmethod
    def get_fan_speed() -> Dict[str, Any]:
        """
        Monitorea el estado del Raspberry Pi 5 Active Cooler / ventilador PWM oficial.
        Lee RPM o nivel de refrigeración desde el kernel sysfs.
        """
        cur_state_path = "/sys/class/thermal/cooling_device0/cur_state"
        cooling_level = 0
        fan_rpm = None

        if os.path.exists(cur_state_path):
            try:
                with open(cur_state_path, "r") as f:
                    cooling_level = int(f.read().strip())
            except Exception:
                pass

        hwmon_base = "/sys/devices/platform/cooling_fan/hwmon"
        if os.path.exists(hwmon_base):
            try:
                for entry in os.listdir(hwmon_base):
                    rpm_path = os.path.join(hwmon_base, entry, "fan1_input")
                    if os.path.exists(rpm_path):
                        with open(rpm_path, "r") as f:
                            fan_rpm = int(f.read().strip())
                        break
            except Exception:
                pass

        return {
            "cooling_level": cooling_level,
            "fan_rpm": fan_rpm,
            "status": "ACTIVE" if (cooling_level > 0 or (fan_rpm and fan_rpm > 0)) else "IDLE"
        }

    @staticmethod
    def get_local_ip() -> str:
        """Determina la IP local primaria del dispositivo sin generar tráfico de red real."""
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
        except Exception:
            ip = "127.0.0.1"
        finally:
            s.close()
        return ip

    @staticmethod
    def get_network_details() -> Dict[str, Any]:
        """
        Obtiene estadísticas de rendimiento de red, interfaces activas,
        tasas de E/S acumuladas y conteo de errores/paquetes descartados.
        """
        net_io = psutil.net_io_counters()
        interfaces = {}

        try:
            addrs = psutil.net_if_addrs()
            stats = psutil.net_if_stats()
            for iface_name, iface_addrs in addrs.items():
                is_up = stats[iface_name].isup if iface_name in stats else False
                speed_mbps = stats[iface_name].speed if iface_name in stats else 0
                ipv4 = None
                for addr in iface_addrs:
                    if addr.family == socket.AF_INET and not addr.address.startswith("127."):
                        ipv4 = addr.address
                        break
                if ipv4 or is_up:
                    interfaces[iface_name] = {
                        "ip": ipv4 or "N/A",
                        "is_up": is_up,
                        "speed_mbps": speed_mbps,
                    }
        except Exception:
            pass

        return {
            "bytes_sent_mb": round(net_io.bytes_sent / (1024 * 1024), 2),
            "bytes_recv_mb": round(net_io.bytes_recv / (1024 * 1024), 2),
            "packets_sent": net_io.packets_sent,
            "packets_recv": net_io.packets_recv,
            "errin": net_io.errin,
            "errout": net_io.errout,
            "dropin": net_io.dropin,
            "dropout": net_io.dropout,
            "interfaces": interfaces
        }

    @classmethod
    def get_full_status(cls) -> Dict[str, Any]:
        """
        Retorna un snapshot integral de telemetría del sistema, hardware,
        térmica, memoria, swap y red para el HUD de V.I.E.R.N.E.S.
        """
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        disk = psutil.disk_usage("/")
        uptime_seconds = int(time.time() - START_TIME)

        temp_c = cls.get_cpu_temp()
        throttling = cls.get_throttling_status()
        cpu_power = cls.get_cpu_freq_and_volts()
        fan = cls.get_fan_speed()
        net_details = cls.get_network_details()

        # Evaluación térmica del procesador
        # Raspberry Pi 5 Thermal Throttling: 80°C Soft Limit, 85°C Hard Limit
        if temp_c >= 85.0:
            thermal_status = "CRITICAL_OVERHEAT_85C"
        elif temp_c >= 80.0:
            thermal_status = "WARNING_SOFT_LIMIT_80C"
        elif temp_c >= 70.0:
            thermal_status = "ELEVATED_TEMP"
        else:
            thermal_status = "NOMINAL_SAFE"

        return {
            "timestamp": time.time(),
            "hostname": socket.gethostname(),
            "local_ip": cls.get_local_ip(),
            "cpu": {
                "percent": psutil.cpu_percent(interval=None),
                "cores": psutil.cpu_count(logical=True),
                "temperature_c": temp_c,
                "freq_mhz": cpu_power["freq_mhz"],
                "voltage_v": cpu_power["voltage_v"],
                "thermal_status": thermal_status,
            },
            "ram": {
                "total_mb": round(mem.total / (1024 * 1024), 1),
                "used_mb": round(mem.used / (1024 * 1024), 1),
                "available_mb": round(mem.available / (1024 * 1024), 1),
                "percent": mem.percent,
            },
            "swap": {
                "total_mb": round(swap.total / (1024 * 1024), 1),
                "used_mb": round(swap.used / (1024 * 1024), 1),
                "free_mb": round(swap.free / (1024 * 1024), 1),
                "percent": swap.percent,
                "sin_mb": round(swap.sin / (1024 * 1024), 2),
                "sout_mb": round(swap.sout / (1024 * 1024), 2),
                "swap_warning": swap.percent > 60.0 or (swap.used > 512 * 1024 * 1024 and swap.percent > 40.0)
            },
            "disk": {
                "total_gb": round(disk.total / (1024 * 1024 * 1024), 1),
                "free_gb": round(disk.free / (1024 * 1024 * 1024), 1),
                "percent": disk.percent,
            },
            "throttling": throttling,
            "cooling": fan,
            "network": net_details,
            "uptime": {
                "seconds": uptime_seconds,
                "formatted": f"{uptime_seconds // 3600:02d}:{(uptime_seconds % 3600) // 60:02d}:{uptime_seconds % 60:02d}",
            },
            "model": "Raspberry Pi 5 (8GB ARM64 BCM2712)",
            "ai_status": "ONLINE",
            "voice_state": "LISTENING",
        }

