"""Logo ELIOT dessiné : un « e » au cœur d'un anneau ouvert façon symbole @."""
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QConicalGradient, QFont, QIcon, QPainter, QPen, QPixmap

from ..config import resource_path
from .theme import C


def logo_pixmap(size: int = 64) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor(C["panel"]))
    p.setPen(Qt.NoPen)
    p.drawEllipse(QRectF(0, 0, size, size))
    grad = QConicalGradient(QPointF(size / 2, size / 2), 90)
    grad.setColorAt(0.0, QColor(C["cyan"]))
    grad.setColorAt(0.5, QColor(C["teal"]))
    grad.setColorAt(1.0, QColor(C["cyan"]))
    pen = QPen(grad, size * 0.085)
    pen.setCapStyle(Qt.RoundCap)
    p.setPen(pen)
    m = size * 0.12
    p.drawArc(QRectF(m, m, size - 2 * m, size - 2 * m), -40 * 16, 300 * 16)
    font = QFont("Segoe UI", max(6, int(size * 0.36)))
    font.setBold(True)
    p.setFont(font)
    p.setPen(QColor(C["text"]))
    p.drawText(QRectF(0, -size * 0.04, size, size), Qt.AlignCenter, "e")
    p.end()
    return pm


def app_icon() -> QIcon:
    ico = resource_path("assets/eliot.ico")
    if ico.exists():
        return QIcon(str(ico))
    icon = QIcon()
    for s in (16, 32, 48, 64, 128, 256):
        icon.addPixmap(logo_pixmap(s))
    return icon
