#!/bin/bash
# Triply AppImage Builder
# Run this script to create a new AppImage from current source
set -e
cd "$(dirname "$(readlink -f "$0")")"

VERSION=${1:-"beta"}
OUTPUT="Triply-${VERSION}-x86_64.AppImage"

echo "Building Triply ${VERSION} AppImage..."

# Clean
rm -rf AppDir_simple

# Create structure
mkdir -p AppDir_simple/usr/src
mkdir -p AppDir_simple/usr/share/applications
mkdir -p AppDir_simple/usr/share/icons/hicolor/256x256/apps

# Copy source and venv
cp -r src/ AppDir_simple/usr/src/
cp -r venv/ AppDir_simple/usr/venv/

# Icon
if [ -f "assets/triply.png" ]; then
    cp assets/triply.png AppDir_simple/triply.png
    cp assets/triply.png AppDir_simple/usr/share/icons/hicolor/256x256/apps/triply.png
else
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
fi

# Desktop file
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

# AppRun
cat > AppDir_simple/AppRun << 'APPRUN'
#!/bin/bash
HERE="$(dirname "$(readlink -f "${0}")")"
export PYTHONPATH="${HERE}/usr/src/src:${PYTHONPATH}"
export PYOPENGL_PLATFORM=glx
export LD_LIBRARY_PATH="${HERE}/usr/venv/lib:${LD_LIBRARY_PATH}"
exec "${HERE}/usr/venv/bin/python3" "${HERE}/usr/src/src/main.py" "$@"
APPRUN
chmod +x AppDir_simple/AppRun

# Build
ARCH=x86_64 ~/tools/appimagetool AppDir_simple "$OUTPUT" 2>&1 | tail -5

# Copy to releases
mkdir -p "$(dirname "$0")/../Releases/${VERSION}"
cp "$OUTPUT" "$(dirname "$0")/../Releases/${VERSION}/"

echo ""
echo "✓ Built: $OUTPUT ($(du -sh $OUTPUT | cut -f1))"
echo "✓ Copied to Releases/${VERSION}/"
