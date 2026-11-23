from dataclasses import dataclass, field
from datetime import datetime

READ = "lecture"
ACT = "action"
MODIFY = "modification"


class StepStatus:
    PENDING = "en attente"
    WAITING = "à confirmer"
    RUNNING = "en cours"
    DONE = "terminée"
    FAILED = "échec"
    REFUSED = "refusée"
    SKIPPED = "ignorée"


class TaskStatus:
    PLANNED = "planifiée"
    RUNNING = "en cours"
    WAITING = "en attente de confirmation"
    PAUSED = "en pause"
    DONE = "terminée"
    FAILED = "échouée"
    STOPPED = "arrêtée"
    BUDGET = "budget atteint"


FINAL = {TaskStatus.DONE, TaskStatus.FAILED, TaskStatus.STOPPED, TaskStatus.BUDGET}


@dataclass
class Step:
    tool: str
    args: dict
    description: str
    risk: str = READ
    status: str = StepStatus.PENDING
    result: str = ""


@dataclass
class Task:
    goal: str
    steps: list = field(default_factory=list)
    status: str = TaskStatus.PLANNED
    summary: str = ""
    log: list = field(default_factory=list)

    def note(self, text: str) -> None:
        self.log.append(f"{datetime.now().strftime('%H:%M:%S')}  {text}")

    @property
    def current(self):
        return next((s for s in self.steps if s.status in (StepStatus.WAITING, StepStatus.RUNNING)), None)
