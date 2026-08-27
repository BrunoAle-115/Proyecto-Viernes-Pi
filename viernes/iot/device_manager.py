"""
Gestor de Dispositivos e Inventario de Red para V.I.E.R.N.E.S.
Mantiene el registro persistente de dispositivos con nombres amigables (ej: "PC Gamer", "Luz WiZ", "Aire Acondicionado").
Soporta migración automática de subred (.100.x), control de WiZ (RGB/Kelvin/Paleta) y AIRSYS AC.
"""

import json
import os
import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from viernes.iot.network_scanner import NetworkScanner
from viernes.iot.wake_on_lan import WakeOnLanManager
from viernes.iot.smart_lights import SmartDeviceController
from viernes.core.event_bus import bus

logger = logging.getLogger("viernes.iot.manager")

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
DEVICES_FILE = os.path.join(DATA_DIR, "devices.json")


class DeviceManager:
    def __init__(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        self.scanner = NetworkScanner()
        self.wol = WakeOnLanManager(scanner=self.scanner)
        self.lights = SmartDeviceController()
        self.devices: Dict[str, Dict[str, Any]] = {}
        self._load_devices()

    def _load_devices(self):
        """Carga dispositivos guardados desde JSON o inicializa defaults para la subred activa."""
        active_sub_prefix = self.scanner.detect_active_subnet().rsplit(".", 1)[0] # ej: 192.168.100

        if os.path.exists(DEVICES_FILE):
            try:
                with open(DEVICES_FILE, "r", encoding="utf-8") as f:
                    self.devices = json.load(f)
                
                # Migración de subred: si la subred activa cambió a .100.x, actualizar defaults antiguos
                if active_sub_prefix == "192.168.100":
                    if "luz_wiz" not in self.devices:
                        self.devices["luz_wiz"] = {
                            "id": "luz_wiz",
                            "alias": "Luz WiZ Escritorio",
                            "ip": "192.168.100.15",
                            "mac": "",
                            "type": "wiz_light",
                            "port": 38899,
                            "vendor": "WiZ Connected",
                            "status": "online",
                            "last_seen": datetime.now().isoformat()
                        }
                    if "aire_ac" not in self.devices:
                        self.devices["aire_ac"] = {
                            "id": "aire_ac",
                            "alias": "Aire Acondicionado AIRSYS",
                            "ip": "192.168.100.20",
                            "mac": "",
                            "type": "air_conditioner",
                            "vendor": "AIRSYS / Tuya Smart Life",
                            "status": "online",
                            "last_seen": datetime.now().isoformat()
                        }
                    # Si el PC Gamer tenía IP 192.168.1.150, migrarlo a la nueva subred .100.150 si no hay conflicto
                    if "pc_principal" in self.devices and self.devices["pc_principal"]["ip"].startswith("192.168.1."):
                        self.devices["pc_principal"]["ip"] = "192.168.100.150"
                    
                    self._save_devices()
                return
            except Exception as e:
                logger.error(f"Error cargando dispositivos desde {DEVICES_FILE}: {e}")

        # Dispositivos por defecto pre-registrados para la subred activa
        self.devices = {
            "pc_principal": {
                "id": "pc_principal",
                "alias": "Mi PC Gamer",
                "ip": f"{active_sub_prefix}.150",
                "mac": "00:11:22:33:44:55",
                "type": "desktop",
                "wol_enabled": True,
                "status": "offline",
                "last_seen": None,
            },
            "luz_wiz": {
                "id": "luz_wiz",
                "alias": "Luz WiZ Escritorio",
                "ip": "192.168.100.15",
                "mac": "",
                "type": "wiz_light",
                "port": 38899,
                "vendor": "WiZ Connected",
                "wol_enabled": False,
                "status": "online",
                "last_seen": None,
            },
            "aire_ac": {
                "id": "aire_ac",
                "alias": "Aire Acondicionado AIRSYS",
                "ip": f"{active_sub_prefix}.20",
                "mac": "",
                "type": "air_conditioner",
                "vendor": "AIRSYS / Smart Life",
                "wol_enabled": False,
                "status": "online",
                "last_seen": None,
            }
        }
        self._save_devices()

    def _save_devices(self):
        try:
            with open(DEVICES_FILE, "w", encoding="utf-8") as f:
                json.dump(self.devices, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error guardando dispositivos: {e}")

    async def scan_and_update(self) -> List[Dict[str, Any]]:
        """Escanea la red actual y actualiza el estado, MACs y hostnames de los dispositivos."""
        scanned = await self.scanner.scan_active_subnet()
        now = datetime.now().isoformat()
        active_sub_prefix = self.scanner.subnet.rsplit(".", 1)[0]

        # Actualizar dispositivos conocidos con datos escaneados
        for sc in scanned:
            ip = sc["ip"]
            mac = sc["mac"]
            vendor = sc.get("vendor", "")
            hostname = sc.get("hostname", "")

            # Buscar si coincide con algún dispositivo guardado
            matched = False
            for dev_id, dev in self.devices.items():
                if dev.get("ip") == ip or (dev.get("mac") and dev.get("mac").lower() == mac.lower()):
                    dev["ip"] = ip
                    dev["mac"] = mac
                    dev["status"] = "online"
                    dev["last_seen"] = now
                    dev["vendor"] = vendor
                    if hostname and hostname != "Dispositivo LAN":
                        dev["hostname"] = hostname
                    matched = True
                    break

            if not matched:
                # Registrar nuevo dispositivo descubierto
                new_id = f"dev_{mac.replace(':', '')[-6:]}" if mac else f"dev_{ip.replace('.', '_')}"
                is_wiz = "wiz" in vendor.lower() or "signify" in vendor.lower()
                is_tuya = "tuya" in vendor.lower() or "espressif" in vendor.lower()
                
                dev_type = "wiz_light" if is_wiz else ("light" if is_tuya else "generic")
                
                self.devices[new_id] = {
                    "id": new_id,
                    "alias": hostname if (hostname and hostname != "Dispositivo LAN") else f"Dispositivo ({vendor})",
                    "ip": ip,
                    "mac": mac,
                    "type": dev_type,
                    "vendor": vendor,
                    "status": "online",
                    "last_seen": now,
                    "wol_enabled": any(k in vendor.lower() for k in ("asustek", "gigabyte", "msi", "asrock", "intel", "desktop")),
                }

        # Limpiar o marcar offline dispositivos que eran de una subred distinta
        for dev_id, dev in self.devices.items():
            dev_ip = dev.get("ip", "")
            if dev_ip and not dev_ip.startswith(active_sub_prefix):
                dev["status"] = "stale_other_subnet"

        self._save_devices()
        return list(self.devices.values())

    def get_device_by_name(self, query: str) -> Optional[Dict[str, Any]]:
        """Busca un dispositivo por coincidencia de texto en su alias, id o tipo, priorizando dispositivos online en la subred activa."""
        if not query:
            return None
        q = query.lower().strip()

        # 1. Búsqueda directa por ID si no está marcado como obsoleto
        if q in self.devices:
            dev = self.devices[q]
            if dev.get("status") != "stale_other_subnet":
                return dev

        # 2. Enrutamiento prioritario para dispositivos tácticos clave de Bruno
        if ("wiz" in q or "luz" in q or "luces" in q or "lampara" in q or "foco" in q):
            wiz = self.devices.get("luz_wiz")
            if wiz and wiz.get("status") != "stale_other_subnet":
                return wiz

        if ("aire" in q or "ac" in q or "clima" in q or "airsys" in q or "frio" in q or "calor" in q):
            ac = self.devices.get("aire_ac")
            if ac and ac.get("status") != "stale_other_subnet":
                return ac

        if ("pc" in q or "computador" in q or "tarro" in q or "gamer" in q or "desktop" in q):
            pc = self.devices.get("pc_principal")
            if pc and pc.get("status") != "stale_other_subnet":
                return pc

        # 3. Búsqueda por coincidencia de alias / IP / MAC en dispositivos activos
        for dev in self.devices.values():
            if dev.get("status") == "stale_other_subnet":
                continue
            alias = dev.get("alias", "").lower()
            dev_id = dev.get("id", "").lower()
            dev_ip = dev.get("ip", "")
            if q == dev_ip or q == dev_id or q in alias or alias in q:
                return dev

        return None

    async def execute_turn_on(self, target_name_or_ip: str) -> Dict[str, Any]:
        """Enciende un equipo mediante Wake-on-LAN buscando por nombre, MAC o IP."""
        dev = self.get_device_by_name(target_name_or_ip)
        if dev and dev.get("mac"):
            target = dev["mac"]
        elif dev and dev.get("ip"):
            target = dev["ip"]
        else:
            target = target_name_or_ip
        return await self.wol.wake_device(target, wait_for_boot=False)

    async def execute_control_light(
        self,
        target_name_or_ip: str,
        state: str,
        brightness: int = 100,
        palette: Optional[str] = None
    ) -> Dict[str, Any]:
        """Enciende/apaga luces y aplica paletas de color/temperatura."""
        dev = self.get_device_by_name(target_name_or_ip)
        ip = dev.get("ip") if dev else target_name_or_ip
        dev_type = dev.get("type", "auto") if dev else "auto"
        return await self.lights.set_light_state(ip, state=state, brightness=brightness, palette=palette, device_type=dev_type)

    async def execute_get_light_status(self, target_name_or_ip: str = "luz_wiz") -> Dict[str, Any]:
        """Consulta la paleta y estado actual de la luz WiZ."""
        dev = self.get_device_by_name(target_name_or_ip)
        ip = dev.get("ip") if dev else target_name_or_ip
        return await self.lights.get_wiz_status(ip)

    async def execute_control_ac(
        self,
        target_name_or_ip: str = "aire_ac",
        power: Optional[bool] = None,
        target_temp: Optional[int] = None,
        mode: Optional[str] = None,
        fan_speed: Optional[str] = None
    ) -> Dict[str, Any]:
        """Controla el Aire Acondicionado AIRSYS / Smart Life."""
        dev = self.get_device_by_name(target_name_or_ip)
        ip = dev.get("ip") if dev else target_name_or_ip
        return await self.lights.control_air_conditioner(
            ip, power=power, target_temp=target_temp, mode=mode, fan_speed=fan_speed
        )


device_mgr = DeviceManager()
