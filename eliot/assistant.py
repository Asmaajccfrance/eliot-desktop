"""Point d'entrée de la logique : comprend une demande et choisit réponse, action ou tâche."""
from dataclasses import dataclass
from datetime import datetime

from .agent_workflows.models import Task
from .commands import router
from .scheduler import ScheduleError, describe, parse_schedule

DAYS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MONTHS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
          "novembre", "décembre"]
HELP = ("Voici ce que je sais faire : ouvrir ou activer une application autorisée (« ouvre Firefox »), lister les "
        "fenêtres, écrire du texte (« écris bonjour dans le Bloc-notes »), envoyer un raccourci (« appuie sur ctrl s »), "
        "cliquer sur un bouton, rechercher sur Internet, ouvrir un résultat et lire la page, lister ou ranger un dossier "
        "autorisé, enchaîner plusieurs actions (« ouvre Firefox et recherche la météo »), consulter tes e-mails et "
        "préparer les réponses, retenir des informations (« retiens que… »), programmer des rappels (« rappelle-moi "
        "d'appeler Paul demain à 15h », « chaque matin à 9h, résume mes e-mails ») et analyser un projet de code. "
        "Dis « Hey Eliot » pour m'appeler. Pour tout le reste, je discute avec toi grâce à Claude.")


MEMORY_KINDS = {"remember", "forget", "list_memory"}
SCHEDULE_KINDS = {"schedule", "list_schedules", "delete_schedule"}


@dataclass
class Reply:
    text: str = ""
    task: Task = None
    kind: str = "chat"


class Assistant:
    def __init__(self, services):
        self.s = services

    def handle(self, text: str, history: list, on_delta=None) -> Reply:
        intent = router.parse(text)
        kind = intent.kind
        if kind == "stop":
            return Reply("D'accord, j'arrête tout.", kind="stop")
        if kind == "time":
            now = datetime.now()
            return Reply(f"Il est {now.hour} h {now.minute:02d}.", kind="info")
        if kind == "date":
            now = datetime.now()
            return Reply(f"Nous sommes le {DAYS[now.weekday()]} {now.day} {MONTHS[now.month - 1]} {now.year}.",
                         kind="info")
        if kind == "help":
            return Reply(HELP, kind="info")
        if kind == "list_apps":
            apps = self.s.registry.enabled()
            return Reply("Applications autorisées : " + ", ".join(a.name for a in apps) + ".", kind="info")
        if kind in MEMORY_KINDS:
            return Reply(self._memory(intent), kind="info")
        if kind in SCHEDULE_KINDS:
            return Reply(self._schedule(intent), kind="info")
        if kind == "task":
            task = self.s.planner.plan(intent.text)
            if task.steps:
                return Reply(f"J'ai préparé un plan en {len(task.steps)} étape(s).", task=task, kind="task")
        else:
            step = self.s.planner.from_intent(intent)
            if step is not None:
                return Reply(step.description + "…", task=Task(goal=text, steps=[step]), kind="action")
        return self._chat(text, history, on_delta)

    def _memory(self, intent) -> str:
        mem = self.s.memory
        if intent.kind == "remember":
            mem.add(intent.target)
            return f"C'est noté, je m'en souviendrai : {intent.target}."
        if intent.kind == "forget":
            n = mem.forget(intent.target)
            return f"J'ai oublié {n} information(s)." if n else "Je n'ai rien retenu de tel."
        items = mem.all()
        if not items:
            return "Je n'ai encore rien retenu. Dis-moi par exemple « retiens que je préfère Firefox »."
        return "Voici ce que je sais sur toi :\n" + "\n".join(f"• {i['content']}" for i in items)

    def _schedule(self, intent) -> str:
        sch = self.s.scheduler
        if intent.kind == "list_schedules":
            return ("Programmations :\n" + "\n".join(describe(i) for i in sch.items)) if sch.items else \
                "Aucun rappel ni tâche programmée."
        if intent.kind == "delete_schedule":
            return "C'est supprimé." if sch.remove(int(intent.target)) else f"Je ne trouve pas le n°{intent.target}."
        orig, low = router.clean(intent.text)
        try:
            data = parse_schedule(orig, low)
        except ScheduleError as exc:
            return str(exc)
        item = sch.add(data["kind"], data["text"], data["when"], data["recurrence"], data["weekday"], data["hour"],
                       data["minute"])
        return "C'est programmé : " + describe(item).split(" · ", 1)[1] + "."

    def _chat(self, text, history, on_delta) -> Reply:
        messages = list(history or [])
        if not messages or messages[-1].get("content") != text:
            messages.append({"role": "user", "content": text})
        return Reply(self.s.llm.chat(messages[-30:], on_delta=on_delta), kind="chat")
