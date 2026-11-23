from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPlainTextEdit,
                               QPushButton, QVBoxLayout)

from ..agent_workflows.models import FINAL, StepStatus, TaskStatus
from .theme import C

ICONS = {
    StepStatus.PENDING: ("○", C["muted"]), StepStatus.WAITING: ("?", C["warn"]),
    StepStatus.RUNNING: ("◐", C["cyan"]), StepStatus.DONE: ("✓", C["ok"]),
    StepStatus.FAILED: ("✕", C["danger"]), StepStatus.REFUSED: ("⊘", C["danger"]),
    StepStatus.SKIPPED: ("–", C["muted"]),
}


class TaskPanel(QFrame):
    confirm_clicked = Signal()
    refuse_clicked = Signal()
    pause_clicked = Signal()
    resume_clicked = Signal()
    stop_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("taskPanel")
        self.setFixedWidth(350)
        self.task = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 26, 22, 22)
        lay.setSpacing(12)
        lay.addWidget(QLabel("TÂCHE EN COURS", objectName="section"))
        self.goal = QLabel("Aucune tâche pour le moment.", objectName="taskGoal")
        self.goal.setWordWrap(True)
        lay.addWidget(self.goal)
        self.status = QLabel("", objectName="statusPill")
        self.status.hide()
        lay.addWidget(self.status)
        self.steps = QListWidget()
        self.steps.setWordWrap(True)
        lay.addWidget(self.steps, 3)

        self.confirm_box = QFrame(objectName="confirmBox")
        cb = QVBoxLayout(self.confirm_box)
        cb.setContentsMargins(14, 12, 14, 12)
        self.confirm_label = QLabel()
        self.confirm_label.setWordWrap(True)
        cb.addWidget(self.confirm_label)
        row = QHBoxLayout()
        self.btn_confirm = QPushButton("Confirmer", objectName="primary")
        self.btn_refuse = QPushButton("Refuser")
        self.btn_confirm.setAccessibleName("tache-confirmer")
        self.btn_refuse.setAccessibleName("tache-refuser")
        row.addWidget(self.btn_confirm)
        row.addWidget(self.btn_refuse)
        cb.addLayout(row)
        self.confirm_box.hide()
        lay.addWidget(self.confirm_box)

        controls = QHBoxLayout()
        self.btn_pause = QPushButton("Pause")
        self.btn_resume = QPushButton("Reprendre")
        self.btn_stop = QPushButton("STOP", objectName="danger")
        for b in (self.btn_pause, self.btn_resume, self.btn_stop):
            controls.addWidget(b)
        lay.addLayout(controls)
        lay.addWidget(QLabel("JOURNAL", objectName="section"))
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setStyleSheet("font-family: Consolas, monospace; font-size: 12px;")
        lay.addWidget(self.log, 2)

        self.btn_confirm.clicked.connect(self.confirm_clicked)
        self.btn_refuse.clicked.connect(self.refuse_clicked)
        self.btn_pause.clicked.connect(self.pause_clicked)
        self.btn_resume.clicked.connect(self.resume_clicked)
        self.btn_stop.clicked.connect(self.stop_clicked)
        self._set_controls(None)

    @property
    def active(self) -> bool:
        return self.task is not None and self.task.status not in FINAL

    def _set_controls(self, task):
        running = task is not None and task.status not in FINAL
        self.btn_pause.setEnabled(running and task.status != TaskStatus.PAUSED)
        self.btn_resume.setEnabled(running and task.status == TaskStatus.PAUSED)
        self.btn_stop.setEnabled(running)

    def show_task(self, task) -> None:
        self.setFixedWidth(330)
        self.show()
        self.task = task
        self.goal.setText(task.goal)
        self.status.setText(task.status.capitalize())
        self.status.show()
        self.steps.clear()
        for n, step in enumerate(task.steps, 1):
            icon, color = ICONS.get(step.status, ("•", C["muted"]))
            item = QListWidgetItem(f"{icon}  {n}. {step.description}")
            item.setForeground(QColor(color))
            item.setToolTip(f"{step.status} · risque : {step.risk}\n{step.result[:800]}")
            self.steps.addItem(item)
        waiting = task.current if task.status == TaskStatus.WAITING else None
        if waiting is not None:
            self.confirm_label.setText(f"<b>Confirmation requise</b> ({waiting.risk})<br>{waiting.description}")
        self.confirm_box.setVisible(waiting is not None)
        self.log.setPlainText("\n".join(task.log))
        self.log.verticalScrollBar().setValue(self.log.verticalScrollBar().maximum())
        self._set_controls(task)
