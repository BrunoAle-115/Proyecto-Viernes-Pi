"""
Gestor de Asignación y Auto-Switching Dinámico de Puertos para V.I.E.R.N.E.S.
Verifica la disponibilidad de puertos (Web HUD, AudioSocket, SIP, API) y realiza conmutación
automática a puertos alternativos si el puerto preferido se encuentra ocupado por otro servicio.
"""

import socket
import logging
from typing import Tuple, List, Optional

logger = logging.getLogger("viernes.core.ports")


class DynamicPortManager:
    @staticmethod
    def is_port_available(port: int, host: str = "0.0.0.0", protocol: str = "tcp") -> bool:
        """Comprueba si un puerto específico TCP o UDP está libre para ser utilizado."""
        sock_type = socket.SOCK_STREAM if protocol.lower() == "tcp" else socket.SOCK_DGRAM
        with socket.socket(socket.AF_INET, sock_type) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind((host, port))
                return True
            except (socket.error, OSError):
                return False

    @classmethod
    def get_available_port(
        cls,
        preferred_port: int,
        fallback_range: int = 20,
        protocol: str = "tcp",
        service_name: str = "Servicio"
    ) -> int:
        """
        Retorna el puerto preferido si está disponible. Si está ocupado, realiza auto-switching
        secuencialmente dentro del rango de fallback hasta encontrar un puerto libre.
        """
        # 1. Probar el puerto preferido
        if cls.is_port_available(preferred_port, protocol=protocol):
            logger.info(f"[{service_name}] Puerto preferido {preferred_port}/{protocol.upper()} disponible.")
            return preferred_port

        logger.warning(
            f"[{service_name}] ¡Puerto {preferred_port}/{protocol.upper()} OCUPADO! "
            f"Iniciando Auto-Switching de puertos alternativos..."
        )

        # 2. Búsqueda de puerto libre en el rango alternativo
        for offset in range(1, fallback_range + 1):
            alt_port = preferred_port + offset
            if cls.is_port_available(alt_port, protocol=protocol):
                logger.info(
                    f"[{service_name}] Auto-Switching exitoso -> Asignado nuevo puerto: {alt_port}/{protocol.upper()} "
                    f"(Evita colisión con otros servicios)."
                )
                return alt_port

        # Fallback a puerto efímero asignado por el sistema operativo
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM if protocol.lower() == "tcp" else socket.SOCK_DGRAM) as s:
            s.bind(("", 0))
            ephemeral_port = s.getsockname()[1]
            logger.warning(f"[{service_name}] Asignando puerto efímero del SO: {ephemeral_port}")
            return ephemeral_port

    @classmethod
    def check_system_services_collision(cls) -> dict:
        """Auditoría de puertos del sistema para garantizar compatibilidad con Pi-hole y Asterisk."""
        pihole_dns = not cls.is_port_available(53, protocol="udp")
        pihole_web = not cls.is_port_available(80, protocol="tcp")
        asterisk_sip = not cls.is_port_available(5060, protocol="udp")
        asterisk_sips = not cls.is_port_available(5061, protocol="tcp")

        return {
            "pihole_dns_53_active": pihole_dns,
            "pihole_web_80_active": pihole_web,
            "asterisk_sip_5060_active": asterisk_sip,
            "asterisk_sips_5061_active": asterisk_sips,
            "recommended_hud_port": cls.get_available_port(9090, service_name="WebHUD"),
            "recommended_audiosocket_port": cls.get_available_port(9099, service_name="AudioSocket")
        }


port_manager = DynamicPortManager()
