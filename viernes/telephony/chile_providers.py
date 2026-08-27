"""
Módulo de Proveedores SIP Trunk Económicos en Chile para V.I.E.R.N.E.S.
Configuraciones predefinidas y generadores de configuración Asterisk (PJSIP / chan_sip).
"""

from typing import Dict, Any


CHILEAN_SIP_PRESETS: Dict[str, Dict[str, Any]] = {
    "zadarma_chile": {
        "name": "Zadarma Chile (Recomendado Persona Natural)",
        "description": "DID de Chile económico (+56 2 / +56 9) con cobro por segundo y sin contratos forzosos.",
        "sip_server": "sip.zadarma.com",
        "sip_port": 5060,
        "codec": ["alaw", "ulaw", "g729", "opus"],
        "caller_id_format": "+569XXXXXXXX",
        "nat": "yes",
        "dtmf_mode": "rfc2833",
        "register_string_template": "{username}:{password}@sip.zadarma.com/{username}",
        "pjsip_endpoint_template": """
; --- ZADARMA CHILE TRUNK ---
[transport-udp]
type=transport
protocol=udp
bind=0.0.0.0

[zadarma_reg]
type=registration
outbound_auth=zadarma_auth
server_uri=sip:sip.zadarma.com
client_uri=sip:{username}@sip.zadarma.com
retry_interval=60

[zadarma_auth]
type=auth
auth_type=userpass
username={username}
password={password}

[zadarma_aor]
type=aor
contact=sip:sip.zadarma.com

[zadarma_endpoint]
type=endpoint
context=from-trunk-viernes
disallow=all
allow=alaw,ulaw,opus
outbound_auth=zadarma_auth
aors=zadarma_aor
from_user={username}
direct_media=no

[zadarma_identify]
type=identify
endpoint=zadarma_endpoint
match=sip.zadarma.com
"""
    },
    "redvoiss": {
        "name": "Redvoiss Chile",
        "description": "Operador SIP chileno de alta fidelidad para telefonía local y móvil.",
        "sip_server": "sip.redvoiss.net",
        "sip_port": 5060,
        "codec": ["alaw", "g729"],
        "caller_id_format": "569XXXXXXXX",
        "nat": "yes",
        "dtmf_mode": "rfc2833",
    },
    "twilio_cl": {
        "name": "Twilio Elastic SIP Trunk (Chile)",
        "description": "Troncal SIP global de Twilio con terminación y números chilenos locales.",
        "sip_server": "{domain}.pstn.twilio.com",
        "sip_port": 5060,
        "codec": ["ulaw", "alaw", "opus"],
        "caller_id_format": "+569XXXXXXXX",
        "nat": "yes",
        "dtmf_mode": "rfc2833",
    },
    "net2phone_chile": {
        "name": "Net2Phone Chile",
        "description": "Proveedor corporativo de SIP Trunk en Chile.",
        "sip_server": "sip.net2phone.cl",
        "sip_port": 5060,
        "codec": ["alaw", "ulaw"],
        "caller_id_format": "56XXXXXXXX",
        "nat": "yes",
        "dtmf_mode": "rfc2833",
    }
}


def generate_asterisk_dialplan(did_number: str = "56912345678") -> str:
    """Genera el dialplan de Asterisk extensions.conf para conectar llamadas con V.I.E.R.N.E.S."""
    return f"""
[general]
static=yes
writeprotect=no

[from-trunk-viernes]
; Cuando entra una llamada al DID chileno
exten => {did_number},1,NoOp(Llamada entrante de ${{CALLERID(num)}} a V.I.E.R.N.E.S)
 same => n,Answer()
 same => n,Wait(1)
 ; Notificar al Asistente V.I.E.R.N.E.S vía FastAGI o ARI (puerto 8088)
 same => n,Stasis(viernes_call_app)
 same => n,Hangup()

; Extensión interna de prueba
exten => 100,1,NoOp(Llamada interna a VIERNES)
 same => n,Answer()
 same => n,Stasis(viernes_call_app)
 same => n,Hangup()

[outbound-viernes]
; Para que VIERNES pueda llamar a tu celular chileno en emergencias o recordatorios
exten => _+569XXXXXXXX,1,NoOp(VIERNES marcando a celular chileno: ${{EXTEN}})
 same => n,Dial(PJSIP/${{EXTEN}}@zadarma_endpoint,60)
 same => n,Hangup()

exten => _569XXXXXXXX,1,NoOp(VIERNES marcando a celular chileno: ${{EXTEN}})
 same => n,Dial(PJSIP/${{EXTEN}}@zadarma_endpoint,60)
 same => n,Hangup()
"""
