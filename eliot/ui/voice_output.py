import logging
import time

from PySide6.QtCore import QObject, QTimer, QUrl, Signal

from ..config import data_dir
from ..voice.speak import HortenseVoice, clean_for_speech, synthesize
from .workers import run_in_thread

log = logging.getLogger("eliot")


class VoiceOutput(QObject):
    started = Signal()
    finished = Signal()
    ended = Signal()

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.hortense = HortenseVoice()
        self._token = 0
        self._player = None
        self._audio = None
        self.dir = data_dir() / "voix"
        self.dir.mkdir(exist_ok=True)
        for old in self.dir.glob("*.mp3"):
            if time.time() - old.stat().st_mtime > 3600:
                try:
                    old.unlink()
                except OSError:
                    pass

    def _ensure_player(self):
        if self._player is None:
            from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
            self._audio = QAudioOutput(self)
            self._player = QMediaPlayer(self)
            self._player.setAudioOutput(self._audio)
            self._player.mediaStatusChanged.connect(self._on_status)
        return self._player

    def speak(self, text: str) -> None:
        text = clean_for_speech(text)
        engine = self.settings.voice_engine
        if not text or engine == "none":
            return
        self.stop()
        token = self._token
        if engine == "hortense":
            self._hortense(text, token)
            return
        run_in_thread(lambda: synthesize(text, self.settings.openai_voice, self.settings.tts_model, self.dir),
                      lambda path: self._play(path, token), lambda err: self._fallback(text, token, err))

    def _play(self, path: str, token: int) -> None:
        if token != self._token:
            return
        try:
            player = self._ensure_player()
            player.setSource(QUrl.fromLocalFile(path))
            player.play()
            self.started.emit()
        except Exception as exc:
            self._fallback(path, token, str(exc))

    def _fallback(self, text: str, token: int, err: str) -> None:
        log.warning("Voix OpenAI indisponible, secours Hortense : %s", err)
        if token == self._token and not text.endswith(".mp3"):
            self._hortense(text, token)

    def _hortense(self, text: str, token: int) -> None:
        try:
            self.hortense.speak(text)
        except Exception as exc:
            log.warning("Hortense indisponible : %s", exc)
            return
        self.started.emit()
        QTimer.singleShot(min(60000, 900 + 65 * len(text)), lambda: token == self._token and self._natural_end())

    def _on_status(self, status) -> None:
        from PySide6.QtMultimedia import QMediaPlayer
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self._natural_end()

    def _natural_end(self) -> None:
        self.finished.emit()
        self.ended.emit()

    def stop(self) -> None:
        self._token += 1
        if self._player is not None:
            self._player.stop()
        self.hortense.stop()
        self.finished.emit()
