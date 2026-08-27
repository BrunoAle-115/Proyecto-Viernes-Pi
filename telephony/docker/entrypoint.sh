#!/bin/bash
set -e

echo "=== INICIANDO V.I.E.R.N.E.S TELEPHONY ENGINE (ASTERISK 20 LTS - CHILE) ==="

# Generar certificados autofirmados si no existen para TLS / WebRTC
if [ ! -f /etc/asterisk/keys/asterisk.crt ]; then
    echo "Generando certificados TLS para SIP / WebRTC..."
    mkdir -p /etc/asterisk/keys
    openssl req -new -x509 -days 3650 -nodes \
        -out /etc/asterisk/keys/asterisk.crt \
        -keyout /etc/asterisk/keys/asterisk.key \
        -subj "/C=CL/ST=Santiago/L=Santiago/O=VIERNES-AI/CN=telephony.viernes.ai" 2>/dev/null || true
fi

# Copiar configuraciones montadas
if [ -d /config_override ]; then
    echo "Aplicando configuraciones de /config_override a /etc/asterisk..."
    cp -rf /config_override/* /etc/asterisk/
fi

# Asegurar permisos correctos
chown -R asterisk:asterisk /etc/asterisk /var/lib/asterisk /var/log/asterisk /var/spool/asterisk /var/run/asterisk 2>/dev/null || true

exec "$@"
