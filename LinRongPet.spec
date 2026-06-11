from pathlib import Path

ROOT = Path(SPECPATH)
ASSETS = ROOT / "src" / "linrong_pet" / "assets"

a = Analysis(
    [str(ROOT / "run_linrong_pet.py")],
    pathex=[str(ROOT / "src")],
    binaries=[],
    datas=[(str(ASSETS), "assets")],
    hiddenimports=["PySide6.QtNetwork"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "PySide6.Qt3DAnimation",
        "PySide6.Qt3DCore",
        "PySide6.Qt3DExtras",
        "PySide6.Qt3DInput",
        "PySide6.Qt3DLogic",
        "PySide6.Qt3DRender",
        "PySide6.QtCharts",
        "PySide6.QtDataVisualization",
        "PySide6.QtGraphs",
        "PySide6.QtHttpServer",
        "PySide6.QtLocation",
        "PySide6.QtMultimedia",
        "PySide6.QtMultimediaWidgets",
        "PySide6.QtPdf",
        "PySide6.QtPdfWidgets",
        "PySide6.QtPositioning",
        "PySide6.QtQml",
        "PySide6.QtQuick",
        "PySide6.QtQuick3D",
        "PySide6.QtQuickControls2",
        "PySide6.QtQuickWidgets",
        "PySide6.QtRemoteObjects",
        "PySide6.QtScxml",
        "PySide6.QtSensors",
        "PySide6.QtSerialBus",
        "PySide6.QtSerialPort",
        "PySide6.QtSpatialAudio",
        "PySide6.QtSql",
        "PySide6.QtSvgWidgets",
        "PySide6.QtTest",
        "PySide6.QtTextToSpeech",
        "PySide6.QtUiTools",
        "PySide6.QtWebChannel",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtWebSockets",
        "PySide6.QtXml",
    ],
    noarchive=False,
    optimize=1,
)


def keep_runtime_entry(entry):
    destination = entry[0].replace("\\", "/").lower()
    unused = (
        "pyside6/qt6pdf.dll",
        "pyside6/qt6qml",
        "pyside6/qt6quick.dll",
        "pyside6/qt6virtualkeyboard.dll",
        "pyside6/plugins/imageformats/qpdf.dll",
        "pyside6/plugins/platforminputcontexts/",
        "pyside6/plugins/platforms/qdirect2d.dll",
        "pyside6/plugins/platforms/qminimal.dll",
        "pyside6/plugins/platforms/qoffscreen.dll",
        "pyside6/translations/",
    )
    return not destination.startswith(unused)


a.binaries = [entry for entry in a.binaries if keep_runtime_entry(entry)]
a.datas = [entry for entry in a.datas if keep_runtime_entry(entry)]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="LinRongPet",
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
    icon=str(ASSETS / "linrong.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="LinRongPet",
)
