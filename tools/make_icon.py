"""Génère assets/eliot.ico et assets/eliot.png à partir du logo dessiné."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QGuiApplication  # noqa: E402

from eliot.ui.logo import logo_pixmap  # noqa: E402

app = QGuiApplication(sys.argv)
out = Path(__file__).resolve().parent.parent / "assets"
out.mkdir(exist_ok=True)
logo_pixmap(256).save(str(out / "eliot.png"), "PNG")
if not logo_pixmap(256).save(str(out / "eliot.ico"), "ICO"):
    from PIL import Image
    Image.open(out / "eliot.png").save(out / "eliot.ico", sizes=[(16, 16), (32, 32), (48, 48), (256, 256)])
print("Icône générée dans", out)
