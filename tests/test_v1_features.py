import email
from datetime import datetime
from email.policy import default as default_policy

import pytest

from eliot.assistant import Assistant
from eliot.commands.router import clean, parse
from eliot.mail.accounts import GmailAccount, Mail, html_to_text
from eliot.mail.service import MailService
from eliot.scheduler import ScheduleError, Scheduler, describe, parse_schedule
from eliot.voice.wakeword import command_after_wake, is_wake

NOW = datetime(2026, 11, 21, 10, 30)  # samedi


def sched(text):
    orig, low = clean(text)
    return parse_schedule(orig, low, NOW)


@pytest.mark.parametrize("text,kind,target", [
    ("consulte mes nouveaux e-mails", "check_emails", ""),
    ("ai-je des nouveaux mails ?", "check_emails", ""),
    ("lis mes mails sur Gmail", "check_emails", "Gmail"),
    ("lis le mail 2", "read_email", "2"),
    ("prépare les réponses", "prepare_replies", ""),
    ("envoie la réponse 3", "send_reply", "3"),
    ("enregistre les réponses en brouillons", "save_drafts", ""),
    ("retiens que je préfère Firefox", "remember", "je préfère Firefox"),
    ("oublie que je préfère Firefox", "forget", "je préfère Firefox"),
    ("que sais-tu sur moi ?", "list_memory", ""),
    ("rappelle-moi d'appeler Paul demain à 15h", "schedule", ""),
    ("chaque matin à 9h, résume mes e-mails", "schedule", ""),
    ("liste mes rappels", "list_schedules", ""),
    ("supprime le rappel 2", "delete_schedule", "2"),
    ("analyse le projet site", "analyze_project", "site"),
    ("ouvre mon projet site dans Cursor", "open_in_app", "Cursor"),
    ("prépare une publication LinkedIn avec son visuel", "task", ""),
])
def test_new_intents(text, kind, target):
    intent = parse(text)
    assert intent.kind == kind
    if target:
        assert intent.target == target


def test_email_and_reply_is_task():
    assert parse("Eliot, consulte mes nouveaux e-mails et prépare les réponses").kind == "task"


def test_schedule_reminder_tomorrow():
    d = sched("rappelle-moi d'appeler Paul demain à 15h")
    assert d["kind"] == "reminder" and d["text"] == "appeler Paul"
    assert d["when"] == datetime(2026, 11, 22, 15, 0)


def test_schedule_relative():
    d = sched("rappelle-moi dans 10 minutes de sortir le gâteau")
    assert d["text"] == "sortir le gâteau" and d["when"] == datetime(2026, 11, 21, 10, 40)
    assert sched("rappelle-moi dans une demi-heure de partir")["when"] == datetime(2026, 11, 21, 11, 0)


def test_schedule_daily_task():
    d = sched("chaque matin à 9h, résume mes e-mails")
    assert d["kind"] == "task" and d["text"] == "résume mes e-mails" and d["recurrence"] == "daily"
    assert d["when"] == datetime(2026, 11, 22, 9, 0)


def test_schedule_weekly_and_weekdays():
    d = sched("tous les lundis à 8h30 range le dossier Téléchargements")
    assert d["recurrence"] == "weekly" and d["weekday"] == 0 and d["when"] == datetime(2026, 11, 23, 8, 30)
    assert d["text"] == "range le dossier Téléchargements"
    w = sched("programme du lundi au vendredi à 18h : consulte mes e-mails")
    assert w["recurrence"] == "weekdays" and w["when"] == datetime(2026, 11, 23, 18, 0)


def test_schedule_today_passed_moves_tomorrow():
    assert sched("rappelle-moi à 9h de boire de l'eau")["when"] == datetime(2026, 11, 22, 9, 0)
    assert sched("rappelle-moi à midi de manger")["when"] == datetime(2026, 11, 21, 12, 0)


def test_schedule_errors():
    with pytest.raises(ScheduleError):
        sched("rappelle-moi d'appeler Paul")


def test_scheduler_store(tmp_path):
    s = Scheduler(tmp_path / "s.json")
    once = s.add("reminder", "a", datetime(2026, 11, 21, 10, 0))
    daily = s.add("task", "b", datetime(2026, 11, 21, 9, 0), "daily", -1, 9, 0)
    due = s.pop_due(NOW)
    assert {d.id for d in due} == {once.id, daily.id}
    again = Scheduler(tmp_path / "s.json")
    assert [i.id for i in again.items] == [daily.id]
    assert again.items[0].when == datetime(2026, 11, 22, 9, 0)
    assert "tous les jours à 9 h 00" in describe(again.items[0])
    assert again.remove(daily.id) and not again.items


def test_memory_in_assistant_and_prompt(services):
    a = Assistant(services)
    assert "noté" in a.handle("retiens que je préfère Firefox", []).text
    assert "Firefox" in a.handle("que sais-tu sur moi ?", []).text
    assert "je préfère Firefox" in services.memory.as_prompt()
    assert "1 information" in a.handle("oublie que je préfère Firefox", []).text
    assert services.memory.all() == []


def test_schedule_in_assistant(services):
    a = Assistant(services)
    out = a.handle("rappelle-moi dans 5 minutes de vérifier le four", []).text
    assert out.startswith("C'est programmé") and services.scheduler.items[0].text == "vérifier le four"
    assert "n°1" in a.handle("liste mes rappels", []).text
    assert "supprimé" in a.handle("supprime le rappel 1", []).text


def test_wake_word():
    assert is_wake("Hey Eliot") and is_wake("Elliot, ouvre Firefox") and is_wake("Élio !")
    assert not is_wake("Le lion dort ce soir") and not is_wake("J'ai lu un livre")
    assert command_after_wake("Hey Eliot, ouvre Firefox.") == "ouvre Firefox"
    assert command_after_wake("Eliot.") == ""


class FakeAccount:
    name = "Outlook"

    def __init__(self):
        self.sent, self.saved = [], []

    def unread(self, limit):
        return [Mail("outlook", "A1", "Paul", "paul@x.fr", "Réunion lundi", "2026-11-21 09:00", "Es-tu dispo lundi ?"),
                Mail("outlook", "A2", "Promo", "news@shop.fr", "-50 %", "2026-11-20 08:00", "Soldes !")]

    def send_reply(self, mail, text):
        self.sent.append((mail.uid, text))

    def save_draft(self, mail, text):
        self.saved.append((mail.uid, text))


class ReplyLLM:
    is_demo = False

    def complete_json(self, prompt, system, max_tokens=0):
        assert "Réunion lundi" in prompt
        return {"replies": [{"index": 1, "needs_reply": True, "reply": "Oui, je suis disponible lundi."},
                            {"index": 2, "needs_reply": False, "reply": ""}]}


def test_mail_flow(services, monkeypatch):
    account = FakeAccount()
    monkeypatch.setattr(MailService, "accounts", lambda self, which="": [account])
    services.llm = ReplyLLM()
    tb = services.toolbox
    assert "2 e-mail(s)" in tb.run("check_emails", {})
    assert "Es-tu dispo" in tb.run("read_email", {"index": 1})
    out = tb.run("prepare_replies", {})
    assert "Réponse n°1 à Paul" in out and "n°2" not in out
    assert tb.tools["send_reply"].risk == "modification"
    assert "1 réponse(s)" in tb.run("save_drafts", {})
    assert "Réponse envoyée à Paul" in tb.run("send_reply", {"index": 1})
    assert account.sent == [("A1", "Oui, je suis disponible lundi.")]


def test_mail_not_configured(services):
    services.settings.outlook_enabled = False
    services.settings.gmail_address = ""
    from eliot.agent_workflows.tools import ToolError
    with pytest.raises(ToolError):
        services.toolbox.run("check_emails", {})


def test_gmail_parse_and_reply():
    raw = (b"From: Paul Martin <paul@exemple.fr>\r\nSubject: =?utf-8?q?R=C3=A9union?=\r\n"
           b"Message-ID: <abc@exemple.fr>\r\nDate: Fri, 20 Nov 2026 09:00:00 +0100\r\n"
           b"Content-Type: text/html; charset=utf-8\r\n\r\n<p>Bonjour<br>Dispo&nbsp;lundi ?</p>")
    acc = GmailAccount("moi@gmail.com", lambda: "abcd efgh")
    mail = acc._parse("7", email.message_from_bytes(raw, policy=default_policy))
    assert mail.sender == "Paul Martin" and mail.subject == "Réunion" and "Dispo" in mail.body
    reply = acc.build_reply(mail, "Oui !")
    assert reply["Subject"] == "Re: Réunion" and reply["In-Reply-To"] == "<abc@exemple.fr>"
    assert reply["To"] == "paul@exemple.fr"
    assert "Bonjour" in html_to_text("<div>Bonjour</div><script>x</script>")


def test_analyze_project(services, tmp_path):
    proj = tmp_path / "zone" / "monprojet"
    (proj / "tests").mkdir(parents=True)
    (proj / "calc.py").write_text("def add(a, b):\n    return a - b\n")
    (proj / "tests" / "test_calc.py").write_text(
        "import sys, os\nsys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))\n"
        "from calc import add\n\ndef test_add():\n    assert add(2, 2) == 4\n")
    out = services.toolbox.run("analyze_project", {"folder": "monprojet"})
    assert "des erreurs ont été détectées" in out and "test_add" in out
    assert "return a - b" in services.toolbox.run("read_file", {"path": str(proj / "calc.py")})
    (proj / "calc.py").write_text("def add(a, b):\n    return a + b\n")
    assert "aucune erreur" in services.toolbox.run("analyze_project", {"folder": str(proj)})


def test_read_file_outside_refused(services, tmp_path):
    from eliot.agent_workflows.tools import ToolError
    secret = tmp_path / "secret.txt"
    secret.write_text("x")
    with pytest.raises(ToolError):
        services.toolbox.run("read_file", {"path": str(secret)})
