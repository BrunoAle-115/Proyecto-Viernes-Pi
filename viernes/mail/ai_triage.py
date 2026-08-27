"""
Módulo de Clasificación y Triage Inteligente de Correos con IA para V.I.E.R.N.E.S.
Descarta spam, ofertas, promociones y boletines para enfocar la atención solo en lo importante.
"""

import re
import logging
from typing import Dict, List, Any

logger = logging.getLogger("viernes.mail.triage")

# Palabras clave y remitentes típicos de publicidad / promociones / spam
PROMOTIONAL_KEYWORDS = [
    "descuento", "oferta", "sale", "cyber", "black friday", "promoción", "rebajas",
    "cupón", "gratis", "newsletter", "suscripción", "no-reply@marketing",
    "unsubscribe", "anuncie", "liquidación", "tarjeta", "préstamo preaprobado",
    "50% off", "compra ahora", "ofertas exclusivas", "digest", "semanal"
]

IMPORTANT_KEYWORDS = [
    "urgente", "factura", "pago", "aprobado", "rechazado", "contrato",
    "reunión", "entrevista", "seguridad", "alerta", "servidor", "caída",
    "soporte", "transferencia", "clave", "código de verificación", "banco",
    "pr review", "pull request", "merge", "deploy", "producción"
]


class EmailTriageEngine:
    """Motor híbrido (Heurístico + IA) de clasificación de correos."""

    @staticmethod
    def classify_heuristically(sender: str, subject: str, snippet: str) -> Dict[str, Any]:
        """Clasificación rápida en microsegundos basada en patrones y metadatos."""
        text = f"{sender} {subject} {snippet}".lower()

        # 1. Detección de publicidad / newsletter
        for kw in PROMOTIONAL_KEYWORDS:
            if kw in text:
                return {
                    "is_important": False,
                    "category": "PROMOTION",
                    "reason": f"Detectado patrón promocional '{kw}'",
                    "priority": "LOW",
                }

        # 2. Detección de remitentes automatizados no urgentes
        if any(ignored in sender.lower() for ignored in ["newsletter", "updates@", "notifications@facebook", "marketing@"]):
            return {
                "is_important": False,
                "category": "NEWSLETTER",
                "reason": "Remitente de boletín automatizado",
                "priority": "LOW",
            }

        # 3. Detección de urgencia / importancia
        for kw in IMPORTANT_KEYWORDS:
            if kw in text:
                return {
                    "is_important": True,
                    "category": "IMPORTANT",
                    "reason": f"Contiene término clave relevante '{kw}'",
                    "priority": "HIGH",
                }

        # 4. Por defecto, si viene de una persona real o dominio propio
        if "@gmail.com" in sender or "@zoho.com" in sender or "@" in sender:
            return {
                "is_important": True,
                "category": "PERSONAL_OR_WORK",
                "reason": "Correo directo sin patrones promocionales",
                "priority": "MEDIUM",
            }

        return {
            "is_important": False,
            "category": "GENERAL",
            "reason": "Baja relevancia aparente",
            "priority": "LOW",
        }

    @classmethod
    def filter_important_emails(cls, raw_emails: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filtra una lista de correos y retorna únicamente los que ameritan la atención del usuario."""
        important_list = []
        for mail in raw_emails:
            analysis = cls.classify_heuristically(
                sender=mail.get("sender", ""),
                subject=mail.get("subject", ""),
                snippet=mail.get("snippet", mail.get("body", "")[:200])
            )
            mail["triage"] = analysis
            if analysis["is_important"]:
                important_list.append(mail)

        logger.info(f"Triage completado: {len(important_list)} de {len(raw_emails)} correos marcados como importantes.")
        return important_list
