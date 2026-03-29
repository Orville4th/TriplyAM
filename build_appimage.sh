#!/bin/bash

set -e

cd "$(dirname "$(readlink -f "$0")")"

VERSION=${1:-"beta"}
OUTPUT="Triply-${VERSION}-x86_64.appimage"

echo "Building Triply ${VERSION} AppImage..."

rm -rf AppDir_simple

mkdir -p AppDir_simple/usr/src
mkdir -p AppDir_simple/usr/lib
mkdir -p AppDir_simple/usr/share/applications
mkdir -p AppDir_simple/usr/share/icons/hicolor/256x256/apps

cp -r src/ AppDir_simple/usr/src/

# ── Build or copy venv ────────────────────────────────────────────────────────
if [ -d "venv" ]; then
    echo "Using existing venv..."
    cp -r venv/ AppDir_simple/usr/venv/
else
    echo "Creating venv and installing dependencies..."
    python3 -m venv AppDir_simple/usr/venv
    AppDir_simple/usr/venv/bin/pip install --quiet \
        PyQt6 PyOpenGL PyOpenGL_accelerate numpy numpy-stl \
        scikit-image scipy meshlib manifold3d cadquery \
        pyvista pymeshfix
fi

# ── Resolve the python3 symlink to a real binary ─────────────────────────────
# venv/bin/python3 is a symlink to the system Python. On another machine that
# path won't exist. Replace every symlink with a copy of the real binary.
for PYLINK in AppDir_simple/usr/venv/bin/python3 AppDir_simple/usr/venv/bin/python3.*; do
    [ -e "$PYLINK" ] || continue
    REAL=$(readlink -f "$PYLINK" 2>/dev/null || true)
    if [ -n "$REAL" ] && [ -f "$REAL" ] && [ "$REAL" != "$(readlink -f "$PYLINK")" ]; then
        echo "Resolving $(basename $PYLINK): $REAL"
        rm "$PYLINK"
        cp "$REAL" "$PYLINK"
        chmod +x "$PYLINK"
    elif [ -L "$PYLINK" ]; then
        REAL=$(readlink -f "$PYLINK")
        if [ -f "$REAL" ]; then
            echo "Resolving symlink $(basename $PYLINK): $REAL"
            rm "$PYLINK"
            cp "$REAL" "$PYLINK"
            chmod +x "$PYLINK"
        fi
    fi
done

# ── Bundle Python stdlib ──────────────────────────────────────────────────────
# The Python binary has sys.prefix baked in pointing to the build machine.
# We override this with PYTHONHOME in AppRun, but Python still needs to find
# its stdlib. Copy it into the AppImage under usr/pythonlib/.
PYTHON_BIN="AppDir_simple/usr/venv/bin/python3"
PYTHON_VERSION=$("$PYTHON_BIN" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "3.11")
STDLIB_SRC=$("$PYTHON_BIN" -c "import sysconfig; print(sysconfig.get_path('stdlib'))" 2>/dev/null || true)

if [ -z "$STDLIB_SRC" ]; then
    # Fallback: try common locations
    for D in \
        "/opt/hostedtoolcache/Python/${PYTHON_VERSION}."*/x64/lib/python${PYTHON_VERSION} \
        "/usr/lib/python${PYTHON_VERSION}" \
        "/usr/local/lib/python${PYTHON_VERSION}"; do
        if [ -d "$D" ]; then STDLIB_SRC="$D"; break; fi
    done
fi

if [ -n "$STDLIB_SRC" ] && [ -d "$STDLIB_SRC" ]; then
    echo "Bundling Python stdlib from: $STDLIB_SRC"
    mkdir -p "AppDir_simple/usr/pythonlib/python${PYTHON_VERSION}"
    cp -r "$STDLIB_SRC/." "AppDir_simple/usr/pythonlib/python${PYTHON_VERSION}/"
    # Also copy lib-dynload if it exists alongside stdlib
    DYNLOAD_SRC="$(dirname "$STDLIB_SRC")/python${PYTHON_VERSION}/lib-dynload"
    if [ ! -d "$DYNLOAD_SRC" ]; then
        DYNLOAD_SRC="${STDLIB_SRC}/lib-dynload"
    fi
    if [ -d "$DYNLOAD_SRC" ]; then
        echo "Bundling lib-dynload from: $DYNLOAD_SRC"
        mkdir -p "AppDir_simple/usr/pythonlib/python${PYTHON_VERSION}/lib-dynload"
        cp -r "$DYNLOAD_SRC/." "AppDir_simple/usr/pythonlib/python${PYTHON_VERSION}/lib-dynload/"
    fi
else
    echo "WARNING: Could not find Python stdlib to bundle. App may not work on other machines."
fi

# ── Bundle libpython and other Python shared libs ────────────────────────────
echo "Bundling Python shared libraries..."
for LIB in $(ldd "$PYTHON_BIN" 2>/dev/null | grep -oP '(?<=> )/[^ ]+' | grep -v 'ld-linux'); do
    LIBNAME=$(basename "$LIB")
    if echo "$LIBNAME" | grep -qE '^(libpython|libssl|libcrypto|libffi|libbz2|liblzma|libsqlite|libreadline|libncurses|libtinfo|libz\.so)'; then
        if [ -f "$LIB" ] && [ ! -f "AppDir_simple/usr/lib/$LIBNAME" ]; then
            echo "  Bundling: $LIBNAME"
            cp "$LIB" "AppDir_simple/usr/lib/$LIBNAME"
        fi
    fi
done

# ── Generate icon ─────────────────────────────────────────────────────────────
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

# ── Write AppRun ──────────────────────────────────────────────────────────────
cat > AppDir_simple/AppRun << 'APPRUN'
#!/bin/bash

HERE="$(dirname "$(readlink -f "${0}")")"

# Detect Python version from bundled stdlib
PYVER=$(ls "${HERE}/usr/pythonlib/" 2>/dev/null | head -1)

# PYTHONHOME tells Python where to find its stdlib and site-packages.
# We point it at our bundled locations so it never looks at the host system.
if [ -n "$PYVER" ]; then
    export PYTHONHOME="${HERE}/usr/pythonlib"
    export PYTHONPATH="${HERE}/usr/pythonlib/${PYVER}:${HERE}/usr/venv/lib/${PYVER}/site-packages:${HERE}/usr/src/src:${PYTHONPATH}"
else
    export PYTHONPATH="${HERE}/usr/src/src:${PYTHONPATH}"
fi

# Bundled libs first
export LD_LIBRARY_PATH="${HERE}/usr/lib:${HERE}/usr/venv/lib:${LD_LIBRARY_PATH}"

# Wayland/X11 detection
if [ -n "$WAYLAND_DISPLAY" ] && [ -z "$DISPLAY" ]; then
    export PYOPENGL_PLATFORM=egl
    export QT_QPA_PLATFORM=wayland
else
    export PYOPENGL_PLATFORM=glx
    export QT_QPA_PLATFORM=xcb
fi

LOG="$HOME/.triply-crash.log"
: > "$LOG"

PYTHON="${HERE}/usr/venv/bin/python3"

if [ ! -f "$PYTHON" ]; then
    echo "ERROR: Bundled Python not found at $PYTHON" | tee "$LOG"
    exit 1
fi

exec "$PYTHON" "${HERE}/usr/src/src/main.py" "$@" 2>>"$LOG" 1>>"$LOG" &
TRIPLY_PID=$!

sleep 5
if ! kill -0 $TRIPLY_PID 2>/dev/null; then
    echo "Triply failed to start. Error log: $LOG"
    echo "Last 20 lines:"
    tail -20 "$LOG"
fi
APPRUN

chmod +x AppDir_simple/AppRun

# ── Package with appimagetool ─────────────────────────────────────────────────
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
