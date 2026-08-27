"""
Configuración central y parámetros de hardware/red para V.I.E.R.N.E.S.
"""

import os
from pathlib import Path

# Cargar variables de entorno desde .env de forma segura
env_path = Path(__file__).resolve().parent.parent / ".env"
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=env_path)
except ImportError:
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())

# API de Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "models/gemini-2.0-flash-exp")
GEMINI_WS_URL = "wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1alpha.GenerativeService.BidiGenerateContent"
VOICE_NAME = os.getenv("VOICE_NAME", "Aoede")  # Aoede, Puck, Charon, Kore, Fenrir

# Configuración de Audio
# Entrada: 16 kHz, 16-bit PCM Mono (1 canal, Little Endian)
AUDIO_INPUT_SAMPLE_RATE = 16000
AUDIO_INPUT_CHANNELS = 1
AUDIO_INPUT_CHUNK_SIZE = 512  # ~32ms por paquete para latencia ultrabaja
AUDIO_INPUT_MIME = "audio/pcm;rate=16000"

# Salida: 24 kHz, 16-bit PCM Mono (1 canal, Little Endian)
AUDIO_OUTPUT_SAMPLE_RATE = 24000
AUDIO_OUTPUT_CHANNELS = 1
AUDIO_OUTPUT_CHUNK_SIZE = 1024
AUDIO_OUTPUT_MIME = "audio/pcm;rate=24000"

# Home Assistant / IoT
HASS_URL = os.getenv("HASS_URL", "http://homeassistant.local:8123")
HASS_TOKEN = os.getenv("HASS_TOKEN", "")

# Email (IMAP)
EMAIL_HOST = os.getenv("EMAIL_HOST", "imap.gmail.com")
EMAIL_USER = os.getenv("EMAIL_USER", "")
EMAIL_PASS = os.getenv("EMAIL_PASS", "")

# GitHub
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")

# Red / Wake-on-LAN
DEFAULT_BROADCAST_IP = os.getenv("DEFAULT_BROADCAST_IP", "192.168.1.255")
