# One-file build for end users: a single ManifestCleaner.exe that unpacks itself into
# %TEMP% on every launch. Build it with BUILD_ONEFILE.cmd; ManifestCleaner.spec stays the
# folder build for the developer machine and the people who receive the zip.
# sys.executable is the real .exe path in a one-file build (sys._MEIPASS is the temp
# unpack folder), so the GUI keeps settings.json and recent_files.json beside the .exe.
# Keep the Analysis block identical to ManifestCleaner.spec; a test compares them.
# Only this build shows a start-up image; the folder build opens in about half a second.
from pathlib import Path
from runpy import run_path

root = Path(SPECPATH)
profiles = run_path(str(root / 'manifest_cleaner' / 'carriers' / '__init__.py'))['CARRIER_PROFILES']
hiddenimports = [profile.adapter for profile in profiles.values()] + ['openpyxl', 'xlrd', 'xlsxwriter']
a = Analysis([str(root / 'app.py')], pathex=[str(root)], binaries=[],
             datas=[(str(root / 'START_HERE.html'), '.'), (str(root / 'settings.example.json'), '.')],
             hiddenimports=hiddenimports, hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[])
pyz = PYZ(a.pure)
# The unpack runs for several seconds before any Python starts, so the bootloader shows this
# image straight away. It carries its own text (assets/splash.png, made by scripts/make_splash.py)
# and is closed by gui._close_splash() when the window is ready.
splash = Splash(str(root / 'assets' / 'splash.png'), binaries=a.binaries, datas=a.datas,
                text_pos=None, always_on_top=True)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, splash, splash.binaries, [], name='ManifestCleaner',
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False, console=False)
