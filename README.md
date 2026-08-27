# 🛡️ V.I.E.R.N.E.S. 2.0 (Viernes Intelligent Entity & Realtime Network Environment System)

Framework completo de **Asistente de Inteligencia Artificial Táctico** inspirado en F.R.I.D.A.Y. de Iron Man / Stark Industries, optimizado para ejecutarse en **Raspberry Pi 5 (ARM64)** con hardware local (micrófono y altavoz), control IoT autónomo con escaneo de red ARP/Nmap y Wake-on-LAN sin configuración manual de MAC, integración telefónica SIP Trunk / Asterisk para Chile (puertos 5060/5061 TLS), memoria vectorial semántica (768-dim RAG auto-alimentado), noticias nacionales de Chile (Canal 13 / T13), clima por hora con detección de lluvia, triage inteligente de correos (Gmail + Zoho) y un Dashboard HUD futurista protegido contra IDOR, XSS y WebRTC Hacking.

---

## 🚀 Características Principales

### 🎙️ 1. Núcleo de Voz en Tiempo Real con Gemini Live API
- **Streaming de Audio Bidireccional de Ultra-Baja Latencia**: Comunicación por WebSockets de audio PCM (16 kHz entrada / 24 kHz salida) utilizando `gemini-2.0-flash-exp` o `gemini-1.5-flash` en Google AI Studio.
- **Detección de Interrupción (Barge-in)**: Si interrumpes a V.I.E.R.N.E.S. mientras habla, el buffer de salida se vacía instantáneamente (<5ms) para escucharte.
- **Wake Word Local Offline**: Activación por voz con la palabra *"Oye Viernes"*, *"Viernes"* o *"Friday"* sin saturar ancho de banda de red.
- **Personalidad Stark Industries**: Respuestas tácticas, concisas y elegantes, refiriéndose al usuario como *"Señor"* o *"Jefe"*.

### 🧠 2. Base de Datos Vectorial 768-Dim & Auto-Feeding Mini-RAG
- **Espacio Vectorial Denso**: Embeddings de 768 dimensiones (`models/text-embedding-004` con fallback determinístico local).
- **Búsqueda Semántica por Coseno**: Búsqueda ultrarrápida ($Sim(A, B) = \frac{A \cdot B}{\|A\| \|B\|}$) con scoring híbrido léxico y semántico.
- **Auto-Alimentación Contextual (`AutoMemoryFeeder`)**: Escucha tus conversaciones en tiempo real y extrae automáticamente preferencias, hábitos, rutinas laborales y ubicaciones, guardándolos sin intervención manual.

### 🇨🇱 3. Noticias de Chile & Clima de Alta Precisión
- **Noticias Nacionales (T13 / BioBioChile / Cooperativa)**: Scraper y parser RSS resiliente con síntesis oral de 30 segundos para briefings matutinos.
- **Clima Open-Meteo de Chile**: Pronóstico en tiempo real y por hora para Santiago, Valparaíso, Concepción y más de 10 ciudades, con cálculo exacto de probabilidad y volumen de lluvia (mm).

### ⚡ 4. IoT Autónomo & Wake-on-LAN Zero-Configuration
- **Auto-Descubrimiento ARP / Nmap / SSDP**: Escanea la red local y detecta automáticamente fabricantes (ASUS, MSI, Gigabyte, Espressif, Yeelight, Shelly, Tuya, Raspberry Pi).
- **Mapeo Transparente IP <-> MAC**: Ya no necesitas buscar ni memorizar direcciones MAC. Solo dile *"Viernes, enciende mi PC Gamer"* y el sistema resuelve la MAC, envía el Magic Packet UDP y monitorea el arranque mediante sondeos ICMP/TCP.
- **Control de Iluminación y Enchufes**: Control directo por TCP/HTTP/REST de Yeelight, Tasmota, Shelly, Tuya y enchufes inteligentes.

### 📞 5. Telefonía SIP Trunk & Asterisk para Chile (Puertos 5060 & 5061 TLS)
- **Compatibilidad con Proveedores Económicos en Chile**:
  - **Zadarma Chile**: DIDs locales chilenos (+56 2 / +56 9) con cobro por segundo y sin contrato forzoso (ideal persona natural).
  - **Redvoiss Chile**: Operador VoIP nacional chileno de alta fidelidad.
  - **Twilio Elastic SIP Trunk (Chile)** y **Net2Phone Chile**.
- **Puente con AudioSocket (TCP 9099)**: Streaming de audio full-duplex de 16-bit PCM entre Asterisk y la IA.
- **Hardening Telefónico**: Transporte UDP/TCP en puerto 5060, TLS 1.3/1.2 en puerto 5061 (SIPS), SRTP para cifrado de medios y `always_auth_reject=yes` contra escaneos SIPVicious.

### 📧 6. Smart Inbox: Gmail + Zoho Mail con Filtro IA
- **Conectores Duales**: Integración con Google Gmail API (OAuth2) y Zoho Mail (IMAP seguro).
- **Triage Inteligente**: Filtro heurístico + LLM que **descarta más del 80% del correo basura** (promociones, newsletters, notificaciones automáticas). Al preguntarle *"¿Qué correos tengo?"*, solo te informará sobre correos urgentes, códigos 2FA/OTP o mensajes de trabajo importantes.

### 🐙 7. Monitor de GitHub & Pull Requests
- Monitoreo continuo de repositorios de `BrunoAle-115`: Detección de Pull Requests aprobadas (`APPROVED`), cambios solicitados por reviewers (`CHANGES_REQUESTED`), conflictos de merge y estado de workflows en GitHub Actions CI/CD.

### 🛡️ 8. Seguridad Integral, Anti-IDOR & Recuperación CLI
- **Criptografía Militar**: Passwords protegidas con **PBKDF2-HMAC-SHA256 (600,000 rondas + 16 bytes salt)** y tokens de sesión firmados con HMAC-SHA256.
- **Protección Anti-IDOR & Anti-XSS**: Verificación obligatoria de sesión en cada endpoint de API (`get_current_user`), escapado HTML de doble capa y cabeceras CSP estrictas.
- **Recuperación Fuera de Banda (OOB)**: La recuperación de contraseña **solo está permitida vía consola CLI** (`python scripts/reset_password.py`), nunca expuesta vía web para evitar ataques de toma de control de cuenta.
- **Gestor de Auto-Switching de Puertos (`DynamicPortManager`)**: Si el puerto 9090 está ocupado, conmuta automáticamente a puertos 9091+ auditando la coexistencia con Pi-hole (puertos 53/80) y Asterisk (5060/5061).

---

## 🏗️ Arquitectura del Sistema

```
V.I.E.R.N.E.S/
├── easy_install.sh               # Instalador de 1 comando para Raspberry Pi OS
├── pytest.ini                    # Configuración de pruebas unitarias
├── requirements.txt              # Dependencias completas del framework
├── .env.example                  # Plantilla maestra de variables de entorno
├── viernes/
│   ├── main.py                   # Entrypoint con auto-switching de puertos
│   ├── core/
│   │   ├── port_manager.py       # Gestor dinámico de puertos y colisiones
│   │   ├── gemini_live.py        # Cliente WebSocket Gemini Multimodal Live
│   │   ├── audio_pipeline.py     # Pipeline de audio dúplex con RMS Ballistics
│   │   ├── tools_registry.py     # Despachador central de herramientas
│   │   ├── telemetry.py          # Telemetría de CPU, RAM, throttled y red Pi 5
│   │   └── event_bus.py          # Bus asíncrono reactivo de eventos
│   ├── auth/
│   │   ├── security.py           # PBKDF2 (600k iter), HMAC tokens, Rate Limiter
│   │   └── manager.py            # Base de datos SQLite de usuarios y permisos
│   ├── memory/
│   │   └── vector_rag.py         # Base de datos vectorial 768-dim & AutoMemoryFeeder
│   ├── services/
│   │   ├── news_chile.py         # Scraper de noticias T13 / BioBio / Cooperativa
│   │   └── weather_engine.py     # Pronóstico de clima y lluvia Open-Meteo Chile
│   ├── iot/
│   │   ├── network_scanner.py    # Escaneo ARP, Nmap y resolución IP/MAC
│   │   ├── wake_on_lan.py        # Magic Packet broadcast y verificación ICMP
│   │   ├── smart_lights.py       # Control de Yeelight, Tuya, Tasmota, Shelly
│   │   └── device_manager.py     # Base de datos persistente de dispositivos
│   ├── telephony/
│   │   ├── sip_manager.py        # Gestor SIP Asterisk AMI/ARI
│   │   └── chile_providers.py    # Presets Zadarma, Redvoiss, Twilio CL
│   └── web/
│       ├── server.py             # FastAPI con CSP, Anti-IDOR y WebSockets
│       ├── static/               # CSS Cyberpunk & Quantum Arc Reactor JS
│       └── templates/hud.html    # HUD Holográfico Stark Industries
├── telephony/
│   ├── telephony_engine/         # Motor industrial AudioSocket & Dialplan Chile
│   ├── config/asterisk/          # pjsip.conf (5060/5061 TLS), extensions.conf
│   └── docker-compose.telephony.yml
├── scripts/
│   └── reset_password.py         # Herramienta CLI interactiva y OOB para reset de password
└── tests/                        # Suite completa de pruebas con pytest
```

---

## 📦 Instalación Rápida en Raspberry Pi 5

### Método 1: Easy Install (1 Solo Comando)
En tu Raspberry Pi 5 con **Raspberry Pi OS (Debian 12 Bookworm 64-bit)**:
```bash
git clone https://github.com/BrunoAle-115/Proyecto-Viernes-Pi.git "V.I.E.R.N.E.S"
cd "V.I.E.R.N.E.S"
chmod +x easy_install.sh
./easy_install.sh
```
*El instalador realiza el pre-flight check, instala las dependencias de ALSA/Python/Nmap, configura permisos de red `cap_net_raw`, crea el `.venv`, verifica los tests y activa el servicio systemd `viernes.service`.*

### Método 2: Configuración Manual y Arranque
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edita tu GEMINI_API_KEY en .env
python viernes/main.py
```

Abre tu navegador en:
`http://localhost:9090` (o `http://<IP_DE_TU_PI5>:9090` o tu IP de Tailscale) para acceder al **Stark Industries HUD Dashboard**.

---

## 🔐 Recuperación de Contraseña por CLI (Fuera de Banda)

Por diseño de seguridad estricto, **la contraseña no puede ser recuperada vía web**. Si necesitas restablecerla o cambiarla:

```bash
# Modo interactivo táctico con validación de seguridad
python3 scripts/reset_password.py

# O asignación directa para un correo específico
python3 scripts/reset_password.py --email brunourrea502@gmail.com --password "TuNuevaContraseñaSegura123!"
```

---

## 🧪 Ejecución de Tests Automatizados

Para verificar el 100% de los subsistemas y suites de prueba:
```bash
pytest -v
```

---
*V.I.E.R.N.E.S. 2.0 // Stark Industries Tactical AI Framework // Developed for BrunoAle-115*
