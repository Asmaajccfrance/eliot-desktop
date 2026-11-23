"""Exécution supervisée : confirmations, pause, reprise, STOP et budgets."""
import copy
import threading
import time

from .models import FINAL, MODIFY, ACT, StepStatus, TaskStatus
from .planner import local_report


class TaskRunner:
    def __init__(self, toolbox, planner, settings, on_update=None):
        self.toolbox = toolbox
        self.planner = planner
        self.settings = settings
        self.on_update = on_update
        self.task = None
        self._running = threading.Event()
        self._running.set()
        self._stop = threading.Event()
        self._answer = None
        self._answered = threading.Event()

    def needs_confirmation(self, step) -> bool:
        return step.risk == MODIFY or (self.settings.confirm_actions and step.risk == ACT)

    def _emit(self):
        if self.on_update and self.task is not None:
            try:
                self.on_update(copy.deepcopy(self.task))
            except RuntimeError:
                self.on_update = None

    def confirm(self, ok: bool) -> None:
        self._answer = bool(ok)
        self._answered.set()

    def pause(self) -> None:
        self._running.clear()
        if self.task and self.task.status not in FINAL:
            self.task.status = TaskStatus.PAUSED
            self.task.note("Pause demandée.")
            self._emit()

    def resume(self) -> None:
        if self.task and self.task.status == TaskStatus.PAUSED:
            self.task.status = TaskStatus.RUNNING
            self.task.note("Reprise.")
        self._running.set()
        self._emit()

    def stop(self) -> None:
        self._stop.set()
        self._running.set()
        self._answered.set()

    @property
    def stopped(self) -> bool:
        return self._stop.is_set()

    def _wait_if_paused(self) -> None:
        while not self._running.wait(0.2):
            if self.stopped:
                return

    def _ask(self, step) -> bool:
        step.status = StepStatus.WAITING
        self.task.status = TaskStatus.WAITING
        self.task.note(f"Confirmation demandée : {step.description}")
        self._answer = None
        self._answered.clear()
        self._emit()
        self._answered.wait()
        return bool(self._answer) and not self.stopped

    def run(self, task):
        self.task = task
        task.status = TaskStatus.RUNNING
        task.note(f"Début : {task.goal}")
        self._emit()
        started, executed, i = time.monotonic(), 0, 0
        while i < len(task.steps):
            self._wait_if_paused()
            if self.stopped:
                break
            step = task.steps[i]
            if executed >= self.settings.max_steps or time.monotonic() - started > self.settings.max_task_seconds:
                task.status = TaskStatus.BUDGET
                task.note("Budget de la tâche atteint, arrêt par sécurité.")
                break
            if self.needs_confirmation(step) and not self._ask(step):
                if self.stopped:
                    break
                step.status = StepStatus.REFUSED
                task.status = TaskStatus.RUNNING
                task.note(f"Refusée : {step.description}")
                self._emit()
                i += 1
                continue
            step.status = StepStatus.RUNNING
            task.status = TaskStatus.RUNNING
            task.note(f"Exécution : {step.description}")
            self._emit()
            try:
                step.result = self.toolbox.run(step.tool, step.args) or ""
                step.status = StepStatus.DONE
                task.note(f"Terminée : {step.description}")
            except Exception as exc:
                step.result = str(exc) or exc.__class__.__name__
                step.status = StepStatus.FAILED
                task.note(f"Échec : {step.result}")
            executed += 1
            self._emit()
            if self.stopped:
                break
            if self.planner is not None and len(task.steps) > 1:
                decision = self.planner.decide(task)
                if decision["decision"] == "finish":
                    task.summary = decision.get("summary", "")
                    task.note("Le superviseur IA a jugé l'objectif terminé.")
                    i = len(task.steps)
                    break
                if decision["decision"] == "add" and decision.get("steps"):
                    room = max(0, self.settings.max_steps - len(task.steps))
                    new = decision["steps"][:room]
                    task.steps[i + 1:i + 1] = new
                    if new:
                        task.note(f"{len(new)} étape(s) ajoutée(s) par le superviseur IA.")
                        self._emit()
            i += 1
        for step in task.steps:
            if step.status in (StepStatus.PENDING, StepStatus.WAITING):
                step.status = StepStatus.SKIPPED
        if self.stopped:
            task.status = TaskStatus.STOPPED
            task.note("Tâche arrêtée (STOP).")
        elif task.status != TaskStatus.BUDGET:
            ran = [s for s in task.steps if s.status in (StepStatus.DONE, StepStatus.FAILED)]
            task.status = TaskStatus.FAILED if ran and all(s.status == StepStatus.FAILED for s in ran) else TaskStatus.DONE
        if not task.summary:
            try:
                task.summary = self.planner.report(task) if self.planner and not self.stopped else local_report(task)
            except Exception:
                task.summary = local_report(task)
        task.note("Fin de la tâche.")
        self._emit()
        return task
