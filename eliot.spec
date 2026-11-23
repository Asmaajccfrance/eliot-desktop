# -*- mode: python ; coding: utf-8 -*-
# Construction : pyinstaller eliot.spec  (lancé automatiquement par build_exe.bat)
from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

datas = [("assets", "assets")]
binaries = []
hiddenimports = ["win32com.client", "pythoncom", "comtypes.stream", "pywinauto.keyboard", "pywinauto.mouse",
                 "keyring.backends.Windows", "PySide6.QtMultimedia", "sounddevice", "anthropic", "imaplib", "smtplib"]

for pkg in ("emergentintegrations", "litellm", "tiktoken", "tiktoken_ext", "playwright", "vosk"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

try:
    d, b, h = collect_all("_sounddevice_data")
    datas += d
    binaries += b
except Exception:
    pass
datas += collect_data_files("certifi")
hiddenimports += collect_submodules("pywinauto")

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "matplotlib", "pandas", "IPython", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ELIOT",
    icon="assets/eliot.ico",
    console=False,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="ELIOT", upx=False)
