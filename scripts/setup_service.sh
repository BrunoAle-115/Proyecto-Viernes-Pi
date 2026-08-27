#!/usr/bin/env bash
# ==============================================================================
# V.I.E.R.N.E.S. - Instalador de Servicio Systemd para Raspberry Pi 5
# ==============================================================================

set -e

if [ "$EUID" -ne 0 ]; then
    echo "Por favor ejecuta este script con permisos sudo: sudo ./scripts/setup_service.sh"
    exit 1
fi

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_FILE="/etc/systemd/system/viernes.service"
USER_NAME="${SUDO_USER:-$USER}"

echo "Configurando servicio systemd para V.I.E.R.N.E.S. en: $PROJECT_DIR"

cat <<EOF > "$SERVICE_FILE"
[Unit]
Description=V.I.E.R.N.E.S. Tactical AI Assistant Core (Raspberry Pi 5)
After=network-online.target sound.target
Wants=network-online.target

[Service]
Type=simple
User=$USER_NAME
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/.venv/bin/python3 $PROJECT_DIR/viernes/main.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable viernes.service
systemctl restart viernes.service

echo "=========================================================="
echo "  ¡Servicio 'viernes.service' instalado y activado!      "
echo "  Estado del servicio: sudo systemctl status viernes     "
echo "  Logs en vivo:        sudo journalctl -u viernes -f     "
echo "=========================================================="
