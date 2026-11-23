from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
                               QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox,
                               QPlainTextEdit, QPushButton, QSpinBox, QTableWidget, QTableWidgetItem, QTabWidget,
                               QVBoxLayout, QWidget)

from ..config import CLAUDE_MODELS, OPENAI_VOICES, PROVIDERS, VOICE_ENGINES
from ..mail.accounts import GMAIL
from ..scheduler import describe
from ..secrets_store import ANTHROPIC, OPENAI, get_secret, set_secret


def _combo(options: dict, current: str) -> QComboBox:
    box = QComboBox()
    for key, label in options.items():
        box.addItem(label, key)
    idx = box.findData(current)
    box.setCurrentIndex(max(0, idx))
    return box


def _key_field(name: str) -> QLineEdit:
    field = QLineEdit()
    field.setEchoMode(QLineEdit.Password)
    field.setPlaceholderText("•••••• clé enregistrée (laisser vide pour la garder)" if get_secret(name)
                             else "Colle ta clé ici")
    return field


class SettingsDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Paramètres d'ELIOT")
        self.resize(640, 560)
        tabs = QTabWidget()
        tabs.addTab(self._general(), "Général")
        tabs.addTab(self._ai(), "Intelligence artificielle")
        tabs.addTab(self._voice(), "Voix")
        tabs.addTab(self._mail(), "Messagerie")
        tabs.addTab(self._web(), "Internet")
        tabs.addTab(self._agent(), "Agent")
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText("Enregistrer")
        buttons.button(QDialogButtonBox.Cancel).setText("Annuler")
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.addWidget(tabs)
        lay.addWidget(buttons)

    def _page(self):
        page = QWidget()
        form = QFormLayout(page)
        form.setContentsMargins(18, 18, 18, 18)
        form.setSpacing(12)
        return page, form

    def _general(self):
        page, form = self._page()
        self.user_name = QLineEdit(self.settings.user_name)
        self.speak_replies = QCheckBox("Lire les réponses à voix haute")
        self.speak_replies.setChecked(self.settings.speak_replies)
        self.keep_in_tray = QCheckBox("Garder ELIOT actif dans la barre des tâches quand je ferme la fenêtre")
        self.keep_in_tray.setChecked(self.settings.keep_in_tray)
        form.addRow("Ton prénom", self.user_name)
        form.addRow("", self.speak_replies)
        form.addRow("", self.keep_in_tray)
        return page

    def _ai(self):
        page, form = self._page()
        self.provider = _combo(PROVIDERS, self.settings.ai_provider)
        self.model = _combo(CLAUDE_MODELS, self.settings.model)
        self.anthropic_key = _key_field(ANTHROPIC)
        form.addRow("Moteur", self.provider)
        form.addRow("Modèle Claude", self.model)
        form.addRow("Clé Anthropic", self.anthropic_key)
        note = QLabel("La clé Anthropic est stockée dans le Gestionnaire d'identification Windows, jamais dans un "
                      "fichier. La clé Emergent intégrée consomme le crédit du compte Emergent.")
        note.setWordWrap(True)
        note.setObjectName("hint")
        form.addRow("", note)
        return page

    def _voice(self):
        page, form = self._page()
        self.voice_engine = _combo(VOICE_ENGINES, self.settings.voice_engine)
        self.openai_voice = _combo({v: v.capitalize() for v in OPENAI_VOICES}, self.settings.openai_voice)
        self.tts_model = _combo({"tts-1": "Standard (rapide)", "tts-1-hd": "Haute définition"}, self.settings.tts_model)
        self.openai_key = _key_field(OPENAI)
        form.addRow("Voix", self.voice_engine)
        form.addRow("Timbre OpenAI", self.openai_voice)
        form.addRow("Qualité", self.tts_model)
        form.addRow("Clé OpenAI (optionnelle)", self.openai_key)
        self.wake_word = QCheckBox("Activer « Hey Eliot » (écoute permanente du micro)")
        self.wake_word.setChecked(self.settings.wake_word)
        self.wake_confirm = QCheckBox("Confirmer le mot d'activation avec Whisper (plus fiable, extrait de 3 s envoyé)")
        self.wake_confirm.setChecked(self.settings.wake_confirm_online)
        self.followup = QCheckBox("Conversation naturelle : réécouter après chaque réponse vocale")
        self.followup.setChecked(self.settings.voice_followup)
        form.addRow("", self.wake_word)
        form.addRow("", self.wake_confirm)
        form.addRow("", self.followup)
        note = QLabel("Sans clé OpenAI, la clé Emergent intégrée est utilisée pour la voix et le micro. "
                      "Les voix OpenAI gardent un léger accent anglais en français.")
        note.setWordWrap(True)
        note.setObjectName("hint")
        form.addRow("", note)
        return page

    def _mail(self):
        page, form = self._page()
        self.outlook = QCheckBox("Utiliser Outlook installé sur ce PC")
        self.outlook.setChecked(self.settings.outlook_enabled)
        self.gmail_address = QLineEdit(self.settings.gmail_address)
        self.gmail_address.setPlaceholderText("prenom.nom@gmail.com (vide = Gmail désactivé)")
        self.gmail_password = _key_field(GMAIL)
        form.addRow("", self.outlook)
        form.addRow("Adresse Gmail", self.gmail_address)
        form.addRow("Mot de passe d'application", self.gmail_password)
        note = QLabel("Gmail : active la validation en deux étapes puis crée un mot de passe d'application sur "
                      "<a style='color:#22D3EE' href='https://myaccount.google.com/apppasswords'>myaccount.google.com/apppasswords</a>. "
                      "Il est stocké dans le Gestionnaire d'identification Windows. ELIOT n'envoie un e-mail "
                      "qu'après ta confirmation.")
        note.setWordWrap(True)
        note.setOpenExternalLinks(True)
        note.setObjectName("hint")
        form.addRow("", note)
        return page

    def _web(self):
        page, form = self._page()
        self.allow_all = QCheckBox("Autoriser tous les sites")
        self.allow_all.setChecked(self.settings.allow_all_domains)
        self.allow_results = QCheckBox("Autoriser l'ouverture des résultats de recherche")
        self.allow_results.setChecked(self.settings.allow_search_results)
        self.domains = QPlainTextEdit("\n".join(self.settings.allowed_domains))
        form.addRow("", self.allow_all)
        form.addRow("", self.allow_results)
        form.addRow("Domaines autorisés\n(un par ligne)", self.domains)
        return page

    def _agent(self):
        page, form = self._page()
        self.adaptive = QCheckBox("Claude réévalue le plan après chaque étape (workflows adaptatifs)")
        self.adaptive.setChecked(self.settings.adaptive_workflows)
        self.confirm_actions = QCheckBox("Demander confirmation aussi pour ouvrir des applications et des pages")
        self.confirm_actions.setChecked(self.settings.confirm_actions)
        self.max_steps = QSpinBox(minimum=1, maximum=40, value=self.settings.max_steps)
        self.max_seconds = QSpinBox(minimum=30, maximum=3600, value=self.settings.max_task_seconds, suffix=" s")
        form.addRow("", self.adaptive)
        form.addRow("", self.confirm_actions)
        form.addRow("Étapes max par tâche", self.max_steps)
        form.addRow("Durée max par tâche", self.max_seconds)
        note = QLabel("Les modifications (écrire, cliquer, fermer, ranger) demandent toujours une confirmation.")
        note.setWordWrap(True)
        note.setObjectName("hint")
        form.addRow("", note)
        return page

    def _save(self):
        s = self.settings
        if self.provider.currentData() == "anthropic" and not (self.anthropic_key.text().strip() or get_secret(ANTHROPIC)):
            QMessageBox.warning(self, "Clé manquante", "Ajoute ta clé Anthropic pour utiliser ce moteur.")
            return
        s.user_name = self.user_name.text().strip()
        s.speak_replies = self.speak_replies.isChecked()
        s.ai_provider = self.provider.currentData()
        s.model = self.model.currentData()
        s.voice_engine = self.voice_engine.currentData()
        s.openai_voice = self.openai_voice.currentData()
        s.tts_model = self.tts_model.currentData()
        s.allow_all_domains = self.allow_all.isChecked()
        s.allow_search_results = self.allow_results.isChecked()
        s.allowed_domains = [d.strip().lower() for d in self.domains.toPlainText().splitlines() if d.strip()]
        s.adaptive_workflows = self.adaptive.isChecked()
        s.confirm_actions = self.confirm_actions.isChecked()
        s.max_steps = self.max_steps.value()
        s.max_task_seconds = self.max_seconds.value()
        s.keep_in_tray = self.keep_in_tray.isChecked()
        s.wake_word = self.wake_word.isChecked()
        s.wake_confirm_online = self.wake_confirm.isChecked()
        s.voice_followup = self.followup.isChecked()
        s.outlook_enabled = self.outlook.isChecked()
        s.gmail_address = self.gmail_address.text().strip()
        for field, name in ((self.anthropic_key, ANTHROPIC), (self.openai_key, OPENAI), (self.gmail_password, GMAIL)):
            if field.text().strip():
                set_secret(name, field.text())
        s.save()
        self.accept()


COLS = ["Active", "Nom", "Catégorie", "Commande ou chemin", "Contrôle clavier/souris"]


class AppsDialog(QDialog):
    def __init__(self, registry, parent=None):
        super().__init__(parent)
        self.registry = registry
        self.setWindowTitle("Applications autorisées")
        self.resize(900, 560)
        lay = QVBoxLayout(self)
        info = QLabel("ELIOT ne peut ouvrir que les applications actives ci-dessous, et ne peut écrire ou cliquer "
                      "que dans celles où « Contrôle » est coché. Chaque modification reste soumise à confirmation.")
        info.setWordWrap(True)
        info.setObjectName("hint")
        lay.addWidget(info)
        self.table = QTableWidget(0, len(COLS))
        self.table.setHorizontalHeaderLabels(COLS)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        lay.addWidget(self.table)
        row = QHBoxLayout()
        for label, slot in (("Ajouter…", self._add), ("Parcourir…", self._browse), ("Supprimer", self._remove),
                            ("Détecter les logiciels installés", self._detect)):
            btn = QPushButton(label)
            btn.clicked.connect(slot)
            row.addWidget(btn)
        row.addStretch()
        save = QPushButton("Enregistrer", objectName="primary")
        save.clicked.connect(self._save)
        row.addWidget(save)
        lay.addLayout(row)
        self._fill()

    def _check(self, value: bool) -> QTableWidgetItem:
        item = QTableWidgetItem()
        item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
        item.setCheckState(Qt.Checked if value else Qt.Unchecked)
        return item

    def _fill(self):
        self.table.setRowCount(0)
        for app in self.registry.apps:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, self._check(app.enabled))
            self.table.setItem(r, 1, QTableWidgetItem(app.name))
            self.table.setItem(r, 2, QTableWidgetItem(app.category))
            self.table.setItem(r, 3, QTableWidgetItem(app.exe or app.launch))
            self.table.setItem(r, 4, self._check(app.allow_control))
        self.table.resizeColumnsToContents()

    def _sync(self):
        for r, app in enumerate(self.registry.apps):
            app.enabled = self.table.item(r, 0).checkState() == Qt.Checked
            app.name = self.table.item(r, 1).text().strip() or app.name
            app.category = self.table.item(r, 2).text().strip() or app.category
            cmd = self.table.item(r, 3).text().strip()
            if Path(cmd).is_absolute():
                app.exe = cmd
            else:
                app.exe, app.launch = "", cmd
            app.allow_control = self.table.item(r, 4).checkState() == Qt.Checked

    def _add(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choisir le programme", "C:\\Program Files", "Programmes (*.exe)")
        if not path:
            return
        name, ok = QInputDialog.getText(self, "Nom de l'application", "Comment l'appelles-tu ?", text=Path(path).stem)
        if ok and name.strip():
            self._sync()
            self.registry.add(name.strip(), str(Path(path)))
            self._fill()

    def _browse(self):
        r = self.table.currentRow()
        if r < 0:
            return
        path, _ = QFileDialog.getOpenFileName(self, "Emplacement du programme", "C:\\Program Files", "Programmes (*.exe)")
        if path:
            self.table.item(r, 3).setText(str(Path(path)))

    def _remove(self):
        r = self.table.currentRow()
        if r >= 0:
            self._sync()
            self.registry.remove(self.registry.apps[r].key)
            self._fill()

    def _detect(self):
        self._sync()
        found = self.registry.autodetect()
        self._fill()
        QMessageBox.information(self, "Détection", "Trouvés : " + (", ".join(found) if found else "aucun nouveau logiciel."))

    def _save(self):
        self._sync()
        self.registry.save()
        self.accept()


class FoldersDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Dossiers autorisés")
        self.resize(620, 420)
        lay = QVBoxLayout(self)
        info = QLabel("ELIOT peut lister et ranger uniquement les fichiers de ces dossiers (et leurs sous-dossiers).")
        info.setWordWrap(True)
        info.setObjectName("hint")
        lay.addWidget(info)
        self.list = QListWidget()
        self.list.addItems(settings.allowed_folders)
        lay.addWidget(self.list)
        row = QHBoxLayout()
        add = QPushButton("Ajouter un dossier…")
        rem = QPushButton("Retirer")
        save = QPushButton("Enregistrer", objectName="primary")
        add.clicked.connect(self._add)
        rem.clicked.connect(lambda: self.list.takeItem(self.list.currentRow()))
        save.clicked.connect(self._save)
        row.addWidget(add)
        row.addWidget(rem)
        row.addStretch()
        row.addWidget(save)
        lay.addLayout(row)

    def _add(self):
        path = QFileDialog.getExistingDirectory(self, "Choisir un dossier")
        if path:
            self.list.addItem(str(Path(path)))

    def _save(self):
        self.settings.allowed_folders = [self.list.item(i).text() for i in range(self.list.count())]
        self.settings.save()
        self.accept()


class MemoryDialog(QDialog):
    def __init__(self, memory, parent=None):
        super().__init__(parent)
        self.memory = memory
        self.setWindowTitle("Mémoire d'ELIOT")
        self.resize(620, 440)
        lay = QVBoxLayout(self)
        info = QLabel("Ce qu'ELIOT sait de toi. Ces informations restent sur ce PC et sont rappelées à Claude à chaque "
                      "conversation. Tu peux aussi dire « retiens que… » ou « oublie que… ».")
        info.setWordWrap(True)
        info.setObjectName("hint")
        lay.addWidget(info)
        self.list = QListWidget()
        lay.addWidget(self.list)
        row = QHBoxLayout()
        add = QPushButton("Ajouter…")
        rem = QPushButton("Supprimer")
        close = QPushButton("Fermer", objectName="primary")
        add.clicked.connect(self._add)
        rem.clicked.connect(self._remove)
        close.clicked.connect(self.accept)
        row.addWidget(add)
        row.addWidget(rem)
        row.addStretch()
        row.addWidget(close)
        lay.addLayout(row)
        self._fill()

    def _fill(self):
        self.list.clear()
        for item in self.memory.all():
            entry = QListWidgetItem(item["content"])
            entry.setData(Qt.UserRole, item["id"])
            self.list.addItem(entry)

    def _add(self):
        text, ok = QInputDialog.getText(self, "Retenir", "Que dois-je retenir ?")
        if ok and text.strip():
            self.memory.add(text)
            self._fill()

    def _remove(self):
        item = self.list.currentItem()
        if item is not None:
            self.memory.remove(item.data(Qt.UserRole))
            self._fill()


class SchedulesDialog(QDialog):
    def __init__(self, scheduler, parent=None):
        super().__init__(parent)
        self.scheduler = scheduler
        self.setWindowTitle("Rappels et automatisations")
        self.resize(680, 440)
        lay = QVBoxLayout(self)
        info = QLabel("Crée-les à la voix ou par écrit : « rappelle-moi d'appeler Paul demain à 15h », « chaque matin "
                      "à 9h, résume mes e-mails », « tous les lundis à 8h, range le dossier Téléchargements ». "
                      "ELIOT doit être ouvert (ou dans la barre des tâches) pour les exécuter.")
        info.setWordWrap(True)
        info.setObjectName("hint")
        lay.addWidget(info)
        self.list = QListWidget()
        lay.addWidget(self.list)
        row = QHBoxLayout()
        rem = QPushButton("Supprimer")
        close = QPushButton("Fermer", objectName="primary")
        rem.clicked.connect(self._remove)
        close.clicked.connect(self.accept)
        row.addWidget(rem)
        row.addStretch()
        row.addWidget(close)
        lay.addLayout(row)
        self._fill()

    def _fill(self):
        self.list.clear()
        for item in self.scheduler.items:
            entry = QListWidgetItem(describe(item))
            entry.setData(Qt.UserRole, item.id)
            self.list.addItem(entry)

    def _remove(self):
        item = self.list.currentItem()
        if item is not None:
            self.scheduler.remove(item.data(Qt.UserRole))
            self._fill()
