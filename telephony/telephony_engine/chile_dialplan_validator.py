"""
V.I.E.R.N.E.S. - Validador y Normalizador de Numeración Telefónica para Chile (SUBTEL)
========================================================================================
Cumplimiento de la normativa de numeración de la Subsecretaría de Telecomunicaciones (SUBTEL):
- Formato Nacional Único: 9 dígitos para todas las llamadas (fijas y móviles).
- Móviles: Prefijo 9 seguido de 8 dígitos (ej: 9 1234 5678).
- Red Fija Región Metropolitana (Santiago): Código de área 22 o 23 + 7 dígitos (ej: 22 123 4567).
- Red Fija Regiones: Códigos de área de 2 dígitos (ej: 32 Valparaíso, 41 Concepción, 55 Antofagasta, 51 La Serena).
- Servicios de Emergencia y Utilidad Pública: 131 (SAMU), 132 (Bomberos), 133 (Carabineros), 134 (PDI), 137 (Rescate Marítimo), 130 (CONAF), 14XX (Seguridad Ciudadana).
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple


class PhoneNumberType(Enum):
    MOBILE = "mobile"
    LANDLINE = "landline"
    EMERGENCY = "emergency"
    MUNICIPAL = "municipal"
    SPECIAL = "special"
    UNKNOWN = "unknown"


@dataclass
class ChileanNumberInfo:
    raw_number: str
    is_valid: bool
    number_type: PhoneNumberType
    digits_9: Optional[str]  # 9 dígitos estándar Chile
    e164: Optional[str]      # +56XXXXXXXXX
    formatted_national: Optional[str] # Ej: "+56 9 1234 5678"
    region: Optional[str]
    carrier_hint: Optional[str]
    description: str


class ChileDialplanValidator:
    """
    Valida, clasifica y normaliza números telefónicos bajo la regulación chilena.
    """

    # Mapeo de códigos de área fija según SUBTEL
    AREA_CODES_CHILE = {
        "22": ("Región Metropolitana (Santiago)", "Fija"),
        "23": ("Región Metropolitana (Santiago)", "Fija"),
        "32": ("Región de Valparaíso (Valparaíso/Viña del Mar)", "Fija"),
        "33": ("Región de Valparaíso (Quillota/La Calera)", "Fija"),
        "34": ("Región de Valparaíso (Los Andes/San Felipe)", "Fija"),
        "35": ("Región de Valparaíso (San Antonio)", "Fija"),
        "41": ("Región del Biobío (Concepción/Talcahuano)", "Fija"),
        "42": ("Región de Ñuble (Chillán)", "Fija"),
        "43": ("Región del Biobío (Los Ángeles)", "Fija"),
        "45": ("Región de la Araucanía (Temuco)", "Fija"),
        "51": ("Región de Coquimbo (La Serena/Coquimbo)", "Fija"),
        "52": ("Región de Atacama (Copiapó)", "Fija"),
        "53": ("Región de Coquimbo (Ovalle)", "Fija"),
        "55": ("Región de Antofagasta (Antofagasta/Calama)", "Fija"),
        "57": ("Región de Tarapacá (Iquique)", "Fija"),
        "58": ("Región de Arica y Parinacota (Arica)", "Fija"),
        "61": ("Región de Magallanes (Punta Arenas)", "Fija"),
        "63": ("Región de Los Ríos (Valdivia)", "Fija"),
        "64": ("Región de Los Lagos (Osorno)", "Fija"),
        "65": ("Región de Los Lagos (Puerto Montt/Chiloé)", "Fija"),
        "67": ("Región de Aysén (Coyhaique)", "Fija"),
        "71": ("Región del Maule (Talca)", "Fija"),
        "72": ("Región de O'Higgins (Rancagua)", "Fija"),
        "73": ("Región del Maule (Linares)", "Fija"),
        "75": ("Región del Maule (Curicó)", "Fija"),
    }

    EMERGENCY_NUMBERS = {
        "131": "SAMU (Ambulancias / Urgencias Médicas)",
        "132": "Cuerpo de Bomberos de Chile",
        "133": "Carabineros de Chile (Emergencias Policiales)",
        "134": "Policía de Investigaciones de Chile (PDI)",
        "137": "Armada de Chile (Rescate Marítimo)",
        "130": "CONAF (Incendios Forestales)",
        "135": "Fono Drogas Carabineros",
        "149": "Fono Familia Carabineros",
        "1455": "Fono Orientación Violencia contra la Mujer (SERNAMEG)",
        "147": "Fono Niños Carabineros",
        "1412": "Fono Ayuda SENDA (Drogas y Alcohol)",
    }

    @classmethod
    def clean_digits(cls, number_str: str) -> str:
        """Limpia caracteres no numéricos excepto el signo + inicial."""
        if not number_str:
            return ""
        number_str = str(number_str).strip()
        has_plus = number_str.startswith("+")
        digits = re.sub(r"\D", "", number_str)
        return f"+{digits}" if has_plus else digits

    @classmethod
    def analyze_number(cls, input_number: str) -> ChileanNumberInfo:
        """
        Analiza y clasifica cualquier número recibido en formato chileno o internacional.
        """
        cleaned = cls.clean_digits(input_number)
        if not cleaned:
            return ChileanNumberInfo(
                raw_number=input_number,
                is_valid=False,
                number_type=PhoneNumberType.UNKNOWN,
                digits_9=None,
                e164=None,
                formatted_national=None,
                region=None,
                carrier_hint=None,
                description="Número vacío o inválido"
            )

        # 1. Verificar si es número de emergencia / utilidad pública
        digits_only = cleaned.lstrip("+")
        if digits_only in cls.EMERGENCY_NUMBERS:
            desc = cls.EMERGENCY_NUMBERS[digits_only]
            return ChileanNumberInfo(
                raw_number=input_number,
                is_valid=True,
                number_type=PhoneNumberType.EMERGENCY,
                digits_9=digits_only,
                e164=f"+56{digits_only}",
                formatted_national=digits_only,
                region="Nacional (Chile)",
                carrier_hint="PSTN Emergencias",
                description=desc
            )

        # Verificar números municipales 14XX
        if len(digits_only) == 4 and digits_only.startswith("14"):
            return ChileanNumberInfo(
                raw_number=input_number,
                is_valid=True,
                number_type=PhoneNumberType.MUNICIPAL,
                digits_9=digits_only,
                e164=f"+56{digits_only}",
                formatted_national=digits_only,
                region="Municipal / Seguridad Comunal",
                carrier_hint="Seguridad Ciudadana",
                description=f"Fono Seguridad Comunal ({digits_only})"
            )

        # 2. Extracción de los 9 dígitos nacionales
        digits_9 = None

        # Si empieza con +56 o 56
        if cleaned.startswith("+56"):
            rest = cleaned[3:]
            if len(rest) == 9:
                digits_9 = rest
        elif cleaned.startswith("56") and len(cleaned) == 11:
            digits_9 = cleaned[2:]
        elif len(cleaned) == 9:
            digits_9 = cleaned
        elif len(cleaned) == 8:
            # Posible número antiguo fijo de 8 dígitos en Santiago o región
            # Si empieza con 2 (antiguo Santiago 2-XXXXXXX), agregar 2 inicial -> 22XXXXXXX
            if cleaned.startswith("2"):
                digits_9 = "2" + cleaned
            # Si empieza con 9 (móvil sin el 9 inicial pero 8 dígitos) -> 9 + cleaned
            else:
                digits_9 = "9" + cleaned

        if not digits_9 or len(digits_9) != 9 or not digits_9.isdigit():
            return ChileanNumberInfo(
                raw_number=input_number,
                is_valid=False,
                number_type=PhoneNumberType.UNKNOWN,
                digits_9=None,
                e164=None,
                formatted_national=None,
                region=None,
                carrier_hint=None,
                description=f"Longitud incorrecta para numeración chilena (Se esperan 9 dígitos)"
            )

        # 3. Clasificación entre Móvil y Red Fija
        first_digit = digits_9[0]
        first_two = digits_9[:2]

        if first_digit == "9":
            # Móvil Chileno (9 XXXX XXXX)
            e164 = f"+56{digits_9}"
            formatted = f"+56 9 {digits_9[1:5]} {digits_9[5:]}"
            
            # Estimación de carrier basada en rangos habituales (Entel, Movistar, Claro, WOM)
            carrier = "Móvil Nacional (Entel/Movistar/Claro/WOM/VTR)"
            
            return ChileanNumberInfo(
                raw_number=input_number,
                is_valid=True,
                number_type=PhoneNumberType.MOBILE,
                digits_9=digits_9,
                e164=e164,
                formatted_national=formatted,
                region="Nacional Móvil",
                carrier_hint=carrier,
                description="Telefonía Móvil de Chile"
            )

        elif first_two in cls.AREA_CODES_CHILE:
            # Red Fija Chilena
            region_name, _ = cls.AREA_CODES_CHILE[first_two]
            e164 = f"+56{digits_9}"
            formatted = f"+56 {first_two} {digits_9[2:5]} {digits_9[5:]}"
            
            return ChileanNumberInfo(
                raw_number=input_number,
                is_valid=True,
                number_type=PhoneNumberType.LANDLINE,
                digits_9=digits_9,
                e164=e164,
                formatted_national=formatted,
                region=region_name,
                carrier_hint="Red Fija / VoIP Local",
                description=f"Red Fija {region_name}"
            )
        else:
            # Número de 9 dígitos pero código de área no registrado formalmente
            e164 = f"+56{digits_9}"
            formatted = f"+56 {digits_9[:2]} {digits_9[2:5]} {digits_9[5:]}"
            return ChileanNumberInfo(
                raw_number=input_number,
                is_valid=True,
                number_type=PhoneNumberType.SPECIAL,
                digits_9=digits_9,
                e164=e164,
                formatted_national=formatted,
                region="Otro Servicio / VoIP Chile",
                carrier_hint="VoIP / Numeración Especial",
                description="Servicio Telefónico Especial Chile"
            )

    @classmethod
    def to_sip_uri(cls, input_number: str, trunk_endpoint: str) -> Optional[str]:
        """
        Convierte un número a formato de marcación SIP URI E.164 compatible con Asterisk PJSIP.
        Ejemplo: sip:+56912345678@zadarma_endpoint
        """
        info = cls.analyze_number(input_number)
        if not info.is_valid or not info.e164:
            return None
        
        # Para emergencias, enviar el número corto directamente
        if info.number_type == PhoneNumberType.EMERGENCY:
            return f"PJSIP/{info.digits_9}@{trunk_endpoint}"
            
        return f"PJSIP/{info.e164}@{trunk_endpoint}"
