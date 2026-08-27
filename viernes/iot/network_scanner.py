"""
Módulo de Reconocimiento y Auto-Descubrimiento de Red para V.I.E.R.N.E.S.
Soporta escaneo ARP, Nmap, tabla de vecinos del kernel y resolución automática de MAC.
"""

import os
import re
import socket
import asyncio
import subprocess
import logging
from typing import Dict, List, Optional, Any
from viernes.core.event_bus import bus

logger = logging.getLogger("viernes.iot.scanner")


class NetworkScanner:
    def __init__(self, subnet: Optional[str] = None):
        self.subnet = subnet or self._detect_subnet()
        self.arp_cache: Dict[str, str] = {} # IP -> MAC
        self.device_names: Dict[str, str] = {} # IP -> Hostname / Alias
        self.device_vendors: Dict[str, str] = {} # MAC -> Vendor
        self._load_oui_database()

    def _detect_subnet(self) -> str:
        """Determina automáticamente la subred local (ej. 192.168.1.0/24)."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            parts = ip.split(".")
            return f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"
        except Exception:
            return "192.168.1.0/24"

    def _load_oui_database(self):
        """Mapeo rápido de prefijos OUI conocidos."""
        self.oui_table = {
            "b8:27:eb": "Raspberry Pi Foundation",
            "dc:a6:32": "Raspberry Pi Trading",
            "e4:5f:01": "Raspberry Pi Trading",
            "28:cd:c1": "Raspberry Pi (Pi 5)",
            "d8:3a:dd": "Raspberry Pi (Pi 5)",
            "00:15:5d": "Microsoft Hyper-V",
            "00:1a:79": "ASUSTek Computer",
            "04:d9:f5": "ASUSTek Computer",
            "50:eb:f6": "ASUSTek / ROG",
            "18:c0:4d": "Gigabyte Technology",
            "2c:fd:a1": "MSI Star Technology",
            "70:85:c2": "ASRock Incorporation",
            "24:4b:fe": "Espressif (Tuya / Smart Home)",
            "30:ae:a4": "Espressif (Yeelight / IoT)",
            "60:01:94": "Espressif (Tasmota / Sonoff)",
            "ec:fa:bc": "Shelly / Allterco",
            "00:17:88": "Philips Hue",
            "f0:18:98": "Apple Inc.",
            "ac:de:48": "Apple Inc.",
            "98:2c:bc": "Samsung Electronics",
        }

    def _lookup_vendor(self, mac: str) -> str:
        if not mac:
            return "Desconocido"
        clean_mac = mac.lower().replace("-", ":")
        prefix = ":".join(clean_mac.split(":")[:3])
        return self.oui_table.get(prefix, "Dispositivo de Red")

    async def scan_arp_table(self) -> Dict[str, Dict[str, Any]]:
        """Lee la tabla ARP del sistema operativo (instantáneo y ultra-ligero)."""
        devices = {}
        try:
            if os.name == "nt": # Windows
                output = subprocess.check_output(["arp", "-a"], text=True, stderr=subprocess.DEVNULL)
                for line in output.splitlines():
                    match = re.search(r"(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F-]{17})\s+(\w+)", line)
                    if match:
                        ip, mac_raw, type_ = match.groups()
                        mac = mac_raw.replace("-", ":").lower()
                        if mac not in ("ff:ff:ff:ff:ff:ff", "00:00:00:00:00:00") and not ip.startswith("224.") and not ip.startswith("239."):
                            self.arp_cache[ip] = mac
                            devices[ip] = {
                                "ip": ip,
                                "mac": mac,
                                "vendor": self._lookup_vendor(mac),
                                "source": "arp_cache",
                            }
            else: # Linux / Raspberry Pi OS
                if os.path.exists("/proc/net/arp"):
                    with open("/proc/net/arp", "r") as f:
                        lines = f.readlines()[1:]
                        for line in lines:
                            parts = line.split()
                            if len(parts) >= 4:
                                ip, mac = parts[0], parts[3].lower()
                                if mac != "00:00:00:00:00:00":
                                    self.arp_cache[ip] = mac
                                    devices[ip] = {
                                        "ip": ip,
                                        "mac": mac,
                                        "vendor": self._lookup_vendor(mac),
                                        "source": "arp_table",
                                    }
        except Exception as e:
            logger.warning(f"Error leyendo tabla ARP del sistema: {e}")

        return devices

    async def scan_active_subnet(self) -> List[Dict[str, Any]]:
        """Realiza un barrido activo para descubrir todos los dispositivos vivos en la subred."""
        # 1. Primero intentar Scapy si está disponible
        found_devices = {}
        try:
            from scapy.all import ARP, Ether, srp
            logger.info(f"Iniciando escaneo ARP en {self.subnet} vía Scapy...")
            ans, _ = await asyncio.to_thread(
                srp, Ether(dst="ff:ff:ff:ff:ff:ff") / ARP(pdst=self.subnet),
                timeout=2, verbose=False
            )
            for _, rcv in ans:
                ip = rcv.psrc
                mac = rcv.hwsrc.lower()
                self.arp_cache[ip] = mac
                vendor = self._lookup_vendor(mac)
                found_devices[ip] = {
                    "ip": ip,
                    "mac": mac,
                    "vendor": vendor,
                    "hostname": self._resolve_hostname(ip),
                    "status": "online",
                }
        except Exception as e:
            logger.debug(f"Scapy no disponible o sin privilegios raw socket: {e}. Usando método fallback ARP/Ping.")
            # Fallback: Ping sweep asíncrono + lectura de tabla ARP
            await self._async_ping_sweep()
            cached = await self.scan_arp_table()
            for ip, info in cached.items():
                is_alive = await self.ping_device(ip)
                found_devices[ip] = {
                    "ip": ip,
                    "mac": info["mac"],
                    "vendor": info["vendor"],
                    "hostname": self._resolve_hostname(ip),
                    "status": "online" if is_alive else "offline",
                }

        results = list(found_devices.values())
        await bus.publish("network/scan_completed", {"count": len(results), "devices": results}, sender="network_scanner")
        return results

    async def _async_ping_sweep(self):
        """Envía pings rápidos concurrentes a toda la subred /24 para poblar la tabla ARP."""
        base_ip = ".".join(self.subnet.split(".")[:3])
        tasks = []
        for i in range(1, 255):
            target = f"{base_ip}.{i}"
            tasks.append(self.ping_device(target, timeout=0.4))
        await asyncio.gather(*tasks, return_exceptions=True)

    def _resolve_hostname(self, ip: str) -> str:
        try:
            name, _, _ = socket.gethostbyaddr(ip)
            return name
        except Exception:
            return "Desconocido"

    async def ping_device(self, ip: str, timeout: float = 1.0) -> bool:
        """Verifica si una IP responde a ping ICMP."""
        try:
            if os.name == "nt":
                cmd = ["ping", "-n", "1", "-w", str(int(timeout * 1000)), ip]
            else:
                cmd = ["ping", "-c", "1", "-W", str(int(timeout)), ip]
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            ret = await proc.wait()
            return ret == 0
        except Exception:
            return False

    async def resolve_mac(self, target: str) -> Optional[str]:
        """
        Resuelve automáticamente la dirección MAC a partir de una IP o Hostname.
        Si la MAC no está en caché, realiza un ping rápido para forzar el ARP discovery.
        """
        # Si ya es una MAC válida:
        if re.match(r"^([0-9a-fA-F]{2}[:-]){5}([0-9a-fA-F]{2})$", target):
            return target.replace("-", ":").lower()

        # Si es un hostname, resolver a IP
        ip = target
        if not re.match(r"^\d+\.\d+\.\d+\.\d+$", target):
            try:
                ip = socket.gethostbyname(target)
            except Exception:
                pass

        # 1. Verificar caché en memoria
        if ip in self.arp_cache:
            return self.arp_cache[ip]

        # 2. Forzar ping y releer tabla ARP
        await self.ping_device(ip)
        await self.scan_arp_table()

        if ip in self.arp_cache:
            return self.arp_cache[ip]

        logger.warning(f"No se pudo resolver la MAC automáticamente para {target} ({ip}).")
        return None
