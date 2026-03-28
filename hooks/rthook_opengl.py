# Fix OpenGL platform detection in frozen app
import sys
import os

# Force GLX platform on Linux
if sys.platform.startswith('linux'):
    os.environ.setdefault('PYOPENGL_PLATFORM', 'glx')
    
# Suppress EGL import error
import importlib
_orig_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__

def _safe_import(name, *args, **kwargs):
    try:
        return _orig_import(name, *args, **kwargs)
    except (ImportError, TypeError) as e:
        if 'egl' in str(name).lower() or 'EGL' in str(e):
            pass
        else:
            raise
            
import builtins
builtins.__import__ = _safe_import
