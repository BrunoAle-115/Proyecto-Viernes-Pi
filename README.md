# 🛡️ V.I.E.R.N.E.S. (Viernes Intelligent Entity & Realtime Network Environment System)

Framework completo de **Asistente de Inteligencia Artificial Táctico** inspirado en F.R.I.D.A.Y. de Iron Man / Stark Industries, optimizado para ejecutarse en **Raspberry Pi 5 (ARM64)** con hardware local (micrófono y altavoz), control IoT autónomo con escaneo de red ARP/Nmap y Wake-on-LAN sin configuración manual de MAC, integración telefónica SIP Trunk / Asterisk para Chile, triage inteligente de correos (Gmail + Zoho) y un Dashboard HUD futurista estilo Stark Industries.

---

## 🚀 Características Principales

### 🎙️ 1. Núcleo de Voz en Tiempo Real con Gemini Live API
- **Streaming de Audio Bidireccional de Ultra-Baja Latencia**: Comunicación por WebSockets de audio PCM (16 kHz entrada / 24 kHz salida) utilizando `gemini-2.0-flash-exp` / `gemini-live` (gratis para desarrollo en el Free Tier de Google AI Studio).
- **Detección de Interrupción (Barge-in)**: Si interrumpes a V.I.E.R.N.E.S. mientras habla, el buffer de audio se vacía instantáneamente para escucharte.
- **Wake Word Local Offline**: Activación por voz con la palabra *"Viernes"* o *"Friday"* sin saturar ancho de banda de red.
- **Personalidad Stark Industries**: Respuestas tácticas, concisas y elegantes, refiriéndose al usuario como *"Señor"* o *"Jefe"*.

### ⚡ 2. IoT Autónomo & Wake-on-LAN Zero-Configuration
- **Auto-Descubrimiento ARP / Nmap / SSDP**: Escanea la red local y detecta automáticamente fabricantes (ASUS, MSI, Gigabyte, Espressif, Yeelight, Shelly, Tuya, Raspberry Pi).
- **Mapeo Transparente IP <-> MAC**: Ya no necesitas buscar ni memorizar direcciones MAC. Solo dile *"Viernes, enciende mi PC Gamer"* y el sistema resuelve la MAC, envía el Magic Packet UDP y monitorea el arranque mediante sondeos ICMP/TCP hasta confirmar que está en línea.
- **Control de Iluminación y Enchufes**: Control directo por TCP/HTTP/REST de Yeelight, Tasmota, Shelly, Tuya y enchufes inteligentes.

### 🇨🇱 3. Telefonía SIP Trunk & Asterisk para Chile
- **Compatibilidad con Proveedores Económicos en Chile**:
  - **Zadarma Chile**: DIDs locales chilenos (+56 2 / +56 9) con cobro por segundo y sin contrato forzoso (ideal persona natural).
  - **Redvoiss Chile**: Operador VoIP nacional chileno de alta fidelidad.
  - **Twilio Elastic SIP Trunk (Chile)**.
  - **Net2Phone Chile**.
- **Marcación Saliente Automatizada**: V.I.E.R.N.E.S. puede llamar a tu celular chileno (`+569XXXXXXXX`) para alertas críticas o recordatorios.
- **Atención de Llamadas Entrantes**: Puedes llamar a tu asistente por teléfono y hablar en tiempo real con la IA mediante Asterisk ARI/AudioSocket.
- **Dialplan Normativo SUBTEL**: Validación de 9 dígitos nacionales y enrutamiento prioritario de emergencias (SAMU 131, Bomberos 132, Carabineros 133).

### 📧 4. Smart Inbox: Gmail + Zoho Mail con Filtro IA
- **Conectores Duales**: Integración con Google Gmail API (OAuth2) y Zoho Mail (IMAP seguro).
- **Triage Inteligente**: Filtro heurístico + LLM que **descarta automáticamente más del 80% del correo basura** (promociones, cupones, newsletters, notificaciones automáticas). Al preguntarle *"¿Qué correos tengo?"*, solo te informará sobre correos urgentes de clientes, transferencias bancarias, incidentes de servidores o mensajes de trabajo importantes.

### 🐙 5. Monitor de GitHub & Pull Requests
- Monitoreo continuo de repositorios: Detección de Pull Requests aprobadas (`APPROVED`), cambios solicitados por reviewers (`CHANGES_REQUESTED`), conflictos de merge y estado de workflows en GitHub Actions CI/CD.

### ⏰ 6. Planificador de Alarmas & Morning Briefing
- Alarmas persistentes con SQLite y APScheduler.
- **Informe Matutino ("Morning Briefing")**: Al despertar, V.I.E.R.N.E.S. resume el estado de la Raspberry Pi 5 (temperatura CPU, RAM), correos importantes pendientes y el estado de tus PRs en GitHub.

### 🖥️ 7. Stark Industries Cyberpunk HUD Dashboard
- **Interfaz Web Reactiva**: Diseñada en Dark Glassmorphism con acentos Cyan Neón y Oro de Reactor Arc.
- **Visualizador Holográfico**: Canvas animado de espectro de onda de audio en tiempo real reactivo al micrófono y a la voz de la IA.
- **Matriz de Dispositivos 1-Click**: Botones de encendido WoL y control de luces en vivo.
- **Telemetría de la Pi 5**: Monitoreo de temperatura de CPU, carga de núcleos, uso de memoria RAM e IP local a través de WebSockets a 10 Hz.

---

## 🏗️ Arquitectura del Sistema

```
V.I.E.R.N.E.S/
├── config/
│   ├── config.yaml.example       # Configuración central del sistema
│   └── asterisk/                 # Archivos de configuración Asterisk (PJSIP, Dialplan)
├── viernes/
│   ├── main.py                   # Entrypoint principal de V.I.E.R.N.E.S
│   ├── core/
│   │   ├── gemini_live.py        # Streaming WebSocket Gemini Multimodal Live API
│   │   ├── audio_pipeline.py     # Pipeline de audio PCM duplex (16kHz / 24kHz)
│   │   ├── wake_word.py          # Detección offline "Viernes" / "Friday"
│   │   ├── tools_registry.py     # Function Calling & Dispatcher de herramientas
│   │   ├── telemetry.py          # Monitor de temperatura CPU, RAM y hardware Pi 5
│   │   └── event_bus.py          # Bus asíncrono reactivo de eventos
│   ├── iot/
│   │   ├── network_scanner.py    # Escaneo ARP, Nmap y resolución IP/MAC
│   │   ├── wake_on_lan.py        # Magic Packet broadcast y verificación de booteo
│   │   ├── smart_lights.py       # Control de Yeelight, Tuya, Tasmota, Shelly
│   │   └── device_manager.py     # Base de datos persistente de dispositivos
│   ├── telephony/
│   │   ├── sip_manager.py        # Integración Asterisk AMI/ARI
│   │   └── chile_providers.py    # Presets para Zadarma, Redvoiss, Twilio CL
│   ├── mail/
│   │   ├── gmail_client.py       # Cliente OAuth2 Gmail API
│   │   ├── zoho_client.py        # Cliente IMAP Zoho Mail
│   │   └── ai_triage.py          # Filtro inteligente de spam y promociones
│   ├── integrations/
│   │   └── github_monitor.py     # Monitoreo de Pull Requests y CI/CD
│   ├── scheduler/
│   │   └── reminder_engine.py    # Alarmas, recordatorios y Morning Briefing
│   └── web/
│       ├── server.py             # Servidor FastAPI + WebSocket
│       ├── static/               # CSS Cyberpunk & JS Visualizer
│       └── templates/hud.html    # HUD Holográfico Stark Industries
├── scripts/
│   ├── install_pi5.sh            # Instalador desatendido para Raspberry Pi OS
│   ├── setup_service.sh          # Generador de servicio systemd
│   └── run.sh                    # Lanzador rápido
├── tests/
│   └── test_framework_integration.py # Suite de pruebas de integración
├── requirements.txt
└── .env.example
```

---

## 📦 Instalación Rápida en Raspberry Pi 5

### 1. Clonar el Repositorio
```bash
git clone <URL_DEL_REPO> "Proyecto Viernes Pi"
cd "Proyecto Viernes Pi"
```

### 2. Ejecutar el Instalador Automatizado
En tu Raspberry Pi 5 con **Raspberry Pi OS (Debian Bookworm 64-bit)**:
```bash
chmod +x scripts/install_pi5.sh scripts/setup_service.sh scripts/run.sh
./scripts/install_pi5.sh
```

### 3. Configurar Credenciales en `.env`
Copia `.env.example` a `.env` y añade tus claves:
```bash
cp .env.example .env
nano .env
```
Campos esenciales:
```env
# Gemini Live API Key (Google AI Studio)
GEMINI_API_KEY="AIzaSyTuClaveDeGoogleAIStudio"

# GitHub Token (opcional para monitoreo de PRs)
GITHUB_TOKEN="ghp_TuTokenPersonalDeGitHub"
GITHUB_USERNAME="tu_usuario"
GITHUB_REPOS="tu_usuario/tu_repo1,tu_usuario/Proyecto-Viernes-Pi"

# Zoho Mail (opcional)
ZOHO_EMAIL="tu_correo@tu_dominio.com"
ZOHO_PASSWORD="tu_app_password"

# SIP Provider (Zadarma Chile / Redvoiss / Twilio)
SIP_PROVIDER="zadarma_chile"
SIP_USERNAME="123456"
SIP_PASSWORD="TuPasswordSip"
SIP_DID_NUMBER="+56912345678"
```

### 4. Iniciar V.I.E.R.N.E.S.
```bash
./scripts/run.sh
```
Abre tu navegador en:
`http://localhost:8080` (o `http://<IP_DE_TU_PI5>:8080`) para ver el **Stark Industries HUD en vivo**.

### 5. Configurar Inicio Automático con el Boot (Systemd)
Para que V.I.E.R.N.E.S. arranque automáticamente cada vez que enciendes la Raspberry Pi 5:
```bash
sudo ./scripts/setup_service.sh
```

---

## 🧪 Ejecución de Tests
Para verificar el 100% de los subsistemas y tests unitarios:
```bash
pytest -v
```

---

## 📄 Licencia
Desarrollado bajo licencia **MIT**. Inspirado en el universo de Tony Stark / Marvel Comics.
