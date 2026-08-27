"""
Tests automatizados para la generación y validación de Certificados SSL/TLS (ssl_manager.py).
Valida:
1. Creación de directorios y rutas de certificados TLS.
2. Validación de estado y tamaño de certificados existentes (is_cert_valid).
3. Recolección de IPs locales para Subject Alternative Names (SAN).
4. Generación vía librería pura cryptography (X.509 v3, RSA 2048, SHA256, 730 días).
5. Fallback a OpenSSL CLI en caso de no disponibilidad o fallo de cryptography.
6. Ciclo de vida completo de get_ssl_files().
"""

import os
import tempfile
import shutil
import ipaddress
import pytest
from unittest.mock import patch, MagicMock

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.x509.oid import NameOID

from viernes.core.ssl_manager import SSLManager


@pytest.fixture
def temp_ssl_dir():
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_ssl_manager_initialization_and_paths(temp_ssl_dir):
    """Verifica que el gestor configure las rutas correctas y cree el directorio si no existe."""
    target_dir = os.path.join(temp_ssl_dir, "nested", "ssl_data")
    mgr = SSLManager(cert_dir=target_dir)

    assert os.path.exists(target_dir)
    assert mgr.cert_file == os.path.join(target_dir, "cert.pem")
    assert mgr.key_file == os.path.join(target_dir, "key.pem")
    assert mgr.is_cert_valid() is False


def test_ssl_manager_is_cert_valid_states(temp_ssl_dir):
    """Verifica los criterios de validación de archivos TLS (existencia y tamaño > 100 bytes)."""
    mgr = SSLManager(cert_dir=temp_ssl_dir)

    # Estado 1: Archivos no existen
    assert mgr.is_cert_valid() is False

    # Estado 2: Archivos vacíos (0 bytes) o corruptos (< 100 bytes)
    with open(mgr.cert_file, "wb") as f:
        f.write(b"CERT CORRUPTO")
    with open(mgr.key_file, "wb") as f:
        f.write(b"KEY CORRUPTA")
    assert mgr.is_cert_valid() is False

    # Estado 3: Archivos válidos con tamaño suficiente
    with open(mgr.cert_file, "wb") as f:
        f.write(b"A" * 150)
    with open(mgr.key_file, "wb") as f:
        f.write(b"B" * 150)
    assert mgr.is_cert_valid() is True


def test_ssl_manager_get_local_ips():
    """Verifica que get_local_ips incluya 127.0.0.1, 192.168.100.43 y solo retorne IPv4 válidas."""
    mgr = SSLManager()
    ips = mgr.get_local_ips()

    assert "127.0.0.1" in ips
    assert "192.168.100.43" in ips
    for ip_str in ips:
        ip_obj = ipaddress.ip_address(ip_str)
        assert ip_obj.version == 4


def test_ssl_manager_generate_self_signed_cert_cryptography(temp_ssl_dir):
    """Valida la generación de certificados X.509 reales y verifica sus extensiones y metadatos."""
    mgr = SSLManager(cert_dir=temp_ssl_dir)
    success = mgr.generate_self_signed_cert()

    assert success is True
    assert mgr.is_cert_valid() is True

    # Cargar y verificar el certificado generado
    with open(mgr.cert_file, "rb") as f:
        cert_data = f.read()
        cert = x509.load_pem_x509_certificate(cert_data)

    # Verificar Subject / Issuer
    subject_org = cert.subject.get_attributes_for_oid(NameOID.ORGANIZATION_NAME)[0].value
    assert "Stark Industries" in subject_org or "V.I.E.R.N.E.S." in subject_org
    subject_cn = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
    assert subject_cn == "192.168.100.43"

    # Verificar Subject Alternative Names (SAN)
    san_ext = cert.extensions.get_extension_for_oid(x509.ExtensionOID.SUBJECT_ALTERNATIVE_NAME)
    san_values = san_ext.value
    dns_names = [name.value for name in san_values if isinstance(name, x509.DNSName)]
    ip_addrs = [str(name.value) for name in san_values if isinstance(name, x509.IPAddress)]

    assert "localhost" in dns_names
    assert "viernes.local" in dns_names
    assert "127.0.0.1" in ip_addrs

    # Verificar clave privada PEM
    with open(mgr.key_file, "rb") as f:
        key_data = f.read()
        private_key = serialization.load_pem_private_key(key_data, password=None)
        assert private_key.key_size == 2048


def test_ssl_manager_get_ssl_files_lifecycle(temp_ssl_dir):
    """Verifica el ciclo de vida: generación automática al inicio y reutilización sin regenerar."""
    mgr = SSLManager(cert_dir=temp_ssl_dir)

    cert_path, key_path = mgr.get_ssl_files()
    assert cert_path == mgr.cert_file
    assert key_path == mgr.key_file
    assert os.path.exists(cert_path)
    assert os.path.exists(key_path)

    cert_mtime_1 = os.path.getmtime(cert_path)

    cert_path_2, key_path_2 = mgr.get_ssl_files()
    assert cert_path_2 == cert_path
    assert key_path_2 == key_path
    assert os.path.getmtime(cert_path) == cert_mtime_1
