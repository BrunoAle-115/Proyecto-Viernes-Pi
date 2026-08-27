"""
Definición de las declaraciones de funciones y esquemas de herramientas para Gemini Multimodal Live API.
"""

from typing import List, Dict, Any

GEMINI_TOOLS_DECLARATIONS: List[Dict[str, Any]] = [
    {
        "name": "wake_on_lan",
        "description": "Envía un paquete mágico Wake-on-LAN (WoL) para encender un equipo o servidor remoto en la red local.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "mac_address": {
                    "type": "STRING",
                    "description": "Dirección MAC del dispositivo de destino en formato 'XX:XX:XX:XX:XX:XX' o 'XX-XX-XX-XX-XX-XX'."
                },
                "broadcast_ip": {
                    "type": "STRING",
                    "description": "Dirección IP de difusión de la subred (por defecto 192.168.1.255 o 255.255.255.255)."
                },
                "port": {
                    "type": "INTEGER",
                    "description": "Puerto UDP para el paquete mágico (por defecto 9 o 7)."
                },
                "device_alias": {
                    "type": "STRING",
                    "description": "Nombre coloquial del equipo para el registro (e.g. 'workstation', 'servidor_taller', 'nas')."
                }
            },
            "required": ["mac_address"]
        }
    },
    {
        "name": "control_lights",
        "description": "Controla luces inteligentes y domótica (Home Assistant / Philips Hue / MQTT): encender, apagar, regular brillo, cambiar color o activar escenas.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "Acción a realizar sobre la iluminación.",
                    "enum": ["turn_on", "turn_off", "toggle", "set_brightness", "set_color", "activate_scene"]
                },
                "room_or_device": {
                    "type": "STRING",
                    "description": "Habitación, área o identificador de entidad (e.g. 'laboratorio', 'oficina', 'taller', 'light.escritorio_principal', 'all')."
                },
                "brightness_pct": {
                    "type": "INTEGER",
                    "description": "Nivel de brillo en porcentaje (1 a 100)."
                },
                "rgb_color": {
                    "type": "ARRAY",
                    "description": "Color en formato RGB [R, G, B] con valores de 0 a 255.",
                    "items": {
                        "type": "INTEGER"
                    }
                },
                "scene_name": {
                    "type": "STRING",
                    "description": "Nombre de la escena a activar si la acción es 'activate_scene' (e.g. 'modo_concentracion', 'noche', 'alerta_roja', 'cine')."
                }
            },
            "required": ["action", "room_or_device"]
        }
    },
    {
        "name": "manage_alarms_timers",
        "description": "Administra temporizadores y alarmas del sistema: crear temporizador por segundos/minutos, programar alarma horaria, listar activos o cancelar.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "Operación con el temporizador o alarma.",
                    "enum": ["set_timer", "set_alarm", "cancel", "list_active"]
                },
                "duration_seconds": {
                    "type": "INTEGER",
                    "description": "Duración en segundos para un nuevo temporizador (e.g. 300 para 5 minutos)."
                },
                "time_str": {
                    "type": "STRING",
                    "description": "Hora programada para una alarma en formato HH:MM (e.g. '07:30', '18:45')."
                },
                "label": {
                    "type": "STRING",
                    "description": "Etiqueta o motivo del temporizador/alarma (e.g. 'Revisar compilación', 'Reunión de equipo')."
                },
                "target_id": {
                    "type": "STRING",
                    "description": "Identificador único de la alarma o temporizador para cancelar."
                }
            },
            "required": ["action"]
        }
    },
    {
        "name": "check_emails",
        "description": "Accede a la bandeja de correo electrónico (IMAP/Gmail API) para leer, buscar y resumir correos no leídos o mensajes importantes.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "folder": {
                    "type": "STRING",
                    "description": "Carpeta a consultar (por defecto 'INBOX')."
                },
                "unread_only": {
                    "type": "BOOLEAN",
                    "description": "Si es True, sólo consulta mensajes no leídos."
                },
                "limit": {
                    "type": "INTEGER",
                    "description": "Cantidad máxima de correos a recuperar (por defecto 5)."
                },
                "search_query": {
                    "type": "STRING",
                    "description": "Filtro de búsqueda específico (e.g. 'from:boss', 'subject:alerta', 'urgent')."
                }
            },
            "required": []
        }
    },
    {
        "name": "github_operations",
        "description": "Interactúa con la API de GitHub: consulta el estado de la integración continua (CI/CD workflows), listas de issues, creación de incidencias o pull requests pendientes.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "Operación de GitHub a ejecutar.",
                    "enum": ["get_repo_status", "check_ci_workflow", "list_issues", "create_issue", "list_pull_requests", "trigger_workflow"]
                },
                "repo": {
                    "type": "STRING",
                    "description": "Nombre del repositorio en formato 'propietario/repo' (o nombre por defecto configurado)."
                },
                "issue_title": {
                    "type": "STRING",
                    "description": "Título para crear un nuevo issue."
                },
                "issue_body": {
                    "type": "STRING",
                    "description": "Cuerpo o descripción para un nuevo issue."
                },
                "workflow_id": {
                    "type": "STRING",
                    "description": "Nombre del archivo del workflow (e.g. 'ci.yml') o su ID numérico."
                },
                "ref": {
                    "type": "STRING",
                    "description": "Rama o commit de referencia (por defecto 'main')."
                }
            },
            "required": ["action"]
        }
    }
]


def get_gemini_tools_payload() -> List[Dict[str, Any]]:
    """Devuelve la estructura formateada para la llamada 'setup' de Gemini Live API."""
    return [
        {
            "functionDeclarations": GEMINI_TOOLS_DECLARATIONS
        }
    ]
