import json

from eliot.agent_workflows.models import Task
from eliot.agent_workflows.planner import Planner
from eliot.config import Settings
from eliot.history import History
from eliot.llm.engine import LLMEngine, clean_messages, extract_json
from eliot.web.browser import BrowserService, ddg_target, normalize_url


class ScriptedLLM:
    is_demo = False

    def __init__(self, replies):
        self.replies = list(replies)

    def complete_json(self, prompt, system, max_tokens=0):
        return self.replies.pop(0)

    def chat(self, messages, system=None, on_delta=None, max_tokens=0):
        return "Compte rendu."


def test_llm_plan_is_validated(services):
    llm = ScriptedLLM([{"steps": [
        {"tool": "open_app", "args": {"name": "Cursor"}, "description": "Ouvrir Cursor"},
        {"tool": "format_disk", "args": {}},
        {"tool": "list_folder", "args": {"folder": "zone"}},
    ]}])
    planner = Planner(services.toolbox, llm, services.settings, services.registry)
    task = planner.plan("ouvre cursor et montre mes fichiers")
    assert [s.tool for s in task.steps] == ["open_app", "list_folder"]
    assert task.steps[0].description == "Ouvrir Cursor"


def test_adaptive_decisions(services):
    llm = ScriptedLLM([{"decision": "add", "steps": [{"tool": "wait", "args": {"seconds": 0}}]},
                       {"decision": "finish", "summary": "Objectif atteint."}])
    planner = Planner(services.toolbox, llm, services.settings, services.registry)
    task = Task(goal="g")
    assert planner.decide(task)["steps"][0].tool == "wait"
    assert planner.decide(task) == {"decision": "finish", "summary": "Objectif atteint."}


def test_extract_json():
    assert extract_json('Voici : {"steps": []} fin') == {"steps": []}


def test_clean_messages():
    msgs = clean_messages([{"role": "assistant", "content": "salut"}, {"role": "user", "content": "a"},
                           {"role": "user", "content": "b"}, {"role": "assistant", "content": ""}])
    assert msgs == [{"role": "user", "content": "a\n\nb"}]


def test_demo_engine(tmp_path):
    s = Settings.load(tmp_path / "s.json")
    s.ai_provider = "demo"
    assert "démonstration" in LLMEngine(s).chat([{"role": "user", "content": "hello"}])


def test_anthropic_without_key(tmp_path):
    s = Settings.load(tmp_path / "s.json")
    s.ai_provider = "anthropic"
    engine = LLMEngine(s, secret_getter=lambda name: None)
    try:
        engine.chat([{"role": "user", "content": "hello"}])
    except Exception as exc:
        assert "Anthropic" in str(exc)
    else:
        raise AssertionError("une erreur était attendue")


def test_settings_roundtrip(tmp_path):
    s = Settings.load(tmp_path / "s.json")
    s.user_name = "Léa"
    s.save()
    data = json.loads((tmp_path / "s.json").read_text(encoding="utf-8"))
    assert data["user_name"] == "Léa" and "path" not in data
    assert Settings.load(tmp_path / "s.json").user_name == "Léa"


def test_history(tmp_path):
    h = History(tmp_path / "h.db")
    cid = h.new_conversation("Test")
    h.add_message(cid, "user", "Bonjour")
    h.add_message(cid, "assistant", "Salut")
    assert [m["role"] for m in h.messages(cid)] == ["user", "assistant"]
    assert h.conversations()[0]["title"] == "Test"
    h.log_action("tâche", "x", "terminée")
    assert h.actions()[0]["status"] == "terminée"
    h.delete_conversation(cid)
    assert h.conversations() == []


def test_browser_domains(tmp_path):
    s = Settings.load(tmp_path / "s.json")
    b = BrowserService(s, tmp_path / "p")
    assert b.domain_allowed("https://fr.wikipedia.org/wiki/Paris")
    assert not b.domain_allowed("https://evil-wikipedia.org")
    s.allow_all_domains = True
    assert b.domain_allowed("https://nimporte.quoi")
    b.shutdown()
    assert normalize_url("lemonde.fr") == "https://lemonde.fr"
    assert ddg_target("//duckduckgo.com/l/?uddg=https%3A%2F%2Fexemple.fr%2Fa&rut=x") == "https://exemple.fr/a"
