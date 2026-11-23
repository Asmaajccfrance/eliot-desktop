import time

import pytest

pytest.importorskip("PySide6")


def _pump(app, seconds=1.0, until=None):
    end = time.time() + seconds
    while time.time() < end:
        app.processEvents()
        if until and until():
            return True
        time.sleep(0.02)
    return False


@pytest.fixture
def window(services):
    from PySide6.QtWidgets import QApplication
    from eliot.ui.main_window import MainWindow
    from eliot.ui.theme import QSS
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(QSS)
    services.settings.speak_replies = False
    w = MainWindow(services)
    w.show()
    yield app, w
    w.close()


def test_window_builds(window):
    app, w = window
    assert w.windowTitle().startswith("ELIOT")
    assert w.stack.currentWidget() is w.home


def test_chat_message_flow(window, services):
    app, w = window
    w.send("bonjour, comment vas-tu ?")
    assert _pump(app, 3, until=lambda: not w._busy)
    msgs = services.history.messages(w.cid)
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    assert msgs[1]["content"] == "réponse"


def test_action_flow_with_task_panel(window, services):
    app, w = window
    w.send("ouvre Firefox")
    assert _pump(app, 4, until=lambda: w.task_panel.task is not None and not w.task_panel.active
                 and w.task_panel.task.summary)
    assert services.launcher.opened == ["firefox"]
    assert "Firefox" in services.history.messages(w.cid)[-1]["content"]


def test_confirmation_by_voice_word(window, services):
    app, w = window
    services.windows.windows.append({"title": "Sans titre - Bloc-notes", "process": "notepad.exe", "handle": 1})
    w.send("ouvre le bloc-notes puis écris bonjour")
    assert _pump(app, 4, until=lambda: w.task_panel.confirm_box.isVisible())
    w.send("oui")
    assert _pump(app, 4, until=lambda: not w.task_panel.active)
    assert services.windows.typed == ["bonjour"]


def test_stop_button(window, services):
    app, w = window
    w.send("ouvre le bloc-notes puis écris bonjour")
    assert _pump(app, 4, until=lambda: w.task_panel.confirm_box.isVisible())
    w.stop_all()
    assert _pump(app, 4, until=lambda: not w.task_panel.active)
    assert w.task_panel.task.status == "arrêtée"


def test_dialogs_open(window, services):
    from eliot.ui.dialogs import AppsDialog, FoldersDialog, SettingsDialog
    app, w = window
    d = SettingsDialog(services.settings, w)
    d.user_name.setText("Marc")
    d._save()
    assert services.settings.user_name == "Marc"
    a = AppsDialog(services.registry, w)
    assert a.table.rowCount() == len(services.registry.apps)
    a._save()
    FoldersDialog(services.settings, w)._save()


def test_reminder_fires(window, services):
    from datetime import datetime, timedelta
    app, w = window
    services.scheduler.add("reminder", "boire de l'eau", datetime.now() - timedelta(seconds=1))
    w._check_schedules()
    assert "Rappel : boire de l'eau" in services.history.messages(w.cid)[-1]["content"]
    assert services.scheduler.items == []


def test_scheduled_task_runs(window, services):
    from datetime import datetime, timedelta
    app, w = window
    services.scheduler.add("task", "ouvre Firefox", datetime.now() - timedelta(seconds=1))
    w._check_schedules()
    assert _pump(app, 4, until=lambda: services.launcher.opened == ["firefox"])


def test_memory_and_schedule_dialogs(window, services):
    from eliot.ui.dialogs import MemoryDialog, SchedulesDialog
    app, w = window
    services.memory.add("Je travaille sur le site de la boulangerie")
    assert MemoryDialog(services.memory, w).list.count() == 1
    from datetime import datetime, timedelta
    services.scheduler.add("reminder", "x", datetime.now() + timedelta(hours=1))
    assert SchedulesDialog(services.scheduler, w).list.count() == 1


def test_wake_command_is_sent(window, services):
    app, w = window
    w._on_wake("ouvre Firefox")
    assert _pump(app, 4, until=lambda: services.launcher.opened == ["firefox"])
    assert w._voice_input is True
