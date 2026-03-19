# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for Recipe Manager
# Build with:  pyinstaller recipe_manager.spec

from PyInstaller.utils.hooks import collect_data_files, collect_submodules
import os

block_cipher = None

# ── Data files to bundle ──────────────────────────────────────────────────────
datas = [
    # The entire static folder (HTML, CSS, JS, images)
    ('static', 'static'),
]

# recipe_scrapers ships JSON/HTML data files for each supported site
datas += collect_data_files('recipe_scrapers')
# extruct (used by recipe_scrapers) also has data files
datas += collect_data_files('extruct', include_py_files=False)

# ── Hidden imports ────────────────────────────────────────────────────────────
hiddenimports = (
    collect_submodules('recipe_scrapers') +
    collect_submodules('flask') +
    collect_submodules('werkzeug') +
    collect_submodules('jinja2') +
    collect_submodules('webview') +
    [
        'pkg_resources.py2_warn',
        'sqlite3',
        'json',
        'encodings.utf_8',
        'encodings.ascii',
    ]
)

# ── Analysis ──────────────────────────────────────────────────────────────────
a = Analysis(
    ['launcher.py'],
    pathex=[os.path.abspath('.')],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'test', 'unittest'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='RecipeManager',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # No black console window – pure GUI app
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon='icon.ico',      # Uncomment and add an icon.ico to use a custom icon
)
