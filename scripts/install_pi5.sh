#!/usr/bin/env bash
# ==============================================================================
# V.I.E.R.N.E.S. - Script de Instalación Automatizada para Raspberry Pi 5
# Sistema Operativo: Raspberry Pi OS (Debian Bookworm 64-bit)
# ==============================================================================

set -e

echo "=========================================================="
echo "    INSTALADOR DE V.I.E.R.N.E.S. PARA RASPBERRY PI 5      "
echo "           Stark Labs Tactical AI Framework               "
echo "=========================================================="

# 1. Actualizar repositorios del sistema
echo "[1/6] Actualizando paquetes del sistema..."
sudo apt-get update && sudo apt-get upgrade -y

# 2. Instalar dependencias nativas del sistema (Audio, Red, Compiladores)
echo "[2/6] Instalando dependencias de audio ALSA/PulseAudio, Nmap y Python..."
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
    ffmpeg \
    sox \
    libsox-fmt-all \
    sqlite3 \
    asterisk \
    asterisk-modules \
    asterisk-pjsip

# 3. Configurar entorno virtual de Python
echo "[3/6] Configurando entorno virtual Python en .venv..."
cd "$(dirname "$0")/.."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi

source .venv/bin/activate
pip install --upgrade pip setuptools wheel

# 4. Instalar librerías de Python
echo "[4/6] Instalando requerimientos de Python..."
pip install -r requirements.txt

# 5. Configurar permisos de audio y sockets sin root
echo "[5/6] Configurando permisos de usuario en grupos audio y netdev..."
sudo usermod -aG audio,dialout,netdev $USER || true

# Permitir a Python enviar raw sockets para ARP sin ser root
PYTHON_BIN="$(which python3)"
sudo setcap cap_net_raw,cap_net_admin=eip "$PYTHON_BIN" || true

# 6. Preparar archivo de entorno
if [ ! -f ".env" ]; then
    echo "[6/6] Creando archivo .env a partir de .env.example..."
    cp .env.example .env
    echo ">> Por favor edita el archivo .env con tu GEMINI_API_KEY y credenciales."
fi

echo "=========================================================="
echo "  ¡INSTALACIÓN COMPLETADA CON ÉXITO EN RASPBERRY PI 5!    "
echo "  Para iniciar V.I.E.R.N.E.S:                             "
echo "    ./scripts/run.sh                                      "
echo "  O instala el servicio persistente con:                  "
echo "    sudo ./scripts/setup_service.sh                       "
echo "=========================================================="
