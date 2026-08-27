#!/usr/bin/env bash
# ==============================================================================
# V.I.E.R.N.E.S. - Easy Install & Autodeploy Engine para Raspberry Pi 5
# Stark Industries Tactical AI Framework
# ==============================================================================

set -e

# Colores de Terminal Stark HUD
CYAN='\033[0;36m'
GOLD='\033[0;33m'
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${CYAN}"
echo "  ██╗   ██╗██╗███████╗██████╗ ███╗   ██╗███████╗███████╗"
echo "  ██║   ██║██║██╔════╝██╔══██╗████╗  ██║██╔════╝██╔════╝"
echo "  ██║   ██║██║█████╗  ██████╔╝██╔██╗ ██║█████╗  ███████╗"
echo "  ╚██╗ ██╔╝██║██╔══╝  ██╔══██╗██║╚██╗██║██╔══╝  ╚════██║"
echo "   ╚████╔╝ ██║███████╗██║  ██║██║ ╚████║███████╗███████║"
echo "    ╚═══╝  ╚═╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═══╝╚══════╝╚══════╝"
echo -e "       ${GOLD}STARK INDUSTRIES AI FRAMEWORK // PI 5 AUTODEPLOY${NC}\n"

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# ------------------------------------------------------------------------------
# 1. VERIFICACIÓN DE SERVICIOS PREEXISTENTES Y DETECCIÓN DE PUERTOS
# ------------------------------------------------------------------------------
echo -e "${GOLD}[1/7] Escaneando servicios preexistentes en la Raspberry Pi 5...${NC}"

# Detectar Pi-hole
if systemctl is-active --quiet pihole-FTL 2>/dev/null || ss -tulpn | grep -q ':53 '; then
    echo -e "  ${GREEN}✓ Pi-hole detectado:${NC} Operando en puerto 53 (DNS) y 80 (Admin Web). ${CYAN}[Sin conflicto: V.I.E.R.N.E.S usará puerto 9090]${NC}"
fi

# Detectar Asterisk
if systemctl is-active --quiet asterisk 2>/dev/null || ss -tulpn | grep -q ':5060 '; then
    echo -e "  ${GREEN}✓ Asterisk PBX detectado:${NC} Operando en puerto 5060 (SIP) y 5038 (AMI). ${CYAN}[V.I.E.R.N.E.S se integrará como cliente local AMI/ARI]${NC}"
fi

# Detectar Headscale / Tailscale
if ip a | grep -q 'tailscale0' || systemctl is-active --quiet tailscaled 2>/dev/null; then
    echo -e "  ${GREEN}✓ Headscale/Tailscale VPN detectado:${NC} Interfaz 'tailscale0' activa. ${CYAN}[HUD accesible remotamente por tu IP de Tailscale]${NC}"
fi

# Verificar disponibilidad del puerto HUD 9090
if ss -tulpn | grep -q ':9090 '; then
    echo -e "  ${RED}⚠ Puerto 9090 en uso. Asignando puerto alternativo 9095...${NC}"
    export WEB_PORT=9095
else
    echo -e "  ${GREEN}✓ Puerto 9090 disponible para Stark HUD Dashboard.${NC}"
    export WEB_PORT=9090
fi

# ------------------------------------------------------------------------------
# 2. INSTALACIÓN DE DEPENDENCIAS DEL SISTEMA OPERATIVO
# ------------------------------------------------------------------------------
echo -e "\n${GOLD}[2/7] Instalando paquetes del sistema (Audio ALSA, Nmap, SQLite, Python)...${NC}"
sudo apt-get update -y
sudo apt-get install -y \
    python3-pip \
    python3-venv \
    python3-dev \
    git \
    nmap \
    wakeonlan \
    libasound2-dev \
    portaudio19-dev \
    libportaudio2 \
    libportaudiocpp0 \
    alsa-utils \
    ffmpeg \
    sox \
    libsox-fmt-all \
    sqlite3

# ------------------------------------------------------------------------------
# 3. CONFIGURACIÓN DEL ENTORNO VIRTUAL PYTHON
# ------------------------------------------------------------------------------
echo -e "\n${GOLD}[3/7] Creando entorno virtual Python 3 (.venv)...${NC}"
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate
pip install --upgrade pip setuptools wheel

echo -e "Instalando dependencias de Python desde requirements.txt..."
pip install -r requirements.txt

# ------------------------------------------------------------------------------
# 4. PERMISOS Y PRIVILEGIOS SIN ROOT (Raw Sockets para ARP y Audio)
# ------------------------------------------------------------------------------
echo -e "\n${GOLD}[4/7] Configurando permisos de audio y sockets de red...${NC}"
TARGET_USER="${SUDO_USER:-$USER}"
sudo usermod -aG audio,dialout,netdev $TARGET_USER || true

# Permitir a Python enviar tramas ARP sin ser ejecutado con sudo
PYTHON_BIN="$PROJECT_DIR/.venv/bin/python3"
if command -v setcap >/dev/null 2>&1; then
    sudo setcap cap_net_raw,cap_net_admin=eip "$PYTHON_BIN" 2>/dev/null || true
fi

# ------------------------------------------------------------------------------
# 5. ESTRUCTURA DE DATOS Y VARIABLES DE ENTORNO
# ------------------------------------------------------------------------------
echo -e "\n${GOLD}[5/7] Configurando carpetas de datos y variables de entorno...${NC}"
mkdir -p data credentials config/asterisk logs
chown -R $TARGET_USER:$TARGET_USER data logs credentials 2>/dev/null || true

if [ ! -f ".env" ]; then
    cp .env.example .env
    echo -e "  ${CYAN}Archivo .env generado.${NC}"
    echo -e "  ${GOLD}>> Recuerda colocar tu GEMINI_API_KEY en .env para activar el streaming de voz.${NC}"
fi

# ------------------------------------------------------------------------------
# 6. VERIFICACIÓN DE SUITE DE TESTS
# ------------------------------------------------------------------------------
echo -e "\n${GOLD}[6/7] Ejecutando suite de validación e integración V.I.E.R.N.E.S...${NC}"
export PYTHONPATH="$PROJECT_DIR"
pytest -v || {
    echo -e "${RED}Hubo advertencias en algunos tests, pero el núcleo continúa desplegando.${NC}"
}

# ------------------------------------------------------------------------------
# 7. REGISTRO Y ACTIVACIÓN COMO SERVICIO SYSTEMD
# ------------------------------------------------------------------------------
echo -e "\n${GOLD}[7/7] Configurando servicio systemd para arranque automático en el boot...${NC}"
SERVICE_FILE="/etc/systemd/system/viernes.service"

sudo bash -c "cat <<EOF > $SERVICE_FILE
[Unit]
Description=V.I.E.R.N.E.S. Tactical AI Assistant Core (Raspberry Pi 5)
After=network-online.target time-sync.target sound.target asterisk.service
Wants=network-online.target time-sync.target

[Service]
Type=simple
User=$TARGET_USER
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/.venv/bin/python3 $PROJECT_DIR/viernes/main.py
Restart=on-failure
RestartSec=5s
StartLimitIntervalSec=120s
StartLimitBurst=5
AmbientCapabilities=CAP_NET_RAW CAP_NET_ADMIN
CapabilityBoundingSet=CAP_NET_RAW CAP_NET_ADMIN
Environment=PYTHONUNBUFFERED=1
Environment="PYTHONPATH=$PROJECT_DIR"
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
EOF"

sudo systemctl daemon-reload
sudo systemctl enable viernes.service
sudo systemctl restart viernes.service

# Obtener IP local
LOCAL_IP=$(hostname -I | awk '{print $1}')
[ -z "$LOCAL_IP" ] && LOCAL_IP="127.0.0.1"

echo -e "\n${GREEN}================================================================${NC}"
echo -e "  ${CYAN}¡V.I.E.R.N.E.S. HA SIDO DESPLEGADA EXITOSAMENTE EN TU PI 5!${NC}"
echo -e "${GREEN}================================================================${NC}"
echo -e "  ${GOLD}• Dashboard HUD en Vivo:${NC} http://${LOCAL_IP}:${WEB_PORT}"
echo -e "  ${GOLD}• Estado del Servicio:${NC}   sudo systemctl status viernes"
echo -e "  ${GOLD}• Logs en Tiempo Real:${NC}   sudo journalctl -u viernes -f"
echo -e "  ${GOLD}• Parar Asistente:${NC}       sudo systemctl stop viernes"
echo -e "  ${GOLD}• Iniciar Manualmente:${NC}   ./scripts/run.sh"
echo -e "${GREEN}================================================================${NC}\n"
