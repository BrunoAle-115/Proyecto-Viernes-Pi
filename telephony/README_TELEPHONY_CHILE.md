# 🇨🇱 Arquitectura de Telefonía SIP y Asterisk para Chile — V.I.E.R.N.E.S.

Sistema de Telefonía IP de Grado de Operador Telecom y Puente de Inteligencia Artificial para Chile, diseñado bajo las normativas técnicas de numeración de la **Subsecretaría de Telecomunicaciones (SUBTEL)** y estándares **ITU-T**.

---

## 📑 Tabla de Contenidos
1. [Visión General y Diagrama de Arquitectura](#-visión-general-y-diagrama-de-arquitectura)
2. [Proveedores SIP Trunk en Chile](#-proveedores-sip-trunk-en-chile)
3. [Normativa SUBTEL y Dialplan de Chile](#-normativa-subtel-y-dialplan-de-chile)
4. [Integración Asterisk: ARI, AMI y AudioSocket](#-integración-asterisk-ari-ami-y-audiosocket)
5. [Pipeline de Conversación en Tiempo Real y Barge-In](#-pipeline-de-conversación-en-tiempo-real-y-barge-in)
6. [Despachador de Alertas Críticas Automatizadas](#-despachador-de-alertas-críticas-automatizadas)
7. [Instalación y Despliegue con Docker](#-instalación-y-despliegue-con-docker)
8. [Configuración de Variables de Entorno](#-configuración-de-variables-de-entorno)

---

## 🏗 Visión General y Diagrama de Arquitectura

```
                  ┌────────────────────────────────────────────────────────┐
                  │                 REDES DE TELEFONÍA CHILE               │
                  │   Móviles (Entel/Movistar/WOM/Claro) - Red Fija/PSTN   │
                  └──────────────┬───────────────────────────┬─────────────┘
                                 │                           │
                   Inbound DID (+56...)           Outbound E.164 (+56...)
                                 │                           │
                                 ▼                           ▼
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │                 ASTERISK 20 LTS (PJSIP + ARI + AudioSocket)                 │
  │                                                                             │
  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────────┐   │
  │  │ Zadarma CL   │  │ Redvoiss CL  │  │ Twilio CL    │  │ Net2Phone CL   │   │
  │  │ (Santiago)   │  │ (Carrier CL) │  │ (Elastic SIP)│  │ (PBX Cloud CL) │   │
  │  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └───────┬────────┘   │
  │         └─────────────────┼─────────────────┼──────────────────┘            │
  │                           ▼                 ▼                               │
  │            [Dialplan / extensions.conf (SUBTEL 9 Dígitos)]                  │
  │                           │                                                 │
  │       ┌───────────────────┴───────────────────────┐                         │
  │       │                                           │                         │
  │       ▼ (Stasis Event Channel)                    ▼ (Full-Duplex PCM Stream)│
  │  ┌─────────┐                                 ┌─────────────┐                │
  │  │ res_ari │ (REST / WebSocket)              │ res_audiosocket│ (TCP Port 9099)│
  │  └────┬────┘                                 └──────┬──────┘                │
  └───────┼─────────────────────────────────────────────┼───────────────────────┘
          │                                             │
          ▼                                             ▼
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │                   V.I.E.R.N.E.S. TELEPHONY ENGINE (Python)                  │
  │                                                                             │
  │  ┌───────────────────────┐             ┌─────────────────────────────────┐  │
  │  │   ARI Event Listener  │             │      AudioSocket Server         │  │
  │  │ (StasisStart/Dtmf/End)│             │  (Framing 16-bit PCM 8k/16k)    │  │
  │  └──────────┬────────────┘             └────────────────┬────────────────┘  │
  │             │                                           │                   │
  │             ▼                                           ▼                   │
  │  ┌───────────────────────┐             ┌─────────────────────────────────┐  │
  │  │ Call Session Manager  │◄───────────►│   VAD & Barge-In Detector       │  │
  │  │ & Outbound Dispatcher │             │ (RMS Energy / Speech End)       │  │
  │  └──────────┬────────────┘             └────────────────┬────────────────┘  │
  │             │                                           │                   │
  │             ▼                                           ▼                   │
  │  ┌───────────────────────────────────────────────────────────────────────┐  │
  │  │             V.I.E.R.N.E.S. AI CORE PIPELINE INTERFACE                 │  │
  │  │                                                                       │  │
  │  │  [STT Whisper/ASR] ──► [V.I.E.R.N.E.S LLM Brain] ──► [TTS Natural CL]│  │
  │  └───────────────────────────────────────────────────────────────────────┘  │
  └─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🇨🇱 Proveedores SIP Trunk en Chile

El archivo [`pjsip.conf`](file:///c:/Users/bruno/Downloads/V.I.E.R.N.E.S/telephony/config/asterisk/pjsip.conf) incluye las 4 troncales principales:

| Proveedor | Enfoque Principal en Chile | Autenticación | Códecs Recomendados |
| :--- | :--- | :--- | :--- |
| **Zadarma Chile** | DIDs geográficos Santiago (+56 22), Valparaíso (+56 32), Concepción (+56 41) y móviles. | Digest Auth (`username`/`password`) | `alaw`, `ulaw`, `opus` |
| **Redvoiss** | Carrier local chileno con conexión directa a la red PSTN y peering nacional. | Digest Auth o IP fija en Santiago | `alaw` (prioritario SUBTEL), `g729` |
| **Twilio CL** | Elastic SIP Trunking con DIDs chilenos (+56) e infraestructura global de alta disponibilidad. | SIP Domain Credentials / ACL | `opus`, `alaw`, `ulaw` |
| **Net2Phone CL** | Solución empresarial con troncal SIP PBX Cloud en Chile. | Digest Auth | `alaw`, `ulaw` |

---

## 📜 Normativa SUBTEL y Dialplan de Chile

Bajo la regulación vigente de la **SUBTEL**:
- Toda llamada nacional utiliza un formato uniforme de **9 dígitos**.
- **Telefonía Móvil**: Comienza con `9` seguido de 8 dígitos (`9XXXXXXXX`). Formato internacional: `+56 9 XXXX XXXX`.
- **Red Fija Santiago (RM)**: Código de área `22` o `23` seguido de 7 dígitos (`22XXXXXXX`).
- **Red Fija Regiones**: Código de área de 2 dígitos (`32` Valparaíso, `41` Concepción, `55` Antofagasta, etc.).
- **Emergencias**: Códigos cortos nacionales:
  - `131`: SAMU (Ambulancias y Emergencias Médicas)
  - `132`: Cuerpo de Bomberos de Chile
  - `133`: Carabineros de Chile
  - `134`: PDI (Policía de Investigaciones)
  - `14XX`: Seguridad Ciudadana Municipal

El módulo [`chile_dialplan_validator.py`](file:///c:/Users/bruno/Downloads/V.I.E.R.N.E.S/telephony/src/chile_dialplan_validator.py) normaliza automáticamente cualquier número entrante o saliente para garantizar el cumplimiento normativo.

---

## ⚡ Integración Asterisk: ARI, AMI y AudioSocket

1. **ARI (Asterisk REST Interface)**:
   - Administrado a través de [`ari_client.py`](file:///c:/Users/bruno/Downloads/V.I.E.R.N.E.S/telephony/src/ari_client.py).
   - Controla el descolgado, creación de bridges, reproducción y captura de eventos DTMF.
2. **AudioSocket (`res_audiosocket`)**:
   - Administrado por [`audiosocket_server.py`](file:///c:/Users/bruno/Downloads/V.I.E.R.N.E.S/telephony/src/audiosocket_server.py).
   - Framing binario de 3 bytes + Linear PCM de 16 bits (8kHz/16kHz) para streaming bidireccional de voz en tiempo real con latencia inferior a 30 milisegundos.
3. **AMI (Asterisk Manager Interface)**:
   - Configurado en [`manager.conf`](file:///c:/Users/bruno/Downloads/V.I.E.R.N.E.S/telephony/config/asterisk/manager.conf) para monitoreo de canales, telemetría y CDRs.

---

## 🗣 Pipeline de Conversación en Tiempo Real y Barge-In

- **Detección VAD (Voice Activity Detection)**: Analiza el RMS del flujo PCM entrante.
- **Barge-In**: Si V.I.E.R.N.E.S está hablando y el usuario empieza a hablar, se dispara inmediatamente una señal de interrupción para detener el TTS, limpiar los buffers y escuchar al usuario sin solapamiento molesto.

---

## 🚨 Despachador de Alertas Críticas Automatizadas

El subsistema [`alert_dispatcher.py`](file:///c:/Users/bruno/Downloads/V.I.E.R.N.E.S/telephony/src/alert_dispatcher.py) permite originar llamadas automáticas con:
- **Cadena de Failover Multi-Carrier**: Si Zadarma no conecta, conmuta a Redvoiss -> Twilio -> Net2Phone de forma transparente.
- **Acuse de Recibo Interactivo**: El usuario puede presionar `1` en su teclado o hablar para confirmar recepción y desactivar la alerta.
- **Prioridades**: `CRITICAL`, `HIGH`, `NORMAL` con reintentos programados.

---

## 🚀 Instalación y Despliegue con Docker

1. **Configurar el archivo `.env.telephony`**:
   ```bash
   cp .env.telephony.example .env.telephony
   # Editar con las credenciales reales de Zadarma, Redvoiss, Twilio o Net2Phone
   ```

2. **Levantar el contenedor de Asterisk y el puente de IA**:
   ```bash
   docker compose -f docker-compose.telephony.yml up -d --build
   ```

3. **Verificar estado de las troncales PJSIP en Asterisk**:
   ```bash
   docker exec -it viernes-asterisk asterisk -rx "pjsip show endpoints"
   docker exec -it viernes-asterisk asterisk -rx "pjsip show registrations"
   ```

4. **Ejecutar Pruebas Unitarias**:
   ```bash
   pytest tests -v
   ```
