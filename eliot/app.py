import logging
import os
import sys

from .config import data_dir


def _setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(data_dir() / "eliot.log", encoding="utf-8")],
    )


def run():
    _setup_logging()
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Eliot.Assistant")
        except Exception:
            pass
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication

    from .services import build_services
    from .ui.logo import app_icon
    from .ui.main_window import MainWindow
    from .ui.theme import QSS

    from PySide6.QtCore import QLockFile
    from PySide6.QtWidgets import QMessageBox

    app = QApplication(sys.argv)
    app.setApplicationName("ELIOT")
    app.setFont(QFont("Segoe UI", 10))
    lock = QLockFile(str(data_dir() / "eliot.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(200):
        QMessageBox.information(None, "ELIOT", "ELIOT est déjà ouvert (regarde dans la barre des tâches, près de l'horloge).")
        sys.exit(0)
    sys.excepthook = lambda *exc: logging.getLogger("eliot").error("Erreur non gérée", exc_info=exc)
    app.setQuitOnLastWindowClosed(False)
    app.setStyleSheet(QSS)
    app.setWindowIcon(app_icon())
    services = build_services()
    window = MainWindow(services)
    window.show()
    code = app.exec()
    services.browser.shutdown()
    lock.unlock()
    sys.exit(code)
