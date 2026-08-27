#!/usr/bin/env python3
"""
V.I.E.R.N.E.S. - Tactical CLI Password Recovery & Auth Administration Tool
Diseñado para consolas locales, terminales SSH y sesiones serie OOB en Raspberry Pi 5.
"""

import sys
import os
import argparse
import getpass
import re
from typing import Optional

# Configurar ruta del proyecto
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_DIR)

from viernes.auth.manager import auth_mgr, DEFAULT_ADMIN_EMAIL

# Secuencias ANSI Seguras (Degradables si TERM=dumb o no hay TTY)
SUPPORTS_COLOR = sys.stdout.isatty() and os.environ.get("TERM") != "dumb"

CYAN = "\033[96m" if SUPPORTS_COLOR else ""
GREEN = "\033[92m" if SUPPORTS_COLOR else ""
YELLOW = "\033[93m" if SUPPORTS_COLOR else ""
RED = "\033[91m" if SUPPORTS_COLOR else ""
BOLD = "\033[1m" if SUPPORTS_COLOR else ""
RESET = "\033[0m" if SUPPORTS_COLOR else ""


def print_banner():
    print(f"\n{CYAN}{BOLD}" + "=" * 62)
    print("   ░█░█░▀█▀░█▀▀░█▀▄░█▀█░█▀▀░█▀▀   TACTICAL OOB ADMIN")
    print("   ░▀▄▀░░█░░█▀▀░█▀▄░█░█░█▀▀░▀▀█   STARK AI FRAMEWORK")
    print("   ░░▀░░▀▀▀░▀▀▀░▀░▀░▀░▀░▀▀▀░▀▀▀   Raspberry Pi 5 Core")
    print("=" * 62 + f"{RESET}\n")


def check_password_strength(password: str) -> tuple[bool, str]:
    if len(password) < 8:
        return False, "Debe contener al menos 8 caracteres."
    return True, "Fuerza adecuada."


def prompt_password_interactive() -> Optional[str]:
    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        try:
            pwd1 = getpass.getpass(f"{CYAN}[>] Ingrese nueva contraseña:{RESET} ")
            if not pwd1:
                print(f"{YELLOW}[!] La contraseña no puede estar vacía.{RESET}")
                continue

            valid, msg = check_password_strength(pwd1)
            if not valid:
                print(f"{YELLOW}[!] Seguridad insuficiente: {msg}{RESET}")
                continue

            pwd2 = getpass.getpass(f"{CYAN}[>] Confirme nueva contraseña:{RESET} ")
            if pwd1 != pwd2:
                print(f"{RED}[✗] Las contraseñas no coinciden. Intento {attempt}/{max_attempts}.{RESET}\n")
                continue

            return pwd1

        except (KeyboardInterrupt, EOFError):
            print(f"\n{YELLOW}[!] Operación cancelada por el usuario.{RESET}")
            return None

    print(f"{RED}[✗] Se excedió el número máximo de intentos.{RESET}")
    return None


def main():
    parser = argparse.ArgumentParser(
        description="V.I.E.R.N.E.S. - Herramienta de Recuperación de Credenciales Fuera de Banda (OOB)"
    )
    parser.add_argument(
        "--email", "-e",
        type=str,
        default=DEFAULT_ADMIN_EMAIL,
        help=f"Correo del usuario a restablecer (Por defecto: {DEFAULT_ADMIN_EMAIL})"
    )
    parser.add_argument(
        "--password", "-p",
        type=str,
        default=None,
        help="Nueva contraseña directamente (para automatización)"
    )
    parser.add_argument(
        "--stdin",
        action="store_true",
        help="Leer contraseña directamente desde STDIN"
    )
    parser.add_argument(
        "--no-banner",
        action="store_true",
        help="Omitir el banner visual táctico"
    )

    args = parser.parse_args()
    email = args.email.strip().lower()

    if not args.no_banner and sys.stdout.isatty():
        print_banner()

    print(f"{BOLD}[*] Usuario objetivo:{RESET} {CYAN}{email}{RESET}")

    new_password = args.password

    if not new_password:
        if args.stdin or not sys.stdin.isatty():
            new_password = sys.stdin.readline().rstrip("\r\n")
            if not new_password:
                print(f"{RED}[✗] Error: Se recibió una contraseña vacía por STDIN.{RESET}", file=sys.stderr)
                sys.exit(1)
        else:
            new_password = prompt_password_interactive()
            if not new_password:
                sys.exit(1)

    # Ejecutar reset en el AuthManager
    success = auth_mgr.reset_password(email, new_password)
    if success:
        print(f"\n{GREEN}{BOLD}[✓] Contraseña para '{email}' actualizada exitosamente.{RESET}")
        print(f"{CYAN}[i] Acceso al Stark HUD Dashboard habilitado.{RESET}\n")
    else:
        print(f"\n{RED}[✗] Error al actualizar la base de datos de usuarios.{RESET}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
