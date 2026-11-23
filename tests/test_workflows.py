import threading
import time

import pytest

from eliot.agent_workflows.executor import TaskRunner
from eliot.agent_workflows.models import StepStatus, Task, TaskStatus
from eliot.agent_workflows.tools import ToolError
from eliot.assistant import Assistant


def test_open_app_when_not_running_opens(services):
    assert services.toolbox.run("open_app", {"name": "Firefox"}) == "J'ouvre Firefox."
    assert services.launcher.opened == ["firefox"]


def test_activate_unknown_running_opens_instead(services):
    out = services.toolbox.run("activate_window", {"title": "Firefox"})
    assert "Firefox" in out and services.launcher.opened == ["firefox"]


def test_activate_running_window(services):
    services.launcher.running.add("firefox")
    services.windows.windows.append({"title": "Accueil — Mozilla Firefox", "process": "firefox.exe", "handle": 7})
    assert "premier plan" in services.toolbox.run("activate_window", {"title": "firefox"})
    assert services.launcher.opened == []


def test_unauthorized_app(services):
    with pytest.raises(ToolError):
        services.toolbox.run("open_app", {"name": "Logiciel Mystère"})
    services.registry.get("firefox").enabled = False
    with pytest.raises(ToolError):
        services.toolbox.run("open_app", {"name": "Firefox"})


def test_list_windows_filters_unauthorized(services):
    services.windows.windows += [
        {"title": "Sans titre - Bloc-notes", "process": "notepad.exe", "handle": 1},
        {"title": "Banque - Application secrète", "process": "banque.exe", "handle": 2},
    ]
    out = services.toolbox.run("list_windows", {})
    assert "Bloc-notes" in out and "Banque" not in out


def test_type_requires_control_permission(services):
    services.windows.windows.append({"title": "Projet - Cursor", "process": "cursor.exe", "handle": 3})
    with pytest.raises(ToolError):
        services.toolbox.run("type_text", {"text": "x", "window": "Cursor"})
    services.windows.windows.append({"title": "Sans titre - Bloc-notes", "process": "notepad.exe", "handle": 1})
    services.toolbox.run("type_text", {"text": "Bonjour", "window": "bloc-notes"})
    assert services.windows.typed == ["Bonjour"]


def test_foreground_not_allowed(services):
    services.windows.fg = {"title": "Banque", "process": "banque.exe", "handle": 9}
    with pytest.raises(ToolError):
        services.toolbox.run("press_keys", {"keys": "ctrl s"})


def test_local_plan_firefox_search(services):
    task = services.planner.plan("Eliot, ouvre Firefox et recherche la météo à Paris")
    assert [s.tool for s in task.steps] == ["search_in_app"]
    assert task.steps[0].args == {"name": "Firefox", "query": "la météo à Paris"}


def test_local_plan_notepad_then_type(services):
    task = services.planner.plan("ouvre le bloc-notes puis écris bonjour")
    assert [s.tool for s in task.steps] == ["open_app", "type_text"]
    assert task.steps[1].args["window"] == "bloc-notes"
    assert task.steps[1].risk == "modification"


def _runner(services, updates=None):
    return TaskRunner(services.toolbox, services.planner, services.settings,
                      on_update=(updates.append if updates is not None else None))


def test_runner_confirmation_accepted(services):
    services.windows.windows.append({"title": "Sans titre - Bloc-notes", "process": "notepad.exe", "handle": 1})
    task = services.planner.plan("ouvre le bloc-notes puis écris bonjour")
    runner = _runner(services)
    t = threading.Thread(target=runner.run, args=(task,))
    t.start()
    for _ in range(50):
        if task.status == TaskStatus.WAITING:
            break
        time.sleep(0.02)
    assert task.status == TaskStatus.WAITING
    runner.confirm(True)
    t.join(3)
    assert task.status == TaskStatus.DONE
    assert services.windows.typed == ["bonjour"]
    assert all(s.status == StepStatus.DONE for s in task.steps)


def test_runner_refusal(services):
    task = services.planner.plan("ouvre le bloc-notes puis écris bonjour")
    runner = _runner(services)
    t = threading.Thread(target=runner.run, args=(task,))
    t.start()
    time.sleep(0.2)
    runner.confirm(False)
    t.join(3)
    assert task.steps[1].status == StepStatus.REFUSED
    assert services.windows.typed == []


def test_runner_stop_while_waiting(services):
    task = services.planner.plan("ouvre le bloc-notes puis écris bonjour")
    runner = _runner(services)
    t = threading.Thread(target=runner.run, args=(task,))
    t.start()
    time.sleep(0.2)
    runner.stop()
    t.join(3)
    assert task.status == TaskStatus.STOPPED
    assert task.steps[1].status == StepStatus.SKIPPED


def test_runner_pause_resume(services):
    task = Task(goal="test", steps=[services.planner.step("wait", {"seconds": 0}),
                                    services.planner.step("list_windows", {})])
    runner = _runner(services)
    runner.pause()
    t = threading.Thread(target=runner.run, args=(task,))
    t.start()
    time.sleep(0.3)
    assert task.steps[0].status == StepStatus.PENDING
    runner.resume()
    t.join(3)
    assert task.status == TaskStatus.DONE


def test_runner_budget(services):
    services.settings.max_steps = 2
    task = Task(goal="b", steps=[services.planner.step("wait", {"seconds": 0}) for _ in range(4)])
    _runner(services).run(task)
    assert task.status == TaskStatus.BUDGET
    assert [s.status for s in task.steps].count(StepStatus.DONE) == 2


def test_runner_failure_reported(services):
    updates = []
    task = Task(goal="ouvre x", steps=[services.planner.step("open_app", {"name": "Inconnu"})])
    _runner(services, updates).run(task)
    assert task.status == TaskStatus.FAILED
    assert "applications autorisées" in task.summary
    assert updates and updates[-1] is not task


def test_assistant_routes(services):
    a = Assistant(services)
    assert a.handle("ouvre Firefox", []).task.steps[0].tool == "open_app"
    assert a.handle("liste les fenêtres", []).task.steps[0].tool == "list_windows"
    assert a.handle("stop", []).kind == "stop"
    assert a.handle("quelle heure est-il", []).text.startswith("Il est")
    assert a.handle("bonjour, ça va ?", []).text == "réponse"
    assert a.handle("ouvre Firefox et recherche la météo", []).kind == "task"


def test_search_read_flow(services):
    out = services.toolbox.run("web_search", {"query": "météo"})
    assert "1. Météo Paris" in out
    assert "Météo Paris" in services.toolbox.run("open_result", {"index": 1})
    assert "Soleil" in services.toolbox.run("read_page", {})
