#!/usr/bin/env python3
"""
V.I.E.R.N.E.S. - Herramienta CLI de Recuperación y Gestión de Contraseñas
Permite restablecer contraseñas de acceso al Dashboard exclusivamente desde la terminal local.
"""

import sys
import os
import argparse
import getpass

# Agregar directorio raíz al PYTHONPATH
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_DIR)

from viernes.auth.manager import auth_mgr, DEFAULT_ADMIN_EMAIL


def main():
    parser = argparse.ArgumentParser(description="V.I.E.R.N.E.S. - CLI Password Recovery Tool")
    parser.add_argument("--email", "-e", type=str, default=DEFAULT_ADMIN_EMAIL, help="Correo del usuario a restablecer")
    parser.add_argument("--password", "-p", type=str, default=None, help="Nueva contraseña (si se omite, se solicitará interactivamente)")
    args = parser.parse_args()

    email = args.email.strip().lower()
    new_password = args.password

    if not new_password:
        print("=" * 60)
        print(f"  V.I.E.R.N.E.S. - RECUPERACIÓN DE CONTRASEÑA CLI")
        print(f"  Usuario objetivo: {email}")
        print("=" * 60)
        new_password = getpass.getpass("Ingresa la nueva contraseña: ")
        confirm_password = getpass.getpass("Confirma la nueva contraseña: ")

        if new_password != confirm_password:
            print("[ERROR] Las contraseñas no coinciden. Operación cancelada.")
            sys.exit(1)

        if len(new_password) < 8:
            print("[ERROR] La contraseña debe tener al menos 8 caracteres por seguridad.")
            sys.exit(1)

    success = auth_mgr.reset_password(email, new_password)
    if success:
        print(f"\n[ÉXITO] La contraseña para '{email}' ha sido restablecida exitosamente.")
        print("Ya puedes iniciar sesión en el Stark HUD Dashboard.")
    else:
        print(f"\n[ERROR] No se pudo restablecer la contraseña para '{email}'.")
        sys.exit(1)


if __name__ == "__main__":
    main()
