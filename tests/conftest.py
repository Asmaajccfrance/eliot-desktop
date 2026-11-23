import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(autouse=True)
def eliot_home(tmp_path, monkeypatch):
    monkeypatch.setenv("ELIOT_HOME", str(tmp_path / "home"))
    return tmp_path / "home"


class FakeWindows:
    def __init__(self, windows=None, fg=None):
        self.windows = windows or []
        self.fg = fg or {"title": "Sans titre - Bloc-notes", "process": "notepad.exe", "handle": 1}
        self.typed = []
        self.keys = []
        self.activated = []

    def list_windows(self):
        return list(self.windows)

    def find(self, pattern="", process_names=None):
        procs = {p.lower() for p in process_names or []}
        for w in self.windows:
            if w["process"].lower() in procs or (pattern and pattern.split("|")[0].lower() in w["title"].lower()):
                return w
        return None

    def activate(self, pattern="", process_names=None):
        info = self.find(pattern, process_names)
        if info:
            self.activated.append(info["title"])
        return info

    def foreground(self):
        return self.fg

    def type_text(self, text):
        self.typed.append(text)

    def press_keys(self, combo):
        from eliot.windows.keys import to_send_keys
        self.keys.append(to_send_keys(combo))

    def click_element(self, handle, name):
        return name

    def click_at(self, x, y):
        pass


class FakeLauncher:
    def __init__(self, running=()):
        self.running = set(running)
        self.opened = []

    def is_running(self, app):
        return app.key in self.running

    def open(self, app):
        self.opened.append(app.key)
        return f"J'ouvre {app.name}."

    def open_with(self, app, target):
        self.opened.append((app.key, target))
        return f"J'ai ouvert {target} dans {app.name}."

    def close(self, app):
        return f"J'ai fermé {app.name}."


class FakeBrowser:
    def __init__(self):
        self.last_results = []

    def search(self, q):
        self.last_results = [{"title": "Météo Paris", "url": "https://meteo.example/paris"}]
        return self.last_results

    def open(self, url, trusted=False):
        return "Page test"

    def open_result(self, i):
        return self.last_results[i - 1]["url"], "Météo Paris"

    def read(self):
        return {"title": "Météo Paris", "url": "https://meteo.example/paris", "text": "Soleil, 21 °C."}

    def shutdown(self):
        pass


class FakeLLM:
    is_demo = True

    def chat(self, messages, system=None, on_delta=None, max_tokens=0):
        return "réponse"


@pytest.fixture
def services(tmp_path):
    from eliot.config import Settings
    from eliot.services import build_services
    settings = Settings.load(tmp_path / "settings.json")
    settings.ai_provider = "demo"
    settings.wake_word = False
    settings.keep_in_tray = False
    settings.allowed_folders = [str(tmp_path / "zone")]
    (tmp_path / "zone").mkdir()
    return build_services(settings, windows=FakeWindows(), launcher=FakeLauncher(), browser=FakeBrowser(),
                          llm=FakeLLM())
