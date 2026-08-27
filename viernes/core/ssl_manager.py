"""
Módulo de Gestión de Certificados SSL/TLS para V.I.E.R.N.E.S.
Genera y mantiene certificados auto-firmados con SAN (Subject Alternative Names)
para habilitar Secure Contexts (Micrófono Web, Web Speech API, WSS) en red local.
"""

import os
import sys
import logging
import datetime
import ipaddress
import socket
import subprocess
from typing import Tuple, Optional

logger = logging.getLogger("viernes.core.ssl")

SSL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "ssl")
CERT_FILE = os.path.join(SSL_DIR, "cert.pem")
KEY_FILE = os.path.join(SSL_DIR, "key.pem")


class SSLManager:
    """Gestiona la generación y validación de certificados TLS locales."""

    def __init__(self, cert_dir: str = SSL_DIR):
        self.cert_dir = cert_dir
        self.cert_file = os.path.join(cert_dir, "cert.pem")
        self.key_file = os.path.join(cert_dir, "key.pem")
        os.makedirs(self.cert_dir, exist_ok=True)

    def is_cert_valid(self) -> bool:
        """Verifica si los archivos de certificado y clave existen y tienen tamaño > 0."""
        return (
            os.path.exists(self.cert_file)
            and os.path.exists(self.key_file)
            and os.path.getsize(self.cert_file) > 100
            and os.path.getsize(self.key_file) > 100
        )

    def get_local_ips(self) -> list:
        """Obtiene todas las IPs locales detectables para incluirlas en el SAN."""
        ips = {"127.0.0.1", "192.168.100.43"}
        try:
            hostname = socket.gethostname()
            for info in socket.getaddrinfo(hostname, None):
                ip = info[4][0]
                if ":" not in ip: # Solo IPv4
                    ips.add(ip)
        except Exception:
            pass
        return list(ips)

    def generate_self_signed_cert(self) -> bool:
        """Genera un certificado auto-firmado válido por 2 años con SAN para todas las IPs locales."""
        logger.info("Generando certificado TLS auto-firmado para V.I.E.R.N.E.S. (Secure Contexts)...")

        # Intento 1: Usar la librería pure-python cryptography si está disponible
        try:
            from cryptography import x509
            from cryptography.x509.oid import NameOID
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.asymmetric import rsa
            from cryptography.hazmat.primitives import serialization

            key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048
            )

            subject = issuer = x509.Name([
                x509.NameAttribute(NameOID.COUNTRY_NAME, "CL"),
                x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Santiago"),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Stark Industries / V.I.E.R.N.E.S."),
                x509.NameAttribute(NameOID.COMMON_NAME, "192.168.100.43"),
            ])

            san_items = [
                x509.DNSName("localhost"),
                x509.DNSName("viernes.local"),
                x509.DNSName("VPN-BRUNO"),
                x509.DNSName("VPN-BRUNO.local"),
            ]

            for ip_str in self.get_local_ips():
                try:
                    san_items.append(x509.IPAddress(ipaddress.ip_address(ip_str)))
                except Exception:
                    pass

            cert = (
                x509.CertificateBuilder()
                .subject_name(subject)
                .issuer_name(issuer)
                .public_key(key.public_key())
                .serial_number(x509.random_serial_number())
                .not_valid_before(datetime.datetime.utcnow() - datetime.timedelta(days=1))
                .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=730))
                .add_extension(x509.SubjectAlternativeName(san_items), critical=False)
                .sign(key, hashes.SHA256())
            )

            with open(self.key_file, "wb") as f:
                f.write(key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.TraditionalOpenSSL,
                    encryption_algorithm=serialization.NoEncryption()
                ))

            with open(self.cert_file, "wb") as f:
                f.write(cert.public_bytes(serialization.Encoding.PEM))

            logger.info(f"✓ Certificado TLS generado con éxito en: {self.cert_file}")
            return True
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"Error generando certificado con cryptography ({e}). Probando openssl CLI...")

        # Intento 2: Usar openssl CLI
        try:
            ips = self.get_local_ips()
            san_entries = ["DNS:localhost", "DNS:viernes.local", "DNS:VPN-BRUNO", "DNS:VPN-BRUNO.local"]
            for ip in ips:
                san_entries.append(f"IP:{ip}")
            san_str = ",".join(san_entries)

            cmd = [
                "openssl", "req", "-x509", "-newkey", "rsa:2048",
                "-keyout", self.key_file,
                "-out", self.cert_file,
                "-days", "730",
                "-nodes",
                "-subj", "/C=CL/ST=Santiago/O=Stark Industries/CN=192.168.100.43",
                "-addext", f"subjectAltName={san_str}"
            ]
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            logger.info(f"✓ Certificado TLS generado con openssl en: {self.cert_file}")
            return True
        except Exception as e:
            logger.error(f"No se pudo generar certificado TLS con openssl: {e}")
            return False

    def get_ssl_files(self) -> Tuple[Optional[str], Optional[str]]:
        """Retorna las rutas (cert_file, key_file) si están listos o se generan con éxito."""
        if not self.is_cert_valid():
            success = self.generate_self_signed_cert()
            if not success:
                return None, None
        return self.cert_file, self.key_file


ssl_mgr = SSLManager()
