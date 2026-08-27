#!/usr/bin/env bash
# Autodeploy wrapper
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec bash "$DIR/easy_install.sh" "$@"
