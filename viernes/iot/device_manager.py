"""
Gestor de Dispositivos e Inventario de Red para V.I.E.R.N.E.S.
Mantiene el registro persistente de dispositivos con nombres amigables (ej: "PC Gamer", "Luces").
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
        """Carga dispositivos guardados desde JSON."""
        if os.path.exists(DEVICES_FILE):
            try:
                with open(DEVICES_FILE, "r", encoding="utf-8") as f:
                    self.devices = json.load(f)
            except Exception as e:
                logger.error(f"Error cargando dispositivos desde {DEVICES_FILE}: {e}")
        else:
            # Dispositivos por defecto pre-registrados
            self.devices = {
                "pc_principal": {
                    "id": "pc_principal",
                    "alias": "Mi PC Gamer",
                    "ip": "192.168.1.150",
                    "mac": "00:11:22:33:44:55",
                    "type": "desktop",
                    "wol_enabled": True,
                    "status": "offline",
                    "last_seen": None,
                },
                "luces_escritorio": {
                    "id": "luces_escritorio",
                    "alias": "Luces de Escritorio",
                    "ip": "192.168.1.120",
                    "mac": "",
                    "type": "light",
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
        """Escanea la red y actualiza el estado y MACs de todos los dispositivos."""
        scanned = await self.scanner.scan_active_subnet()
        now = datetime.now().isoformat()

        # Actualizar dispositivos conocidos con datos escaneados
        for sc in scanned:
            ip = sc["ip"]
            mac = sc["mac"]
            vendor = sc.get("vendor", "")

            # Buscar si coincide con algún dispositivo guardado
            matched = False
            for dev_id, dev in self.devices.items():
                if dev.get("ip") == ip or (dev.get("mac") and dev.get("mac").lower() == mac.lower()):
                    dev["ip"] = ip
                    dev["mac"] = mac
                    dev["status"] = "online"
                    dev["last_seen"] = now
                    dev["vendor"] = vendor
                    matched = True
                    break

            if not matched:
                # Registrar nuevo dispositivo descubierto
                new_id = f"dev_{mac.replace(':', '')[-6:]}" if mac else f"dev_{ip.replace('.', '_')}"
                self.devices[new_id] = {
                    "id": new_id,
                    "alias": sc.get("hostname") or f"Dispositivo ({vendor})",
                    "ip": ip,
                    "mac": mac,
                    "type": "light" if "yeelight" in vendor.lower() or "tuya" in vendor.lower() else "generic",
                    "vendor": vendor,
                    "status": "online",
                    "last_seen": now,
                    "wol_enabled": "desktop" in vendor.lower() or "asustek" in vendor.lower() or "gigabyte" in vendor.lower() or "msi" in vendor.lower(),
                }

        self._save_devices()
        return list(self.devices.values())

    def get_device_by_name(self, query: str) -> Optional[Dict[str, Any]]:
        """Busca un dispositivo por coincidencia de texto en su alias, id o tipo."""
        q = query.lower().strip()
        if q in self.devices:
            return self.devices[q]

        for dev in self.devices.values():
            alias = dev.get("alias", "").lower()
            if q in alias or alias in q or q == dev.get("id", "").lower():
                return dev
            if ("pc" in q or "computador" in q or "tarro" in q) and dev.get("type") == "desktop":
                return dev
            if ("luz" in q or "luces" in q or "lampara" in q) and dev.get("type") == "light":
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

    async def execute_control_light(self, target_name_or_ip: str, state: str, brightness: int = 100) -> Dict[str, Any]:
        """Enciende/apaga luces por nombre o IP."""
        dev = self.get_device_by_name(target_name_or_ip)
        ip = dev.get("ip") if dev else target_name_or_ip
        return await self.lights.set_light_state(ip, state=state, brightness=brightness)


device_mgr = DeviceManager()
