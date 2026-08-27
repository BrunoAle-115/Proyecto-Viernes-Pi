"""
Módulo de Clasificación y Triage Inteligente de Correos con IA para V.I.E.R.N.E.S.
Descarta spam, ofertas, promociones y boletines para enfocar la atención solo en lo importante.
"""

import re
import logging
from typing import Dict, List, Any, Optional

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


# Expresiones regulares para extracción de códigos 2FA / OTP
OTP_PATTERNS = [
    re.compile(r'(?:código|code|otp|pin|clave|passcode|token|seguridad)[^\w\d]{1,10}(\d{4,8})\b', re.IGNORECASE),
    re.compile(r'\b(G-\d{6})\b'),
    re.compile(r'\b(\d{3}-\d{3})\b'),
    re.compile(r'\b(\d{6})\b')
]

PROVIDER_PATTERNS = {
    "Google": ["google", "accounts.google.com", "gmail"],
    "GitHub": ["github", "github.com"],
    "Microsoft": ["microsoft", "live.com", "outlook", "azure"],
    "Banco de Chile": ["bancochile", "banco de chile", "edwards"],
    "Santander": ["santander", "santander.cl"],
    "BancoEstado": ["bancoestado", "banco estado"],
    "MercadoPago": ["mercadopago", "mercadolibre"],
    "OpenAI": ["openai", "chatgpt"],
    "AWS": ["amazon web services", "aws"],
    "Discord": ["discord"]
}


class EmailTriageEngine:
    """Motor híbrido (Heurístico + IA) de clasificación de correos y extracción de 2FA/OTP."""

    @staticmethod
    def extract_otp(text: str) -> Optional[Dict[str, str]]:
        """Extrae códigos de verificación en dos pasos (2FA/OTP) y detecta el proveedor."""
        for pat in OTP_PATTERNS:
            match = pat.search(text)
            if match:
                code = match.group(1) if match.lastindex else match.group(0)
                # Detectar proveedor
                provider = "Servicio Web"
                text_low = text.lower()
                for prov_name, kw_list in PROVIDER_PATTERNS.items():
                    if any(k in text_low for k in kw_list):
                        provider = prov_name
                        break
                return {"code": code.replace("-", ""), "provider": provider}
        return None

    @staticmethod
    def classify_heuristically(sender: str, subject: str, snippet: str) -> Dict[str, Any]:
        """Clasificación rápida en microsegundos basada en patrones y metadatos."""
        full_text = f"{sender} {subject} {snippet}".lower()

        # 1. Detección prioritaria de Códigos 2FA / OTP
        otp_info = EmailTriageEngine.extract_otp(f"{subject} {snippet}")
        if otp_info or any(k in full_text for k in ["código de verificación", "verification code", "security code", "tu clave temporal", "código de seguridad"]):
            return {
                "is_important": True,
                "category": "OTP_2FA",
                "reason": f"Código de seguridad 2FA/OTP detectado ({otp_info['provider'] if otp_info else 'Seguridad'})",
                "priority": "CRITICAL",
                "otp": otp_info
            }

        # 2. Detección de publicidad / newsletter
        for kw in PROMOTIONAL_KEYWORDS:
            if kw in full_text:
                return {
                    "is_important": False,
                    "category": "PROMOTION",
                    "reason": f"Detectado patrón promocional '{kw}'",
                    "priority": "LOW",
                    "otp": None
                }

        # 3. Detección de remitentes automatizados no urgentes
        if any(ignored in sender.lower() for ignored in ["newsletter", "updates@", "notifications@facebook", "marketing@"]):
            return {
                "is_important": False,
                "category": "NEWSLETTER",
                "reason": "Remitente de boletín automatizado",
                "priority": "LOW",
                "otp": None
            }

        # 4. Detección de urgencia / importancia
        for kw in IMPORTANT_KEYWORDS:
            if kw in full_text:
                return {
                    "is_important": True,
                    "category": "IMPORTANT",
                    "reason": f"Contiene término clave relevante '{kw}'",
                    "priority": "HIGH",
                    "otp": None
                }

        # 5. Por defecto, si viene de una persona real o dominio propio
        if "@gmail.com" in sender or "@zoho.com" in sender or "@" in sender:
            return {
                "is_important": True,
                "category": "PERSONAL_OR_WORK",
                "reason": "Correo directo sin patrones promocionales",
                "priority": "MEDIUM",
                "otp": None
            }

        return {
            "is_important": False,
            "category": "GENERAL",
            "reason": "Baja relevancia aparente",
            "priority": "LOW",
            "otp": None
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
            if analysis.get("otp"):
                mail["otp"] = analysis["otp"]
            if analysis["is_important"]:
                important_list.append(mail)

        logger.info(f"Triage completado: {len(important_list)} de {len(raw_emails)} correos marcados como importantes.")
        return important_list
