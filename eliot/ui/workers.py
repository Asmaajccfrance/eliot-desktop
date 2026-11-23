"""Exécution des appels lents (IA, voix, actions) hors du thread graphique."""
import logging

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal

log = logging.getLogger("eliot")
_jobs = set()


class _Signals(QObject):
    done = Signal(object)
    failed = Signal(str)


class _Job(QRunnable):
    def __init__(self, fn):
        super().__init__()
        self.fn = fn
        self.signals = _Signals()

    def run(self):
        try:
            result = self.fn()
        except Exception as exc:
            log.exception("Erreur dans une tâche de fond")
            self._emit(self.signals.failed, str(exc) or exc.__class__.__name__)
            return
        self._emit(self.signals.done, result)

    @staticmethod
    def _emit(signal, value):
        try:
            signal.emit(value)
        except RuntimeError:
            pass


def run_in_thread(fn, on_done=None, on_error=None) -> None:
    job = _Job(fn)
    job.setAutoDelete(False)
    if on_done:
        job.signals.done.connect(on_done, Qt.QueuedConnection)
    if on_error:
        job.signals.failed.connect(on_error, Qt.QueuedConnection)
    job.signals.done.connect(lambda *_: _jobs.discard(job), Qt.QueuedConnection)
    job.signals.failed.connect(lambda *_: _jobs.discard(job), Qt.QueuedConnection)
    _jobs.add(job)
    QThreadPool.globalInstance().start(job)
