"""
Módulo de Reconocimiento de Red Asíncrono no bloqueante para V.I.E.R.N.E.S.
Soporta subred activa dinámica .100.x, escaneo ARP/Nmap asíncrono y control de concurrencia.
"""

import os
import re
import socket
import asyncio
import logging
from typing import Dict, List, Optional, Any
from viernes.core.event_bus import bus

logger = logging.getLogger("viernes.iot.scanner")


class NetworkScanner:
    def __init__(self, subnet: Optional[str] = None):
        self.subnet = subnet or self.detect_active_subnet()
        self.arp_cache: Dict[str, str] = {}
        self.device_names: Dict[str, str] = {}
        self.device_vendors: Dict[str, str] = {}
        self.device_details: Dict[str, Dict[str, Any]] = {}
        self.known_ips: set = set()
        self._deep_scan_semaphore = asyncio.Semaphore(1) # Máximo 1 escaneo profundo a la vez
        self._load_oui_database()

    def detect_active_subnet(self) -> str:
        """Determina la subred local activa en tiempo real."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            parts = ip.split(".")
            active_subnet = f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"
            self.subnet = active_subnet
            return active_subnet
        except Exception:
            return "192.168.100.0/24"

    def _load_oui_database(self):
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
            "24:4b:fe": "Espressif (WiZ / Tuya / Smart Home)",
            "30:ae:a4": "Espressif (Yeelight / WiZ / IoT)",
            "60:01:94": "Espressif (Tasmota / Sonoff)",
            "a0:20:a6": "WiZ Connected / Signify",
            "44:4f:8e": "WiZ Connected Light",
            "ec:fa:bc": "Shelly / Allterco",
            "00:17:88": "Philips Hue",
            "f0:18:98": "Apple Inc.",
            "ac:de:48": "Apple Inc.",
            "98:2c:bc": "Samsung Electronics",
            "50:02:91": "Tuya Smart Inc.",
        }

    def _lookup_vendor(self, mac: str) -> str:
        if not mac:
            return "Desconocido"
        clean_mac = mac.lower().replace("-", ":")
        prefix = ":".join(clean_mac.split(":")[:3])
        return self.oui_table.get(prefix, "Dispositivo de Red")

    def _resolve_netbios_name(self, ip: str, timeout: float = 0.25) -> Optional[str]:
        """Consulta el nombre NetBIOS (puerto UDP 137)."""
        try:
            query = (
                b"\x80\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00"
                b"\x20\x43\x4b\x41\x41\x41\x41\x41\x41\x41\x41\x41"
                b"\x41\x41\x41\x41\x41\x41\x41\x41\x41\x41\x41\x41"
                b"\x41\x41\x41\x41\x41\x41\x41\x41\x41\x00\x00\x21\x00\x01"
            )
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(timeout)
            sock.sendto(query, (ip, 137))
            data, _ = sock.recvfrom(1024)
            sock.close()

            if len(data) > 56:
                num_names = data[56]
                if num_names > 0 and len(data) >= 57 + 18:
                    name_bytes = data[57:57 + 15].strip()
                    netbios_name = name_bytes.decode("latin1", errors="ignore").strip()
                    if netbios_name and not netbios_name.startswith("IS~"):
                        return netbios_name
        except Exception:
            pass
        return None

    def _resolve_hostname_deep(self, ip: str) -> str:
        """Resuelve el nombre de host de forma rápida."""
        if ip in self.device_names:
            return self.device_names[ip]

        # 1. Reverse DNS
        try:
            name, _, _ = socket.gethostbyaddr(ip)
            if name and name != ip:
                clean_name = name.split(".")[0]
                self.device_names[ip] = clean_name
                return clean_name
        except Exception:
            pass

        # 2. NetBIOS Query
        nb_name = self._resolve_netbios_name(ip)
        if nb_name:
            self.device_names[ip] = nb_name
            return nb_name

        return "Dispositivo LAN"

    async def scan_arp_table(self) -> Dict[str, Dict[str, Any]]:
        """Lee la tabla ARP del kernel."""
        devices = {}
        try:
            if os.name == "nt":
                proc = await asyncio.create_subprocess_exec(
                    "arp", "-a", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL
                )
                stdout, _ = await proc.communicate()
                output = stdout.decode("latin1", errors="ignore")
                for line in output.splitlines():
                    match = re.search(r"(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F-]{17})\s+(\w+)", line)
                    if match:
                        ip, mac_raw, _ = match.groups()
                        mac = mac_raw.replace("-", ":").lower()
                        if mac not in ("ff:ff:ff:ff:ff:ff", "00:00:00:00:00:00") and not ip.startswith("224.") and not ip.startswith("239."):
                            self.arp_cache[ip] = mac
                            devices[ip] = {
                                "ip": ip,
                                "mac": mac,
                                "vendor": self._lookup_vendor(mac),
                                "source": "arp_cache",
                            }
            else:
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
            logger.debug(f"Error en scan_arp_table: {e}")

        return devices

    async def _run_fast_nmap_scan(self, target_subnet: str) -> List[Dict[str, Any]]:
        """Ejecuta Nmap ping sweep asíncrono (-sn -PR -T4)."""
        found = []
        try:
            proc = await asyncio.create_subprocess_exec(
                "nmap", "-sn", "-PR", "-T4", "--min-rate", "120", "--host-timeout", "400ms", target_subnet,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5.0)
            output = stdout.decode("latin1", errors="ignore")

            current_ip = None
            current_name = None

            for line in output.splitlines():
                host_match = re.search(r"Nmap scan report for (?:([^\s()]+)\s+\()?(\d+\.\d+\.\d+\.\d+)\)?", line)
                if host_match:
                    current_name, current_ip = host_match.groups()

                mac_match = re.search(r"MAC Address:\s+([0-9a-fA-F:]{17})\s*(?:\((.*?)\))?", line)
                if mac_match and current_ip:
                    mac = mac_match.group(1).lower()
                    vendor = mac_match.group(2) or self._lookup_vendor(mac)
                    self.arp_cache[current_ip] = mac
                    if current_name:
                        self.device_names[current_ip] = current_name

                    found.append({
                        "ip": current_ip,
                        "mac": mac,
                        "vendor": vendor,
                        "hostname": current_name or self._resolve_hostname_deep(current_ip),
                        "status": "online"
                    })
                    current_ip = None
                    current_name = None
        except Exception as e:
            logger.debug(f"Nmap rápido no disponible: {e}")
        return found

    async def scan_active_subnet(self) -> List[Dict[str, Any]]:
        """Escanea la subred activa de forma 100% no-bloqueante."""
        self.detect_active_subnet()
        found_devices: Dict[str, Dict[str, Any]] = {}

        # 1. Nmap rápido
        nmap_results = await self._run_fast_nmap_scan(self.subnet)
        for dev in nmap_results:
            found_devices[dev["ip"]] = dev

        # 2. Tabla ARP
        cached = await self.scan_arp_table()
        for ip, info in cached.items():
            if ip.rsplit(".", 1)[0] == self.subnet.rsplit(".", 1)[0]:
                if ip not in found_devices:
                    hostname = self._resolve_hostname_deep(ip)
                    found_devices[ip] = {
                        "ip": ip,
                        "mac": info["mac"],
                        "vendor": info["vendor"],
                        "hostname": hostname,
                        "status": "online"
                    }

        results = list(found_devices.values())
        await bus.publish("network/scan_completed", {"count": len(results), "devices": results}, sender="network_scanner")
        return results

    async def ping_device(self, ip: str, timeout: float = 0.5) -> bool:
        """Verifica si una IP responde a ping ICMP de forma asíncrona."""
        try:
            if os.name == "nt":
                cmd = ["ping", "-n", "1", "-w", str(int(timeout * 1000)), ip]
            else:
                cmd = ["ping", "-c", "1", "-W", str(int(timeout)), ip]
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL
            )
            ret = await proc.wait()
            return ret == 0
        except Exception:
            return False

    async def resolve_mac(self, target: str) -> Optional[str]:
        if re.match(r"^([0-9a-fA-F]{2}[:-]){5}([0-9a-fA-F]{2})$", target):
            return target.replace("-", ":").lower()

        ip = target
        if not re.match(r"^\d+\.\d+\.\d+\.\d+$", target):
            try:
                ip = socket.gethostbyname(target)
            except Exception:
                pass

        if ip in self.arp_cache:
            return self.arp_cache[ip]

        await self.ping_device(ip)
        await self.scan_arp_table()
        return self.arp_cache.get(ip)


scanner = NetworkScanner()
