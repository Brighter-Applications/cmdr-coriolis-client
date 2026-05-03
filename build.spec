# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for cmdr-coriolis-client.

Build with:
    pyinstaller build.spec

Or use the shortcut:
    pip install pyinstaller
    python -m PyInstaller build.spec
"""

import os, subprocess, sys

def _find_tcl_tk_data():
    """Locate Tcl/Tk data dirs, handling Nix split packages."""
    datas = []
    try:
        out = subprocess.check_output([
            sys.executable, '-c',
            'import tkinter; r=tkinter.Tk(); '
            'print(r.tk.eval("info library")); '
            'print(r.tk.eval("info patchlevel")); '
            'r.destroy()'
        ], text=True).strip().splitlines()
        tcl_dir = out[0]
        ver = '.'.join(out[1].split('.')[:2])
        if os.path.isdir(tcl_dir):
            datas.append((tcl_dir, '_tcl_data'))
        # Tk data may be in a different store path on Nix — find it via glob
        tk_dir = os.path.join(os.path.dirname(tcl_dir), f'tk{ver}')
        if not os.path.isdir(tk_dir):
            import glob
            candidates = glob.glob(f'/nix/store/*/lib/tk{ver}')
            if candidates:
                tk_dir = candidates[0]
        if os.path.isdir(tk_dir):
            datas.append((tk_dir, '_tk_data'))
    except Exception:
        pass
    return datas

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=_find_tcl_tk_data(),
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='CMDRCoriolisClient',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # No console window — the tkinter GUI is the interface
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
