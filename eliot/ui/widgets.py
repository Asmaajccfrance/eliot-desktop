import math

from PySide6.QtCore import QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap, QRadialGradient
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget

from ..config import resource_path
from .theme import C

class CommandBackground(QWidget):
    """Fond holographique, recadré pour couvrir toute la fenêtre."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pix = QPixmap(str(resource_path("assets/fond.jpg")))

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        if self._pix.isNull():
            painter.fillRect(self.rect(), QColor(C["bg"]))
            painter.end()
            return
        scaled = self._pix.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        x = (self.width() - scaled.width()) // 2
        y = (self.height() - scaled.height()) // 2
        painter.drawPixmap(x, y, scaled)
        painter.fillRect(self.rect(), QColor(2, 10, 22, 55))
        painter.end()


class FeatureCard(QFrame):
    def __init__(self, kicker: str, title: str, text: str, button: str, parent=None):
        super().__init__(parent)
        self.setObjectName("featureCard")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setMinimumHeight(148)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(6)
        lay.addWidget(QLabel(kicker, objectName="kicker"))
        lay.addWidget(QLabel(title, objectName="cardTitle"))
        body = QLabel(text, objectName="subtitle")
        body.setWordWrap(True)
        lay.addWidget(body)
        lay.addStretch(1)
        self.button = QPushButton(button, objectName="cardButton")
        lay.addWidget(self.button, 0, Qt.AlignLeft)


STATE_COLORS = {"idle": C["cyan"], "listening": C["danger"], "thinking": C["warn"], "speaking": C["teal"]}
STATE_LABELS = {"idle": "Clique ou parle", "listening": "Je t'écoute…", "thinking": "Je réfléchis…",
                "speaking": "Je parle…"}


class MicOrb(QWidget):
    clicked = Signal()

    def __init__(self, size=220, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.setCursor(Qt.PointingHandCursor)
        self.state = "idle"
        self.phase = 0.0
        self.setAccessibleName("orbe-micro")
        self.timer = QTimer(self, interval=33, timeout=self._tick)
        self.timer.start()

    def set_state(self, state: str) -> None:
        self.state = state
        self.setToolTip(STATE_LABELS.get(state, ""))
        self.update()

    def _tick(self):
        speed = {"idle": 0.03, "listening": 0.16, "thinking": 0.09, "speaking": 0.12}[self.state]
        self.phase = (self.phase + speed) % (2 * math.pi * 100)
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        cx = cy = w / 2
        color = QColor(STATE_COLORS[self.state])
        pulse = (math.sin(self.phase) + 1) / 2
        glow = QRadialGradient(cx, cy, w / 2)
        c1 = QColor(color)
        c1.setAlpha(int(70 + 60 * pulse))
        c2 = QColor(color)
        c2.setAlpha(0)
        glow.setColorAt(0.45, c1)
        glow.setColorAt(1.0, c2)
        p.setPen(Qt.NoPen)
        p.setBrush(glow)
        p.drawEllipse(QRectF(0, 0, w, w))
        for i in range(3):
            r = w * (0.30 + 0.06 * i + 0.02 * math.sin(self.phase + i))
            ring = QColor(color)
            ring.setAlpha(150 - 40 * i)
            p.setPen(QPen(ring, 1.5))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(QRectF(cx - r, cy - r, 2 * r, 2 * r))
        core = w * 0.26
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(C["panel"]))
        p.drawEllipse(QRectF(cx - core, cy - core, 2 * core, 2 * core))
        p.setPen(QPen(color, w * 0.022, Qt.SolidLine, Qt.RoundCap))
        mw, mh = w * 0.08, w * 0.15
        p.drawRoundedRect(QRectF(cx - mw / 2, cy - mh * 0.75, mw, mh), mw / 2, mw / 2)
        p.drawArc(QRectF(cx - mw * 1.05, cy - mh * 0.45, mw * 2.1, mh * 0.95), 200 * 16, 140 * 16)
        p.drawLine(int(cx), int(cy + mh * 0.5), int(cx), int(cy + mh * 0.75))
        p.end()


class MessageBubble(QFrame):
    def __init__(self, role: str, text: str = "", parent=None):
        super().__init__(parent)
        self.role = role
        self.setObjectName("bubbleUser" if role == "user" else "bubbleAssistant")
        self.setAttribute(Qt.WA_StyledBackground, True)
        if role == "user":
            self.setStyleSheet(f"#bubbleUser {{ background: {C['blue']}; border: 1px solid #2B4DB0; border-radius: 14px; }}")
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Minimum)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        self.label = QLabel()
        self.label.setWordWrap(True)
        self.label.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse)
        self.label.setOpenExternalLinks(True)
        self.label.setTextFormat(Qt.PlainText if role == "user" else Qt.MarkdownText)
        self.label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        lay.addWidget(self.label)
        self.set_text(text)

    def set_text(self, text: str) -> None:
        self.label.setText(text)
        metrics = self.label.fontMetrics()
        widest = max((metrics.horizontalAdvance(line) for line in (text or " ").splitlines() or [" "]), default=0)
        self.label.setMinimumWidth(min(widest + 8, 640))

    def set_thinking(self) -> None:
        self.label.setText("…")

    def set_error(self, text: str) -> None:
        self.setObjectName("bubbleError")
        self.style().unpolish(self)
        self.style().polish(self)
        self.label.setTextFormat(Qt.PlainText)
        self.set_text(text)


class ChatView(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.viewport().setStyleSheet("background: transparent;")
        self.body = QWidget()
        self.body.setStyleSheet("background: transparent;")
        self.lay = QVBoxLayout(self.body)
        self.lay.setContentsMargins(4, 4, 12, 4)
        self.lay.setSpacing(14)
        self.lay.addStretch(1)
        self.setWidget(self.body)
        self.verticalScrollBar().rangeChanged.connect(lambda _a, b: self.verticalScrollBar().setValue(b))

    def add_message(self, role: str, text: str) -> MessageBubble:
        bubble = MessageBubble(role, text)
        row = QHBoxLayout()
        bubble.setMaximumWidth(760)
        if role == "user":
            row.addStretch(1)
            row.addWidget(bubble)
        else:
            row.addWidget(bubble)
            row.addStretch(1)
        self.lay.insertLayout(self.lay.count() - 1, row)
        return bubble

    def clear(self) -> None:
        while self.lay.count() > 1:
            item = self.lay.takeAt(0)
            layout = item.layout()
            if layout is not None:
                while layout.count():
                    w = layout.takeAt(0).widget()
                    if w is not None:
                        w.deleteLater()
