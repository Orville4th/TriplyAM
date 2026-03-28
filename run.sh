#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
if [ ! -d "venv" ]; then echo "Running setup first..."; ./setup.sh; fi
source venv/bin/activate
python3 src/main.py
deactivate
