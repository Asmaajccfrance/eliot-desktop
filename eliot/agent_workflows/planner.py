"""Planification (Claude ou locale) et décisions adaptatives après chaque étape."""
import json

from ..commands import router
from ..llm.engine import LLMError
from .models import Step, StepStatus, Task

PLAN_SYSTEM = """Tu es le module de planification d'ELIOT, un assistant qui agit sur un PC Windows.
Transforme la demande de l'utilisateur en étapes concrètes utilisant UNIQUEMENT ces outils :
{tools}

Applications autorisées : {apps}
Dossiers autorisés : {folders}

Réponds UNIQUEMENT avec un objet JSON : {{"steps": [{{"tool": "...", "args": {{...}}, "description": "..."}}]}}
Règles : au maximum {max_steps} étapes ; descriptions courtes en français ; si la demande ne nécessite aucune action
sur le PC (simple question), renvoie {{"steps": []}}. Pour rechercher dans Firefox/Chrome/Edge utilise search_in_app.
Pour lire puis résumer une page, utilise web_search, open_result puis read_page (le résumé sera fait à la fin).
Pour les e-mails : check_emails puis prepare_replies (jamais send_reply sans demande explicite d'envoi).
Pour un projet de code : open_in_app (Cursor) si demandé, analyze_project, puis read_file sur les fichiers en erreur ;
le compte rendu final expliquera les problèmes et proposera les corrections."""

DECIDE_SYSTEM = """Tu supervises l'exécution d'une tâche d'ELIOT. Après chaque étape, décide de la suite.
Outils disponibles :
{tools}
Réponds UNIQUEMENT en JSON, une des formes :
{{"decision": "continue"}}
{{"decision": "add", "steps": [{{"tool": "...", "args": {{...}}, "description": "..."}}]}}  (étapes insérées juste après)
{{"decision": "finish", "summary": "..."}}  (objectif atteint ou impossible, résumé en français)
Ajoute des étapes seulement si c'est nécessaire pour atteindre l'objectif (ex : corriger un échec)."""

REPORT_SYSTEM = """Tu es ELIOT. Rédige en français un compte rendu bref (3 à 8 phrases, lisible à voix haute, sans
markdown lourd) de la tâche exécutée : ce qui a été fait, les résultats utiles (résume le contenu lu s'il y en a),
les échecs éventuels et ce que l'utilisateur peut faire ensuite. N'invente rien.
Pour des e-mails : liste brièvement expéditeur et sujet, et signale les réponses préparées (« envoie la réponse 2 »).
Pour une analyse de code : identifie chaque problème (fichier, cause probable) et propose la correction précise."""

INTENT_TOOLS = {
    "open_app": ("open_app", lambda i: {"name": i.target}),
    "activate_window": ("activate_window", lambda i: {"title": i.target}),
    "list_windows": ("list_windows", lambda i: {}),
    "close_app": ("close_app", lambda i: {"name": i.target}),
    "web_search": ("web_search", lambda i: {"query": i.target}),
    "open_url": ("open_url", lambda i: {"url": i.target}),
    "open_result": ("open_result", lambda i: {"index": int(i.target or 1)}),
    "read_page": ("read_page", lambda i: {}),
    "list_folder": ("list_folder", lambda i: {"folder": i.target}),
    "open_folder": ("open_folder", lambda i: {"folder": i.target}),
    "organize_folder": ("organize_folder", lambda i: {"folder": i.target}),
    "undo": ("undo_organize", lambda i: {}),
    "type_text": ("type_text", lambda i: {"text": i.text, "window": i.target}),
    "press_keys": ("press_keys", lambda i: {"keys": i.target}),
    "click": ("click_element", lambda i: {"name": i.text, "window": i.target}),
    "check_emails": ("check_emails", lambda i: {"account": i.target}),
    "read_email": ("read_email", lambda i: {"index": int(i.target or 1)}),
    "prepare_replies": ("prepare_replies", lambda i: {"instructions": i.target.strip(" ,:")}),
    "send_reply": ("send_reply", lambda i: {"index": int(i.target or 1)}),
    "save_drafts": ("save_drafts", lambda i: {}),
    "analyze_project": ("analyze_project", lambda i: {"folder": i.target}),
    "open_in_app": ("open_in_app", lambda i: {"name": i.target, "target": i.text}),
}
SUMMARIZE = {"read_page", "check_emails", "read_email", "analyze_project", "read_file"}


def _task_state(task: Task) -> str:
    lines = [f"Objectif : {task.goal}"]
    for n, s in enumerate(task.steps, 1):
        result = (s.result or "")[:1500]
        lines.append(f"{n}. [{s.status}] {s.tool} {json.dumps(s.args, ensure_ascii=False)} -> {result}")
    return "\n".join(lines)


class Planner:
    def __init__(self, toolbox, llm, settings, registry=None):
        self.toolbox = toolbox
        self.llm = llm
        self.settings = settings
        self.registry = registry

    def step(self, tool: str, args: dict, description: str = "") -> Step:
        return Step(tool=tool, args=args, description=description or self.toolbox.describe_step(tool, args),
                    risk=self.toolbox.tools[tool].risk)

    def from_intent(self, intent):
        mapping = INTENT_TOOLS.get(intent.kind)
        if not mapping:
            return None
        tool, build = mapping
        return self.step(tool, build(intent))

    def validate(self, raw_steps) -> list:
        steps = []
        for item in raw_steps or []:
            if not isinstance(item, dict) or item.get("tool") not in self.toolbox.tools:
                continue
            args = item.get("args") if isinstance(item.get("args"), dict) else {}
            steps.append(self.step(item["tool"], args, str(item.get("description") or "")))
        return steps[: self.settings.max_steps]

    def plan(self, goal: str) -> Task:
        steps = []
        if not self.llm.is_demo:
            try:
                steps = self._llm_plan(goal)
            except LLMError:
                steps = []
        if not steps:
            steps = self.local_plan(goal)
        return Task(goal=goal, steps=steps)

    def _llm_plan(self, goal: str) -> list:
        apps = ", ".join(a.name for a in self.registry.enabled()) if self.registry else "?"
        system = PLAN_SYSTEM.format(tools=self.toolbox.describe_for_llm(), apps=apps,
                                    folders=", ".join(self.settings.allowed_folders), max_steps=self.settings.max_steps)
        return self.validate(self.llm.complete_json(goal, system).get("steps"))

    def local_plan(self, goal: str) -> list:
        intents = [router.parse(seg) for seg in router.split_segments(goal)]
        steps = []
        for idx, intent in enumerate(intents):
            prev = intents[idx - 1] if idx else None
            if intent.kind == "web_search" and prev and prev.kind == "open_app" and self.registry:
                app = self.registry.find(prev.target)
                if app is not None and app.is_browser and steps and steps[-1].tool == "open_app":
                    steps[-1] = self.step("search_in_app", {"name": prev.target, "query": intent.target})
                    continue
            if intent.kind == "type_text" and not intent.target and prev and prev.kind == "open_app":
                intent.target = prev.target
            step = self.from_intent(intent)
            if step:
                steps.append(step)
        return steps[: self.settings.max_steps]

    def decide(self, task: Task) -> dict:
        if self.llm.is_demo or not self.settings.adaptive_workflows:
            return {"decision": "continue"}
        try:
            data = self.llm.complete_json(_task_state(task), DECIDE_SYSTEM.format(tools=self.toolbox.describe_for_llm()),
                                          max_tokens=800)
        except LLMError:
            return {"decision": "continue"}
        decision = data.get("decision")
        if decision == "add":
            return {"decision": "add", "steps": self.validate(data.get("steps"))}
        if decision == "finish":
            return {"decision": "finish", "summary": str(data.get("summary") or "")}
        return {"decision": "continue"}

    def report(self, task: Task) -> str:
        worth = len(task.steps) > 1 or any(s.tool in SUMMARIZE for s in task.steps)
        if worth and not self.llm.is_demo and any(s.status == StepStatus.DONE for s in task.steps):
            try:
                return self.llm.chat([{"role": "user", "content": _task_state(task)}], system=REPORT_SYSTEM,
                                     max_tokens=600).strip()
            except LLMError:
                pass
        return local_report(task)


def local_report(task: Task) -> str:
    done = [s for s in task.steps if s.status == StepStatus.DONE]
    failed = [s for s in task.steps if s.status == StepStatus.FAILED]
    refused = [s for s in task.steps if s.status == StepStatus.REFUSED]
    if len(task.steps) == 1 and done:
        return done[0].result
    if len(task.steps) == 1 and failed:
        return failed[0].result
    parts = [f"Tâche {task.status} : {len(done)} étape(s) réussie(s) sur {len(task.steps)}."]
    parts += [f"Échec « {s.description} » : {s.result}" for s in failed]
    if refused:
        parts.append(f"{len(refused)} étape(s) refusée(s).")
    if done and done[-1].result:
        parts.append(done[-1].result[:600])
    return "\n".join(parts)
