#!/usr/bin/env bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
echo "================================================"
echo "  Triply — AM Tools and Lattices — Setup"
echo "================================================"
echo ""
if ! command -v python3 &>/dev/null; then echo "ERROR: python3 not found."; exit 1; fi
PYVER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PYMIN=$(python3 -c "import sys; print(sys.version_info.minor)")
echo "Found Python $PYVER"
if ! python3 -m venv --help &>/dev/null 2>&1; then
    echo "Installing python3.$PYMIN-venv..."
    sudo apt install -y python3.$PYMIN-venv python3.$PYMIN-dev
fi
if [ -d "venv" ]; then rm -rf venv; fi
echo "Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip --quiet
echo "Installing dependencies:"
pip install "PyQt6"          --quiet && echo "  ✓ PyQt6"
pip install "PyOpenGL"       --quiet && echo "  ✓ PyOpenGL"
pip install "numpy"          --quiet && echo "  ✓ numpy"
pip install "numpy-stl"      --quiet && echo "  ✓ numpy-stl"
pip install "scikit-image"   --quiet && echo "  ✓ scikit-image"
pip install "scipy"          --quiet && echo "  ✓ scipy"
pip install "pyinstaller"    --quiet && echo "  ✓ pyinstaller"
deactivate
echo ""
echo "================================================"
echo "  Setup complete!  Run ./run.sh to launch."
echo "================================================"
