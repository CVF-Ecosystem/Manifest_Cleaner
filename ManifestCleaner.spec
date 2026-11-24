# Build on the target Windows computer using BUILD_EXE.cmd. PyInstaller 6
# keeps collected resources inside its support directory; the build launcher
# also copies the user-facing guide/example beside the executable. The GUI
# intentionally reads/writes settings.json beside sys.executable when frozen.
from pathlib import Path

root = Path(SPECPATH)
hiddenimports = [
    'manifest_cleaner.carriers.vosco.adapter',
    'manifest_cleaner.carriers.vimc.adapter',
    'manifest_cleaner.carriers.vinafco.adapter',
    'openpyxl', 'xlrd', 'xlsxwriter',
]
a = Analysis([str(root / 'app.py')], pathex=[str(root)], binaries=[],
             datas=[(str(root / 'START_HERE.html'), '.'), (str(root / 'settings.example.json'), '.')],
             hiddenimports=hiddenimports, hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='ManifestCleaner',
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False, console=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='ManifestCleaner')
