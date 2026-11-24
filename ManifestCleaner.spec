# Build on the target Windows computer using BUILD_EXE.cmd. PyInstaller 6
# keeps collected resources inside its support directory; the build launcher
# also copies the user-facing guide/example beside the executable. The GUI
# intentionally reads/writes settings.json beside sys.executable when frozen.
from pathlib import Path
from runpy import run_path

root = Path(SPECPATH)
profiles = run_path(str(root / 'manifest_cleaner' / 'carriers' / '__init__.py'))['CARRIER_PROFILES']
hiddenimports = [profile.adapter for profile in profiles.values()] + ['openpyxl', 'xlrd', 'xlsxwriter']
a = Analysis([str(root / 'app.py')], pathex=[str(root)], binaries=[],
             datas=[(str(root / 'START_HERE.html'), '.'), (str(root / 'settings.example.json'), '.')],
             hiddenimports=hiddenimports, hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='ManifestCleaner',
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False, console=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='ManifestCleaner')
