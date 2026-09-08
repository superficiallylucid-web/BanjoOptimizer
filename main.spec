# -*- mode: python ; coding: utf-8 -*-
#
# BO-158 -- PyInstaller spec for the Banjo Optimizer GUI.
#
# Build with: pyinstaller main.spec
# Result: dist/BanjoOptimizer/BanjoOptimizer.exe (Windows) plus
# everything else it needs, all in that same dist/BanjoOptimizer/
# folder.
#
# Entry point is gui.py, not main.py -- this builds the GUI
# application (double-click, window opens), not a repackaged CLI.
# main.py itself is still imported (gui.py does `import main` and
# calls main.run_optimizer() directly, per the BO-153 refactor),
# so its own CLI __main__ block is simply never reached in this
# build -- confirmed not to interfere.
#
# One-folder mode (the PyInstaller default: a folder rather than
# a single merged .exe), used deliberately, not incidentally.
# main.py's own existing sys.frozen handling
# (PROJECT_FOLDER = Path(sys.executable).parent, unmodified by
# this spec) expects scores/, output/, and templates/ to live in
# the real, on-disk folder containing the .exe itself. One-file
# mode would instead extract bundled data to a temporary
# sys._MEIPASS folder at every launch -- a different location
# main.py was never written to look in, and one that's wiped
# between runs, which is actively wrong for output/ (results
# would vanish) even before considering the mismatch itself.
# One-folder mode avoids all of this: PyInstaller's own COLLECT
# step places `datas` entries directly alongside the .exe,
# exactly where main.py already looks, with no code changes
# needed anywhere.
#
# templates/ is the one genuinely required data file -- confirmed
# directly: generate_tab_from_template() reads
# templates/TAB_linked_Treble_Example.mscz unconditionally on
# every run, and unlike scores/ and output/ (which main.py/
# output.py already create automatically if missing), this is a
# real, pre-existing asset with no self-creation logic -- it must
# already be present. scores/ and output/ are deliberately NOT
# bundled here: both already self-create on first use (confirmed
# directly against main.py and output.py's own
# create_run_folder()), and shipping no scores/ contents is
# correct for a distributable app -- a user's own scores are
# picked via the real file picker (BO-155, any .mscz anywhere on
# disk), not expected to live inside the app's own install folder.

a = Analysis(
    ['gui.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('templates', 'templates'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

# BO-158 -- contents_directory='.' is the actual, correct fix
# (found in PyInstaller's own source, PyInstaller/building/api.py:
# EXE's own contents_directory kwarg, default "_internal").
# Confirmed by testing directly: PyInstaller 6.x's default onedir
# layout places everything except the .exe itself -- including
# anything added via Analysis's own datas=[...] above -- inside a
# separate _internal/ subdirectory one level deeper than
# Path(sys.executable).parent. main.py's existing, unmodified
# sys.frozen handling looks for templates/, scores/, and output/
# directly beside the .exe, not inside _internal/, so left at its
# default this build would silently fail to find
# templates/TAB_linked_Treble_Example.mscz at runtime. Setting
# this to '.' disables the _internal/ layout entirely, restoring
# the flat structure (everything directly alongside the .exe)
# that main.py was actually written for -- confirmed directly:
# a first attempt at fixing this with Tree() (placed alongside
# COLLECT's own args) did NOT move templates/ out of _internal/;
# contents_directory is the real mechanism.
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='BanjoOptimizer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    contents_directory='.',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='BanjoOptimizer',
)
