#!/usr/bin/env python3
"""
Script de Restauración de Luz WiZ a Paleta Cálida (2700K).
Restaura el estado original y apacible de iluminación en la Raspberry Pi 5.
"""

import sys
import os
import asyncio

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from viernes.iot.smart_lights import SmartDeviceController


async def main():
    light_ip = sys.argv[1] if len(sys.argv) > 1 else "192.168.100.15"
    print(f"🔆 Restaurando luz WiZ en {light_ip} a paleta 'Cálida' (2700K, brillo 80%)...")
    res = await SmartDeviceController.control_wiz_light(
        light_ip,
        state=True,
        dimming=80,
        temp=2700,
        palette="cálida"
    )
    print(f"Resultado: {res.get('message', 'Comando enviado.')}")
    print("✓ Luz WiZ restaurada a Blanco Cálido.")


if __name__ == "__main__":
    asyncio.run(main())
