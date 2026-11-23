import copy
import threading

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QMainWindow, QMenu, QPushButton, QScrollArea, QStackedWidget,
                               QSystemTrayIcon, QVBoxLayout, QWidget)

from .. import VERSION
from ..agent_workflows.executor import TaskRunner
from ..agent_workflows.models import TaskStatus
from ..assistant import Assistant
from ..commands import router
from ..config import CLAUDE_MODELS, PROVIDERS, data_dir
from ..text import simplify
from ..voice.listen import record, transcribe
from .dialogs import AppsDialog, FoldersDialog, MemoryDialog, SchedulesDialog, SettingsDialog
from .logo import app_icon, logo_pixmap
from .task_panel import TaskPanel
from .voice_output import VoiceOutput
from .widgets import ChatView, CommandBackground, FeatureCard, MicOrb
from .workers import run_in_thread

YES = {"oui", "confirme", "je confirme", "vas y", "ok", "d accord", "continue", "valide", "oui vas y", "go"}
NO = {"non", "refuse", "je refuse", "annule", "non merci", "pas maintenant"}


def _listen(path, stop_event) -> str:
    return transcribe(path) if record(path, stop_event) else ""


class MainWindow(QMainWindow):
    delta = Signal(str)
    task_update = Signal(object)
    wake_detected = Signal(str)
    wake_status = Signal(str)

    def __init__(self, services):
        super().__init__()
        self.s = services
        self.assistant = Assistant(services)
        self.voice = VoiceOutput(services.settings, self)
        self.runner = None
        self.cid = None
        self._token = 0
        self._bubble = None
        self._stream = ""
        self._busy = False
        self._rec_stop = None
        self._asked = None
        self._voice_input = False
        self._quitting = False
        self._tray_hint = False
        self.wake = None
        self.setWindowTitle(f"ELIOT {VERSION}")
        self.resize(1440, 900)
        self.setMinimumSize(1180, 720)
        self.delta.connect(self._on_delta)
        self.task_update.connect(self._on_task_update)
        self.voice.started.connect(self._on_voice_started)
        self.voice.finished.connect(self._on_voice_finished)
        self.voice.ended.connect(self._on_voice_ended)
        self.wake_detected.connect(self._on_wake)
        self.wake_status.connect(self._on_wake_status)
        self._build()
        self._build_tray()
        self.schedule_timer = QTimer(self, interval=15000, timeout=self._check_schedules)
        self.schedule_timer.start()
        QTimer.singleShot(1500, self._apply_wake)
        self._refresh_conversations()
        self._update_status()
        QShortcut(QKeySequence("Escape"), self, activated=self.stop_all)
        QShortcut(QKeySequence("Ctrl+M"), self, activated=self.toggle_mic)
        QShortcut(QKeySequence("Ctrl+N"), self, activated=self.new_conversation)

    # --- construction ---------------------------------------------------------------
    def _build(self):
        root = CommandBackground()
        outer = QVBoxLayout(root)
        outer.setContentsMargins(46, 34, 46, 34)
        shell = QFrame(objectName="shell")
        shell.setAttribute(Qt.WA_StyledBackground, True)
        lay = QHBoxLayout(shell)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(0)
        lay.addWidget(self._sidebar())
        center = QWidget(objectName="center")
        center.setAttribute(Qt.WA_StyledBackground, True)
        col = QVBoxLayout(center)
        col.setContentsMargins(28, 18, 28, 18)
        col.setSpacing(14)
        header = QVBoxLayout()
        header.setSpacing(2)
        header.addWidget(QLabel("ASSISTANT PERSONNEL", objectName="kicker"))
        row = QHBoxLayout()
        self.page_title = QLabel("Accueil", objectName="pageTitle")
        self.status_lbl = QLabel(objectName="statusPill")
        row.addWidget(self.page_title)
        row.addStretch()
        row.addWidget(self.status_lbl)
        header.addLayout(row)
        col.addLayout(header)
        self.stack = QStackedWidget()
        self.stack.setAttribute(Qt.WA_StyledBackground, True)
        self.home = self._home()
        self.chat = ChatView()
        self.stack.addWidget(self.home)
        self.stack.addWidget(self.chat)
        col.addWidget(self.stack, 1)
        col.addWidget(self._input_bar())
        lay.addWidget(center, 1)
        self.task_panel = TaskPanel()
        self.task_panel.setAttribute(Qt.WA_StyledBackground, True)
        self.task_panel.confirm_clicked.connect(lambda: self._answer(True))
        self.task_panel.refuse_clicked.connect(lambda: self._answer(False))
        self.task_panel.pause_clicked.connect(lambda: self.runner and self.runner.pause())
        self.task_panel.resume_clicked.connect(lambda: self.runner and self.runner.resume())
        self.task_panel.stop_clicked.connect(self.stop_all)
        self.task_panel.hide()
        lay.addWidget(self.task_panel)
        outer.addWidget(shell)
        self.setCentralWidget(root)

    def _sidebar(self):
        side = QFrame(objectName="sidebar")
        side.setAttribute(Qt.WA_StyledBackground, True)
        side.setFixedWidth(250)
        lay = QVBoxLayout(side)
        lay.setContentsMargins(18, 24, 18, 18)
        lay.setSpacing(10)
        brand = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(logo_pixmap(44))
        names = QVBoxLayout()
        names.setSpacing(0)
        names.addWidget(QLabel("ELIOT", objectName="brand"))
        names.addWidget(QLabel(f"ASSISTANT IA · V{VERSION}", objectName="version"))
        brand.addWidget(logo)
        brand.addLayout(names)
        brand.addStretch()
        lay.addLayout(brand)
        lay.addSpacing(14)
        new = QPushButton("+  Nouvelle conversation", objectName="primary")
        new.clicked.connect(self.new_conversation)
        lay.addWidget(new)
        lay.addSpacing(10)
        lay.addWidget(QLabel("HISTORIQUE", objectName="section"))
        self.conv_list = QListWidget()
        self.conv_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.conv_list.setTextElideMode(Qt.ElideRight)
        self.conv_list.itemClicked.connect(self._open_conversation)
        self.conv_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.conv_list.customContextMenuRequested.connect(self._conv_menu)
        lay.addWidget(self.conv_list, 1)
        lay.addWidget(QLabel("FONCTIONS", objectName="section"))
        for label, slot in (("Applications", self._open_apps), ("Dossiers", self._open_folders),
                            ("Mémoire", self._open_memory), ("Rappels", self._open_schedules),
                            ("Voix et réglages", self._open_settings)):
            btn = QPushButton(label, objectName="nav")
            btn.clicked.connect(slot)
            lay.addWidget(btn)
        foot = QLabel("Données conservées localement sur ce PC.", objectName="footer")
        foot.setWordWrap(True)
        lay.addWidget(foot)
        return side

    def _home(self):
        page = QWidget(objectName="homePage")
        page.setAttribute(Qt.WA_StyledBackground, True)
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 4, 0, 0)
        lay.setSpacing(12)
        top = QHBoxLayout()
        text = QVBoxLayout()
        self.greeting = QLabel(objectName="greeting")
        self.greeting.setWordWrap(True)
        sub = QLabel("Parle ou écris. Les fonctions ci-dessous ouvrent ce qu'ELIOT peut faire sur ce PC.",
                     objectName="subtitle")
        sub.setWordWrap(True)
        text.addWidget(self.greeting)
        text.addWidget(sub)
        top.addLayout(text, 1)
        self.orb = MicOrb(120)
        self.orb.clicked.connect(self.toggle_mic)
        top.addWidget(self.orb, 0, Qt.AlignRight | Qt.AlignVCenter)
        lay.addLayout(top)
        grid = QGridLayout()
        grid.setSpacing(12)
        cards = (
            ("VOIX", "Parler", "Micro, « Hey Eliot » et réponses à voix haute.", "Activer le micro", self.toggle_mic),
            ("PROGRAMMES", "Applications", "ELIOT n'ouvre que les applications autorisées.", "Gérer", self._open_apps),
            ("FICHIERS", "Dossiers", "Ranger un dossier autorisé, puis annuler si besoin.", "Choisir", self._open_folders),
            ("MÉMOIRE", "Ce qu'il retient", "« Retiens que… » sert dans chaque conversation.", "Voir", self._open_memory),
            ("AGENDA", "Rappels", "Rappels et tâches répétées pendant qu'ELIOT est ouvert.", "Voir", self._open_schedules),
            ("RÉGLAGES", "Voix et messagerie", "Modèle, voix, e-mails et domaines autorisés.", "Configurer", self._open_settings),
        )
        for i, (kicker, title, body, button, slot) in enumerate(cards):
            card = FeatureCard(kicker, title, body, button)
            card.button.clicked.connect(slot)
            grid.addWidget(card, i // 2, i % 2)
        lay.addLayout(grid)
        hint = QLabel("CLIQUE SUR L'ORBE OU CTRL+M POUR PARLER · ÉCHAP POUR TOUT ARRÊTER", objectName="hint")
        hint.setAlignment(Qt.AlignCenter)
        lay.addWidget(hint)
        lay.addStretch(1)
        self._update_greeting()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.viewport().setStyleSheet("background: transparent;")
        scroll.setWidget(page)
        return scroll

    def _input_bar(self):
        bar = QFrame(objectName="inputBar")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(10, 8, 10, 8)
        self.mic_btn = QPushButton("●", objectName="mic")
        self.mic_btn.setCheckable(True)
        self.mic_btn.setToolTip("Parler (Ctrl+M)")
        self.mic_btn.clicked.connect(self.toggle_mic)
        self.input = QLineEdit()
        self.input.setPlaceholderText("Demande quelque chose à ELIOT…  (ex : ouvre Firefox et recherche…)")
        self.input.returnPressed.connect(self.send)
        send = QPushButton("Envoyer", objectName="primary")
        send.clicked.connect(self.send)
        stop = QPushButton("STOP", objectName="danger")
        stop.setToolTip("Tout arrêter (Échap)")
        stop.clicked.connect(self.stop_all)
        for w in (self.mic_btn, self.input, send, stop):
            lay.addWidget(w)
        lay.setStretch(1, 1)
        return bar

    # --- état -----------------------------------------------------------------------
    def _update_greeting(self):
        name = self.s.settings.user_name
        self.greeting.setText(f"Bonjour {name}, je suis ELIOT." if name else "Bonjour, je suis ELIOT.")

    def _update_status(self):
        s = self.s.settings
        model = CLAUDE_MODELS.get(s.model, s.model).split(" (")[0]
        self.status_lbl.setText(PROVIDERS[s.ai_provider] if s.ai_provider == "demo" else f"● {model}")

    def _orb(self, state):
        self.orb.set_state(state)

    def _refresh_conversations(self):
        self.conv_list.clear()
        for conv in self.s.history.conversations():
            item = QListWidgetItem(conv["title"] or "Conversation")
            item.setData(Qt.UserRole, conv["id"])
            self.conv_list.addItem(item)

    def new_conversation(self):
        self.cid = None
        self.chat.clear()
        self.stack.setCurrentWidget(self.home)
        self.page_title.setText("Accueil")
        self.conv_list.clearSelection()

    def _open_conversation(self, item):
        self.cid = item.data(Qt.UserRole)
        self.chat.clear()
        for msg in self.s.history.messages(self.cid):
            self.chat.add_message(msg["role"], msg["content"])
        self.stack.setCurrentWidget(self.chat)
        self.page_title.setText(item.text())

    def _conv_menu(self, pos):
        item = self.conv_list.itemAt(pos)
        if item is None:
            return
        menu = QMenu(self)
        delete = menu.addAction("Supprimer la conversation")
        if menu.exec(self.conv_list.mapToGlobal(pos)) == delete:
            cid = item.data(Qt.UserRole)
            self.s.history.delete_conversation(cid)
            if cid == self.cid:
                self.new_conversation()
            self._refresh_conversations()

    # --- conversation ---------------------------------------------------------------
    def _add(self, role, text):
        bubble = self.chat.add_message(role, text)
        self.s.history.add_message(self.cid, role, text)
        return bubble

    def send(self, text=None, voice=False):
        text = (text if isinstance(text, str) else self.input.text()).strip()
        if not text:
            return
        self._voice_input = voice
        self.input.clear()
        if self.task_panel.active and self.runner and self.task_panel.task.status == TaskStatus.WAITING:
            answer = simplify(router.clean(text)[0])
            if answer in YES or answer in NO:
                self._add("user", text)
                self._answer(answer in YES)
                return
        if router.parse(text).kind == "stop":
            self.stop_all()
            if self.cid:
                self._add("user", text)
            return
        if self._busy:
            self.input.setText(text)
            self.input.setPlaceholderText("Je termine la demande précédente…")
            return
        self.voice.stop()
        if self.cid is None:
            self.cid = self.s.history.new_conversation(text[:60])
            self._refresh_conversations()
            self.page_title.setText(text[:60])
        self.stack.setCurrentWidget(self.chat)
        self._add("user", text)
        self._bubble = self.chat.add_message("assistant", "")
        self._bubble.set_thinking()
        self._stream = ""
        self._busy = True
        self._token += 1
        token = self._token
        self._orb("thinking")
        history = [{"role": m["role"], "content": m["content"]} for m in self.s.history.messages(self.cid, 30)]

        def emit(chunk):
            if token == self._token:
                self.delta.emit(chunk)

        run_in_thread(lambda: self.assistant.handle(text, history, on_delta=emit),
                      lambda reply: self._on_reply(reply, token), lambda err: self._on_error(err, token))

    def _on_delta(self, chunk):
        if self._bubble is not None and self._busy:
            self._stream += chunk
            self._bubble.set_text(self._stream)

    def _on_reply(self, reply, token):
        if token != self._token:
            return
        self._busy = False
        self._orb("idle")
        if reply.kind == "stop":
            self.stop_all()
        self._bubble.set_text(reply.text)
        self.s.history.add_message(self.cid, "assistant", reply.text)
        if reply.task is not None:
            if len(reply.task.steps) > 1:
                self.say(reply.text)
            self.start_task(reply.task)
        else:
            self.say(reply.text)

    def _on_error(self, err, token):
        if token != self._token:
            return
        self._busy = False
        self._orb("idle")
        self._bubble.set_error(err)
        self.s.history.add_message(self.cid, "assistant", err)
        self.say(err)

    def say(self, text):
        if self.s.settings.speak_replies:
            self.voice.speak(text)

    # --- tâches ---------------------------------------------------------------------
    def start_task(self, task):
        if self.task_panel.active:
            self._add("assistant", "Une tâche est déjà en cours. Termine-la ou appuie sur STOP.")
            return
        runner = TaskRunner(self.s.toolbox, self.s.planner, self.s.settings, on_update=self.task_update.emit)
        self.runner = runner
        self._asked = None
        self.task_panel.show_task(copy.deepcopy(task))
        run_in_thread(lambda: runner.run(task), self._on_task_done, self._on_task_error)

    def _on_task_update(self, task):
        self.task_panel.show_task(task)
        step = task.current
        key = task.steps.index(step) if step is not None else None
        if task.status == TaskStatus.WAITING and step is not None and self._asked != key:
            self._asked = key
            self.say(f"Confirmation requise : {step.description}. Dis oui ou non.")

    def _on_task_done(self, task):
        self.task_panel.show_task(task)
        if self.cid is None:
            self.cid = self.s.history.new_conversation(task.goal[:60])
            self._refresh_conversations()
        if task.summary:
            self._add("assistant", task.summary)
            self.say(task.summary)
        self.s.history.log_action("tâche", task.goal, task.status)

    def _on_task_error(self, err):
        self._add("assistant", f"La tâche a rencontré une erreur : {err}")

    def _answer(self, ok: bool):
        if self.runner is not None:
            self.voice.stop()
            self.runner.confirm(ok)

    # --- micro & stop ---------------------------------------------------------------
    def toggle_mic(self):
        if self._rec_stop is not None:
            self._rec_stop.set()
            return
        self.voice.stop()
        if self.wake is not None:
            self.wake.wait_until_released()
        stop_event = threading.Event()
        self._rec_stop = stop_event
        self.mic_btn.setChecked(True)
        self._orb("listening")
        path = data_dir() / "micro.wav"
        run_in_thread(lambda: _listen(path, stop_event), self._on_heard, self._on_mic_error)

    def _mic_reset(self):
        self._rec_stop = None
        self.mic_btn.setChecked(False)
        self._orb("idle")
        if self.wake is not None:
            self.wake.resume()

    def _on_heard(self, text):
        cancelled = self._rec_stop is not None and self._rec_stop.is_set() and not text
        self._mic_reset()
        if text:
            self.send(text, voice=True)
        elif self._voice_input:
            self._voice_input = False
        elif not cancelled:
            self.input.setPlaceholderText("Je n'ai pas compris. Parle plus près du micro, ou écris ta demande.")
            self._on_mic_error("Je n'ai pas compris. Parle plus près du micro, ou écris ta demande.")

    def _on_mic_error(self, err):
        self._mic_reset()
        if self.cid is None:
            self.cid = self.s.history.new_conversation("Micro")
            self._refresh_conversations()
        self.stack.setCurrentWidget(self.chat)
        self.chat.add_message("assistant", "").set_error(err)

    def stop_all(self):
        self._token += 1
        self._voice_input = False
        if self._busy and self._bubble is not None:
            self._bubble.set_text((self._stream or "") + "\n\n*Interrompu.*")
            self.s.history.add_message(self.cid, "assistant", self._stream or "Interrompu.")
        self._busy = False
        if self.runner is not None:
            self.runner.stop()
        if self._rec_stop is not None:
            self._rec_stop.set()
        self.voice.stop()
        self._orb("idle")

    # --- configuration --------------------------------------------------------------
    def _open_settings(self):
        if SettingsDialog(self.s.settings, self).exec():
            self._update_status()
            self._update_greeting()
            self._apply_wake()

    def _open_memory(self):
        MemoryDialog(self.s.memory, self).exec()

    def _open_schedules(self):
        SchedulesDialog(self.s.scheduler, self).exec()

    # --- voix naturelle, « Hey Eliot », barre des tâches, programmations -----------------
    def _on_voice_started(self):
        self._orb("speaking")
        if self.wake is not None:
            self.wake.pause()

    def _on_voice_finished(self):
        self._orb("idle")
        if self.wake is not None and self._rec_stop is None:
            self.wake.resume()

    def _on_voice_ended(self):
        if self._voice_input and self.s.settings.voice_followup and self._rec_stop is None and not self._busy:
            QTimer.singleShot(250, self.toggle_mic)

    def _apply_wake(self):
        wanted = self.s.settings.wake_word
        if self.wake is not None and (not wanted or not self.wake.running):
            self.wake.stop()
            self.wake = None
        if wanted and self.wake is None:
            from ..voice.wakeword import WakeWordListener
            confirm = transcribe if self.s.settings.wake_confirm_online else None
            self.wake = WakeWordListener(data_dir() / "modeles", on_detect=self.wake_detected.emit,
                                         on_status=self.wake_status.emit, confirm=confirm)
            self.wake.start()
        self._update_wake_action()

    def _on_wake_status(self, message):
        self.status_lbl.setToolTip(message)
        self.input.setPlaceholderText(message)

    def _on_wake(self, command):
        self.show_window()
        self.voice.stop()
        if command:
            self.send(command, voice=True)
            if self.wake is not None:
                self.wake.resume()
        else:
            self._voice_input = True
            self.toggle_mic()

    def _build_tray(self):
        self.tray = QSystemTrayIcon(app_icon(), self)
        self.tray.setToolTip("ELIOT")
        menu = QMenu()
        menu.addAction("Afficher ELIOT", self.show_window)
        menu.addAction("Parler à ELIOT", lambda: (self.show_window(), self.toggle_mic()))
        self.wake_action = QAction("Écoute « Hey Eliot »", self, checkable=True)
        self.wake_action.toggled.connect(self._toggle_wake_setting)
        menu.addAction(self.wake_action)
        menu.addSeparator()
        menu.addAction("Quitter ELIOT", self.quit_app)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda reason: reason == QSystemTrayIcon.Trigger and self.show_window())
        self._tray_menu = menu
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()

    def _update_wake_action(self):
        self.wake_action.blockSignals(True)
        self.wake_action.setChecked(self.s.settings.wake_word)
        self.wake_action.blockSignals(False)

    def _toggle_wake_setting(self, on):
        self.s.settings.wake_word = on
        self.s.settings.save()
        self._apply_wake()

    def notify(self, title, text):
        if self.tray.isVisible():
            self.tray.showMessage(title, text[:240], app_icon(), 8000)

    def show_window(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def quit_app(self):
        self._quitting = True
        self.close()
        QApplication.quit()

    def _check_schedules(self):
        for item in self.s.scheduler.pop_due():
            if item.kind == "reminder":
                self.notify("Rappel ELIOT", item.text)
                if self.cid is None:
                    self.cid = self.s.history.new_conversation("Rappels")
                    self._refresh_conversations()
                self.stack.setCurrentWidget(self.chat)
                self._add("assistant", f"⏰ Rappel : {item.text}")
                self.say(f"Rappel : {item.text}")
            elif self._busy or self.task_panel.active:
                self.s.scheduler.postpone(item)
            else:
                self.notify("Tâche programmée", item.text)
                self.send(item.text)

    def _open_apps(self):
        AppsDialog(self.s.registry, self).exec()

    def _open_folders(self):
        FoldersDialog(self.s.settings, self).exec()

    def closeEvent(self, event):
        if self.s.settings.keep_in_tray and self.tray.isVisible() and not self._quitting:
            event.ignore()
            self.hide()
            if not self._tray_hint:
                self._tray_hint = True
                self.notify("ELIOT reste actif", "Je reste dans la barre des tâches pour « Hey Eliot » et tes rappels. "
                            "Clic droit sur l'icône > Quitter pour me fermer.")
            return
        self.stop_all()
        if self.wake is not None:
            self.wake.stop()
        self.tray.hide()
        super().closeEvent(event)
        if not self._quitting:
            QApplication.quit()
