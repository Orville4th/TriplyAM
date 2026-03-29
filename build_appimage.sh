#!/bin/bash

set -e

cd "$(dirname "$(readlink -f "$0")")"

VERSION=${1:-"beta"}

OUTPUT="Triply-${VERSION}-x86_64.appimage"

echo "Building Triply ${VERSION} AppImage..."

rm -rf AppDir_simple

mkdir -p AppDir_simple/usr/src
mkdir -p AppDir_simple/usr/share/applications
mkdir -p AppDir_simple/usr/share/icons/hicolor/256x256/apps

cp -r src/ AppDir_simple/usr/src/

# Use existing venv if available, otherwise create one
if [ -d "venv" ]; then
    echo "Using existing venv..."
    cp -r venv/ AppDir_simple/usr/venv/

    # CRITICAL FIX: venv/bin/python3 is a symlink to the host system Python.
    # That path doesn't exist on other machines. Resolve it to the real binary
    # and replace the symlink with a copy of the actual interpreter.
    VENV_PY="AppDir_simple/usr/venv/bin/python3"
    REAL_PY=$(readlink -f "$VENV_PY" 2>/dev/null || true)

    if [ -n "$REAL_PY" ] && [ -f "$REAL_PY" ] && [ "$REAL_PY" != "$(pwd)/$VENV_PY" ]; then
        echo "Resolving python3 symlink: $REAL_PY -> bundled copy"
        rm "$VENV_PY"
        cp "$REAL_PY" "$VENV_PY"
        chmod +x "$VENV_PY"
    fi

    # Also fix python3.x versioned symlinks (e.g. python3.11)
    for VERSIONED in AppDir_simple/usr/venv/bin/python3.*; do
        [ -L "$VERSIONED" ] || continue
        REAL=$(readlink -f "$VERSIONED" 2>/dev/null || true)
        if [ -n "$REAL" ] && [ -f "$REAL" ]; then
            echo "Resolving $(basename $VERSIONED) symlink"
            rm "$VERSIONED"
            cp "$REAL" "$VERSIONED"
            chmod +x "$VERSIONED"
        fi
    done

else
    echo "Creating venv and installing dependencies..."
    python3 -m venv AppDir_simple/usr/venv

    # Resolve symlinks immediately after creation
    VENV_PY="AppDir_simple/usr/venv/bin/python3"
    REAL_PY=$(readlink -f "$VENV_PY")
    rm "$VENV_PY"
    cp "$REAL_PY" "$VENV_PY"
    chmod +x "$VENV_PY"

    AppDir_simple/usr/venv/bin/pip install --quiet \
        PyQt6 PyOpenGL PyOpenGL_accelerate numpy numpy-stl \
        scikit-image scipy meshlib manifold3d cadquery \
        pyvista pymeshfix
fi

# Generate icon
python3 -c "
import struct,zlib
w,h=256,256
img=[]
for y in range(h):
    row=[]
    for x in range(w):
        r,g,b,a=18,18,20,255
        if 80<y<120 and 40<x<216: r,g,b=139,0,0
        if 110<y<220 and 108<x<148: r,g,b=139,0,0
        row.extend([r,g,b,a])
    img.append(bytes(row))
def chunk(t,d): c=zlib.crc32(t+d)&0xffffffff; return struct.pack('>I',len(d))+t+d+struct.pack('>I',c)
raw=b''.join(b'\x00'+r for r in img)
data=(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',w,h,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(raw))+chunk(b'IEND',b''))
open('/tmp/triply.png','wb').write(data)
"

cp /tmp/triply.png AppDir_simple/triply.png
cp /tmp/triply.png AppDir_simple/usr/share/icons/hicolor/256x256/apps/triply.png

cat > AppDir_simple/triply.desktop << 'DESKTOP'
[Desktop Entry]
Name=Triply
Comment=AM Tools and Lattices — by Orville Wright IV
Exec=Triply
Icon=triply
Type=Application
Categories=Graphics;
DESKTOP

cp AppDir_simple/triply.desktop AppDir_simple/usr/share/applications/triply.desktop

cat > AppDir_simple/AppRun << 'APPRUN'
#!/bin/bash

HERE="$(dirname "$(readlink -f "${0}")")"

export PYTHONPATH="${HERE}/usr/src/src:${PYTHONPATH}"
export LD_LIBRARY_PATH="${HERE}/usr/venv/lib:${LD_LIBRARY_PATH}"

# Wayland/X11 detection — GLX requires X11; on pure Wayland use EGL instead
if [ -n "$WAYLAND_DISPLAY" ] && [ -z "$DISPLAY" ]; then
    export PYOPENGL_PLATFORM=egl
    export QT_QPA_PLATFORM=wayland
else
    export PYOPENGL_PLATFORM=glx
    export QT_QPA_PLATFORM=xcb
fi

# Log file for crash diagnostics
LOG="$HOME/.triply-crash.log"

PYTHON="${HERE}/usr/venv/bin/python3"

if [ ! -f "$PYTHON" ]; then
    echo "ERROR: Bundled Python not found at $PYTHON" | tee "$LOG"
    echo "Please report this at https://github.com/Orville4th/TriplyAM/issues" | tee -a "$LOG"
    exit 1
fi

exec "$PYTHON" "${HERE}/usr/src/src/main.py" "$@" 2>>"$LOG" 1>>"$LOG" &
TRIPLY_PID=$!

# Give it 3 seconds to either show a window or die
sleep 3
if ! kill -0 $TRIPLY_PID 2>/dev/null; then
    echo ""
    echo "Triply failed to start. Error log: $LOG"
    echo "Last 20 lines:"
    tail -20 "$LOG"
fi
APPRUN

chmod +x AppDir_simple/AppRun

# Find appimagetool
if command -v appimagetool &>/dev/null; then
    APPIMAGETOOL="appimagetool"
elif [ -f "$HOME/tools/appimagetool" ]; then
    APPIMAGETOOL="$HOME/tools/appimagetool"
elif [ -f "$(dirname "$0")/appimagetool" ]; then
    APPIMAGETOOL="$(dirname "$0")/appimagetool"
else
    echo "Downloading appimagetool..."
    wget -q "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage" -O /tmp/appimagetool
    chmod +x /tmp/appimagetool
    APPIMAGETOOL="/tmp/appimagetool"
fi

ARCH=x86_64 $APPIMAGETOOL AppDir_simple "$OUTPUT" 2>&1 | tail -5

mkdir -p "$(dirname "$0")/../Releases/${VERSION}" 2>/dev/null || true
cp "$OUTPUT" "$(dirname "$0")/../Releases/${VERSION}/" 2>/dev/null || true

echo "✓ Built: $OUTPUT ($(du -sh $OUTPUT | cut -f1))"
echo "  Crash logs will appear at: ~/.triply-crash.log"
