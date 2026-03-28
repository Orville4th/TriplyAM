# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_dynamic_libs

block_cipher = None

# Collect all data/binaries from heavy packages
meshlib_datas, meshlib_binaries, meshlib_hiddenimports = collect_all('meshlib')
manifold_datas, manifold_binaries, manifold_hiddenimports = collect_all('manifold3d')
cadquery_datas, cadquery_binaries, cadquery_hiddenimports = collect_all('cadquery')
skimage_datas, skimage_binaries, skimage_hiddenimports = collect_all('skimage')
pyvista_datas, pyvista_binaries, pyvista_hiddenimports = collect_all('pyvista')

a = Analysis(
    ['src/main.py'],
    pathex=['src'],
    binaries=meshlib_binaries + manifold_binaries + cadquery_binaries + skimage_binaries + pyvista_binaries,
    datas=[
        ('src', 'src'),
    ] + meshlib_datas + manifold_datas + cadquery_datas + skimage_datas + pyvista_datas,
    hiddenimports=[
        'meshlib', 'meshlib.mrmeshpy',
        'manifold3d',
        'cadquery',
        'skimage', 'skimage.measure',
        'scipy', 'scipy.ndimage',
        'pyvista',
        'OpenGL', 'OpenGL.GL', 'OpenGL.GLU',
        'OpenGL.platform', 'OpenGL.platform.glx', 'OpenGL.platform.egl',
        'OpenGL.platform.ctypesloader', 'OpenGL.arrays',
        'OpenGL.arrays.numpymodule', 'OpenGL.arrays.ctypesarrays',
        'OpenGL.arrays.formathandler', 'OpenGL.arrays.numbers',
        'OpenGL.extensions', 'OpenGL.raw', 'OpenGL.raw.GL',
        'OpenGL.raw.GL.ARB', 'OpenGL.raw.GL.VERSION',
        'PyQt6', 'PyQt6.QtWidgets', 'PyQt6.QtCore', 'PyQt6.QtGui',
        'PyQt6.QtOpenGLWidgets', 'PyQt6.QtOpenGL',
        'numpy', 'numpy.core',
        'stl', 'stl.mesh',
        'mesh_repair', 'lattice', 'viewport', 'packer',
        'triply_io', 'triply_io.importer', 'triply_io.exporter',
    ] + meshlib_hiddenimports + manifold_hiddenimports + cadquery_hiddenimports + skimage_hiddenimports + pyvista_hiddenimports,
    hookspath=['hooks'],
    hooksconfig={},
    runtime_hooks=['hooks/rthook_opengl.py'],
    excludes=['tkinter', 'matplotlib.tests', 'numpy.random._examples'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Triply',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Triply',
)
