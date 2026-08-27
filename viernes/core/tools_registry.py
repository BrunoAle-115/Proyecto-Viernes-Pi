"""
Registro de Herramientas y Function Calling para Gemini Live en V.I.E.R.N.E.S.
Conecta las intenciones del modelo con las acciones reales del hardware, IoT, noticias, clima y memoria personal.
"""

import json
import logging
from typing import Dict, Any, List
from datetime import datetime

from viernes.iot.device_manager import device_mgr
from viernes.mail.gmail_client import gmail_client
from viernes.mail.zoho_client import zoho_client
from viernes.integrations.github_monitor import github_monitor
from viernes.scheduler.reminder_engine import reminder_engine
from viernes.telephony.sip_manager import sip_mgr
from viernes.core.telemetry import SystemTelemetry
from viernes.services.news_chile import chile_news
from viernes.services.weather_engine import weather_engine
from viernes.memory.mini_rag import personal_rag
from viernes.core.models_manager import models_manager

logger = logging.getLogger("viernes.tools")

# Declaraciones de herramientas en formato Gemini Tool Schema
GEMINI_TOOL_DECLARATIONS = [
    {
        "name": "turn_on_pc",
        "description": "Enciende un PC o computador en la red local enviando un Magic Packet Wake-on-LAN. Resuelve la MAC e IP automáticamente por nombre (ej: 'mi pc', 'pc gamer', 'computador').",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "device_name": {
                    "type": "STRING",
                    "description": "Nombre, alias o IP del computador a encender (ej. 'pc gamer', 'mi computador', '192.168.1.150')."
                }
            },
            "required": ["device_name"]
        }
    },
    {
        "name": "control_smart_light",
        "description": "Enciende, apaga o ajusta el brillo de las luces inteligentes del hogar o escritorio (Yeelight, Tuya, Tasmota, Shelly).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "target": {
                    "type": "STRING",
                    "description": "Nombre de la luz o IP (ej. 'luces escritorio', 'lampara', '192.168.1.120')."
                },
                "action": {
                    "type": "STRING",
                    "description": "Acción a realizar: 'on', 'off', 'toggle', 'brightness'."
                },
                "brightness": {
                    "type": "INTEGER",
                    "description": "Nivel de brillo de 1 a 100 si la acción es brightness o encendido."
                }
            },
            "required": ["target", "action"]
        }
    },
    {
        "name": "get_chile_news",
        "description": "Obtiene las noticias y titulares más importantes de Chile en tiempo real desde Canal 13 (T13), BioBioChile y Cooperativa.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "limit": {
                    "type": "INTEGER",
                    "description": "Número máximo de titulares a obtener (por defecto 4)."
                }
            }
        }
    },
    {
        "name": "get_weather_forecast",
        "description": "Consulta el clima actual, pronóstico por hora y probabilidad de lluvia/precipitaciones para ciudades de Chile (Santiago, Valparaíso, Concepción, etc.).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "city": {
                    "type": "STRING",
                    "description": "Ciudad de Chile a consultar (ej: 'santiago', 'valparaiso', 'concepcion')."
                }
            }
        }
    },
    {
        "name": "store_personal_memory",
        "description": "Guarda un recuerdo, preferencia personal, rutina, nota o información clave sobre el usuario en la base de datos de memoria Mini-RAG.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "category": {
                    "type": "STRING",
                    "description": "Categoría: 'routine', 'preference', 'project', 'note', 'contact'."
                },
                "key_concept": {
                    "type": "STRING",
                    "description": "Concepto clave o etiqueta única (ej: 'cumpleanos_mama', 'rutina_ejercicio', 'preferencia_cafe')."
                },
                "content": {
                    "type": "STRING",
                    "description": "Detalle completo de la memoria a recordar."
                }
            },
            "required": ["category", "key_concept", "content"]
        }
    },
    {
        "name": "recall_personal_memory",
        "description": "Recupera recuerdos, rutinas o preferencias guardadas del usuario consultando el Mini-RAG.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {
                    "type": "STRING",
                    "description": "Término de búsqueda o pregunta sobre lo que se desea recordar."
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "scan_local_network",
        "description": "Escanea la red local con ARP/Nmap para descubrir nuevos dispositivos, PCs, luces y actualizar el mapa de IPs y MACs.",
        "parameters": {
            "type": "OBJECT",
            "properties": {}
        }
    },
    {
        "name": "get_important_emails",
        "description": "Obtiene y resume los correos electrónicos importantes no leídos de Gmail y Zoho Mail, descartando automáticamente spam, promociones y boletines.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "source": {
                    "type": "STRING",
                    "description": "Fuente a consultar: 'all' (por defecto), 'gmail', o 'zoho'."
                }
            }
        }
    },
    {
        "name": "check_github_status",
        "description": "Consulta el estado de las Pull Requests en GitHub, verificando si fueron aprobadas, si tienen cambios solicitados o si el CI/CD pasó.",
        "parameters": {
            "type": "OBJECT",
            "properties": {}
        }
    },
    {
        "name": "set_alarm_or_reminder",
        "description": "Configura una alarma o un recordatorio con fecha/hora específica para que V.I.E.R.N.E.S. lo anuncie por voz o sonido.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "title": {
                    "type": "STRING",
                    "description": "Motivo del recordatorio o alarma (ej. 'Reunión con el equipo', 'Despertar')."
                },
                "time_iso": {
                    "type": "STRING",
                    "description": "Fecha y hora en formato ISO (ej. '2026-08-27T08:30:00') o hora relativa."
                },
                "is_alarm": {
                    "type": "BOOLEAN",
                    "description": "True si es una alarma sonora despertador, False si es un recordatorio de voz."
                }
            },
            "required": ["title", "time_iso"]
        }
    },
    {
        "name": "make_phone_call",
        "description": "Realiza una llamada telefónica hacia un número celular en Chile (+569XXXXXXXX) mediante la troncal SIP.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "phone_number": {
                    "type": "STRING",
                    "description": "Número de teléfono destino en Chile (ej. '+56912345678')."
                },
                "reason": {
                    "type": "STRING",
                    "description": "Motivo de la llamada para que VIERNES lo sepa."
                }
            },
            "required": ["phone_number"]
        }
    },
    {
        "name": "get_system_telemetry",
        "description": "Obtiene la telemetría en tiempo real de la Raspberry Pi 5 (temperatura CPU, RAM, uptime, IP).",
        "parameters": {
            "type": "OBJECT",
            "properties": {}
        }
    },
    {
        "name": "get_morning_briefing",
        "description": "Genera el informe matutino consolidado con telemetría del sistema, clima con alerta de lluvia, noticias de Chile, correos importantes y estado de GitHub.",
        "parameters": {
            "type": "OBJECT",
            "properties": {}
        }
    }
]


class ToolsDispatcher:
    """Ejecutor de herramientas invocadas por Gemini Live."""

    @classmethod
    async def execute_tool(cls, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"Ejecutando herramienta invocada por IA: {name} con argumentos: {args}")
        try:
            if name == "turn_on_pc":
                target = args.get("device_name", "pc_principal")
                return await device_mgr.execute_turn_on(target)

            elif name == "control_smart_light":
                target = args.get("target", "luces_escritorio")
                action = args.get("action", "toggle")
                brightness = args.get("brightness", 100)
                return await device_mgr.execute_control_light(target, state=action, brightness=brightness)

            elif name == "get_chile_news":
                limit = args.get("limit", 4)
                news = await chile_news.get_top_news(limit=limit)
                summary_voice = await chile_news.get_voice_news_briefing()
                return {"success": True, "count": len(news), "news": news, "voice_summary": summary_voice}

            elif name == "get_weather_forecast":
                city = args.get("city", "santiago")
                weather = await weather_engine.get_forecast(city)
                voice_summary = await weather_engine.get_voice_weather_summary(city)
                return {"success": True, "weather": weather, "voice_summary": voice_summary}

            elif name == "store_personal_memory":
                cat = args.get("category", "note")
                key = args.get("key_concept", "nota_general")
                content = args.get("content", "")
                return await personal_rag.store_memory(category=cat, key_concept=key, content=content)

            elif name == "recall_personal_memory":
                query = args.get("query", "")
                memories = await personal_rag.recall_memories(query=query)
                return {"success": True, "count": len(memories), "memories": memories}

            elif name == "scan_local_network":
                devices = await device_mgr.scan_and_update()
                return {"success": True, "count": len(devices), "devices": devices}

            elif name == "get_important_emails":
                src = args.get("source", "all")
                gmail_mails = []
                zoho_mails = []
                if src in ("all", "gmail"):
                    gmail_mails = await gmail_client.get_unread_emails(max_results=5, only_important=True)
                if src in ("all", "zoho"):
                    zoho_mails = zoho_client.get_unread_emails(max_results=5, only_important=True)
                
                all_mails = gmail_mails + zoho_mails
                return {
                    "success": True,
                    "total_important": len(all_mails),
                    "emails": all_mails,
                    "summary": f"Se encontraron {len(all_mails)} correos importantes pendientes."
                }

            elif name == "check_github_status":
                return await github_monitor.get_pull_requests_summary()

            elif name == "set_alarm_or_reminder":
                title = args.get("title", "Recordatorio")
                time_iso = args.get("time_iso", datetime.now().isoformat())
                is_alarm = args.get("is_alarm", False)
                return await reminder_engine.add_reminder(title=title, remind_time=time_iso, is_alarm=is_alarm)

            elif name == "make_phone_call":
                phone = args.get("phone_number", "")
                return await sip_mgr.originate_call(phone)

            elif name == "get_system_telemetry":
                return SystemTelemetry.get_full_status()

            elif name == "get_morning_briefing":
                text = await reminder_engine.generate_morning_briefing()
                return {"success": True, "briefing_text": text}

            else:
                return {"success": False, "error": f"Herramienta '{name}' no reconocida."}
        except Exception as e:
            logger.error(f"Error ejecutando herramienta {name}: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
