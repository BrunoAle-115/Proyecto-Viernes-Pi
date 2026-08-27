"""
Módulo Wake-on-LAN (WoL) con Auto-Resolución de MAC y Verificación de Encendido para V.I.E.R.N.E.S.
"""

import socket
import asyncio
import logging
from typing import Optional, Dict, Any
from viernes.iot.network_scanner import NetworkScanner
from viernes.core.event_bus import bus

logger = logging.getLogger("viernes.iot.wol")


class WakeOnLanManager:
    def __init__(self, scanner: Optional[NetworkScanner] = None, broadcast_ip: str = "255.255.255.255"):
        self.scanner = scanner or NetworkScanner()
        self.broadcast_ip = broadcast_ip

    def _create_magic_packet(self, mac_address: str) -> bytes:
        """Construye el Magic Packet de 102 bytes (6x 0xFF seguido de 16x la MAC)."""
        clean_mac = mac_address.replace(":", "").replace("-", "").replace(".", "")
        if len(clean_mac) != 12:
            raise ValueError(f"Dirección MAC inválida: '{mac_address}'")
        mac_bytes = bytes.fromhex(clean_mac)
        return b"\xff" * 6 + mac_bytes * 16

    def send_raw_magic_packet(self, mac_address: str, port: int = 9) -> bool:
        """Envía el Magic Packet por socket UDP broadcast."""
        try:
            packet = self._create_magic_packet(mac_address)
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                s.sendto(packet, (self.broadcast_ip, port))
                # También enviar al puerto 7 como redundancia
                s.sendto(packet, (self.broadcast_ip, 7))
            logger.info(f"Magic Packet transmitido con éxito para MAC {mac_address} en broadcast {self.broadcast_ip}:{port}")
            return True
        except Exception as e:
            logger.error(f"Error transmitiendo Magic Packet a {mac_address}: {e}")
            return False

    async def wake_device(self, target: str, wait_for_boot: bool = True, timeout_seconds: int = 25) -> Dict[str, Any]:
        """
        Enciende un dispositivo por IP, Hostname o MAC.
        Resuelve automáticamente la MAC si el usuario solo indica la IP o nombre.
        """
        logger.info(f"Iniciando secuencia Wake-on-LAN para objetivo: '{target}'...")
        
        # 1. Resolver MAC automáticamente si no se proporcionó directamente
        mac = await self.scanner.resolve_mac(target)
        if not mac:
            # Si el target parece ser directamente una MAC
            if len(target.replace(":", "").replace("-", "")) == 12:
                mac = target
            else:
                return {
                    "success": False,
                    "target": target,
                    "error": f"No se pudo resolver automáticamente la dirección MAC para '{target}'. Realiza un escaneo de red primero.",
                    "status": "mac_resolution_failed",
                }

        # 2. Transmitir Magic Packet
        sent = self.send_raw_magic_packet(mac)
        if not sent:
            return {
                "success": False,
                "target": target,
                "mac": mac,
                "error": "Fallo al enviar socket UDP broadcast",
                "status": "transmission_failed",
            }

        await bus.publish("wol/packet_sent", {"target": target, "mac": mac}, sender="wol_manager")

        # 3. Verificación de booteo mediante Ping continuo
        if wait_for_boot:
            logger.info(f"Monitoreando arranque del equipo ({target}) durante {timeout_seconds}s...")
            # Si el target es una IP, hacemos ping a ella
            check_ip = target if target.count(".") == 3 else None
            if not check_ip:
                # Buscar en arp_cache si tenemos la IP de esta MAC
                for ip_cached, mac_cached in self.scanner.arp_cache.items():
                    if mac_cached.lower() == mac.lower():
                        check_ip = ip_cached
                        break

            if check_ip:
                start_time = asyncio.get_event_loop().time()
                while (asyncio.get_event_loop().time() - start_time) < timeout_seconds:
                    await asyncio.sleep(2.5)
                    is_online = await self.scanner.ping_device(check_ip, timeout=0.8)
                    if is_online:
                        logger.info(f"Confirmado: Dispositivo {check_ip} ({mac}) ha iniciado y responde a ping.")
                        await bus.publish("wol/device_online", {"target": target, "ip": check_ip, "mac": mac}, sender="wol_manager")
                        return {
                            "success": True,
                            "target": target,
                            "ip": check_ip,
                            "mac": mac,
                            "status": "online",
                            "message": f"El equipo {target} ha encendido exitosamente y está en línea.",
                        }

        return {
            "success": True,
            "target": target,
            "mac": mac,
            "status": "magic_packet_sent",
            "message": f"Paquete mágico enviado a {mac}. El equipo debería iniciar en breve.",
        }
