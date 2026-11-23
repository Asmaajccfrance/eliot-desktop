"""Gestionnaire des applications autorisées."""
import difflib
import json
import ntpath
import os
import shutil
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

from ..text import simplify


@dataclass
class AllowedApp:
    key: str
    name: str
    aliases: list = field(default_factory=list)
    launch: str = ""
    exe: str = ""
    process_names: list = field(default_factory=list)
    window_pattern: str = ""
    category: str = "Autre"
    enabled: bool = True
    allow_control: bool = False

    def command(self) -> str:
        if self.exe and Path(self.exe).exists():
            return self.exe
        return self.launch or self.exe

    @property
    def is_browser(self) -> bool:
        return self.category == "Navigateur"


_DEFAULTS = [
    ("notepad", "Bloc-notes", ["bloc notes", "blocnote", "blocnotes", "bloc note", "notepad"], "notepad.exe",
     ["notepad.exe"], "Bloc-notes", "Outils", True),
    ("calculator", "Calculatrice", ["calculatrice", "calc", "calculette"], "calc.exe",
     ["calculatorapp.exe", "calc.exe"], "Calculatrice", "Outils", True),
    ("paint", "Paint", ["paint", "mspaint"], "mspaint.exe", ["mspaint.exe"], "Paint", "Outils", True),
    ("explorer", "Explorateur de fichiers", ["explorateur", "explorateur de fichiers", "explorer", "fichiers"],
     "explorer.exe", ["explorer.exe"], "Explorateur", "Outils", False),
    ("firefox", "Firefox", ["firefox", "mozilla", "mozilla firefox"], "firefox.exe", ["firefox.exe"],
     "Firefox", "Navigateur", True),
    ("chrome", "Google Chrome", ["chrome", "google chrome"], "chrome.exe", ["chrome.exe"], "Chrome",
     "Navigateur", True),
    ("edge", "Microsoft Edge", ["edge", "microsoft edge"], "msedge.exe", ["msedge.exe"], "Edge", "Navigateur", True),
    ("cursor", "Cursor", ["cursor"], "", ["cursor.exe"], "Cursor", "Développement", False),
    ("vscode", "Visual Studio Code", ["vs code", "vscode", "visual studio code", "code"], "code",
     ["code.exe"], "Visual Studio Code", "Développement", False),
    ("terminal", "Terminal Windows", ["terminal", "invite de commandes", "powershell", "console"], "wt.exe",
     ["windowsterminal.exe", "wt.exe"], "Terminal", "Développement", False),
    ("word", "Microsoft Word", ["word", "microsoft word"], "winword.exe", ["winword.exe"], "Word",
     "Bureautique", True),
    ("excel", "Microsoft Excel", ["excel", "microsoft excel"], "excel.exe", ["excel.exe"], "Excel",
     "Bureautique", True),
    ("outlook", "Outlook", ["outlook", "messagerie"], "outlook.exe", ["outlook.exe", "olk.exe"], "Outlook",
     "Bureautique", False),
    ("photoshop", "Adobe Photoshop", ["photoshop"], "photoshop.exe", ["photoshop.exe"], "Photoshop",
     "Création", False),
]

_CANDIDATES = {
    "firefox": [r"%ProgramFiles%\Mozilla Firefox\firefox.exe", r"%ProgramFiles(x86)%\Mozilla Firefox\firefox.exe"],
    "chrome": [r"%ProgramFiles%\Google\Chrome\Application\chrome.exe",
               r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"],
    "edge": [r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"],
    "cursor": [r"%LOCALAPPDATA%\Programs\cursor\Cursor.exe", r"%LOCALAPPDATA%\Programs\Cursor\Cursor.exe"],
    "vscode": [r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe", r"%ProgramFiles%\Microsoft VS Code\Code.exe"],
    "word": [r"%ProgramFiles%\Microsoft Office\root\Office16\WINWORD.EXE",
             r"%ProgramFiles(x86)%\Microsoft Office\root\Office16\WINWORD.EXE"],
    "excel": [r"%ProgramFiles%\Microsoft Office\root\Office16\EXCEL.EXE",
              r"%ProgramFiles(x86)%\Microsoft Office\root\Office16\EXCEL.EXE"],
    "outlook": [r"%ProgramFiles%\Microsoft Office\root\Office16\OUTLOOK.EXE"],
    "photoshop": [r"%ProgramFiles%\Adobe\Adobe Photoshop 2026\Photoshop.exe",
                  r"%ProgramFiles%\Adobe\Adobe Photoshop 2025\Photoshop.exe",
                  r"%ProgramFiles%\Adobe\Adobe Photoshop 2024\Photoshop.exe"],
}


def default_apps() -> list:
    return [AllowedApp(key=k, name=n, aliases=a, launch=l, process_names=p, window_pattern=w, category=c,
                       allow_control=ctrl) for k, n, a, l, p, w, c, ctrl in _DEFAULTS]


class AppRegistry:
    def __init__(self, path):
        self.path = Path(path)
        self.apps = self._load()

    def _load(self) -> list:
        if self.path.exists():
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
                known = {f.name for f in fields(AllowedApp)}
                return [AllowedApp(**{k: v for k, v in item.items() if k in known}) for item in raw]
            except (ValueError, OSError, TypeError):
                pass
        return default_apps()

    def save(self) -> None:
        self.path.write_text(json.dumps([asdict(a) for a in self.apps], indent=2, ensure_ascii=False),
                             encoding="utf-8")

    def enabled(self) -> list:
        return [a for a in self.apps if a.enabled]

    def get(self, key: str):
        return next((a for a in self.apps if a.key == key), None)

    def find(self, query: str, include_disabled: bool = True):
        raw = simplify(query)
        q = " ".join(w for w in raw.split() if w not in {"le", "la", "les", "l", "mon", "ma", "application", "logiciel",
                                                         "appli", "fenetre", "de", "du", "d"})
        if not q:
            return None
        pool = self.apps if include_disabled else self.enabled()
        names = {}
        for app in pool:
            for label in [app.key, app.name, *app.aliases]:
                names.setdefault(simplify(label), app)
        for candidate in (raw, q):
            if candidate in names:
                return names[candidate]
        for label, app in sorted(names.items(), key=lambda kv: -len(kv[0])):
            if f" {label} " in f" {q} ":
                return app
        close = difflib.get_close_matches(q, list(names), n=1, cutoff=0.75)
        return names[close[0]] if close else None

    def add(self, name: str, command: str, category: str = "Autre", allow_control: bool = False) -> AllowedApp:
        base = simplify(name).replace(" ", "_") or "app"
        key, i = base, 2
        while self.get(key):
            key, i = f"{base}_{i}", i + 1
        exe_name = ntpath.basename(command).lower()
        absolute = ntpath.isabs(command) or os.path.isabs(command)
        app = AllowedApp(key=key, name=name, aliases=[simplify(name)], exe=command if absolute else "",
                         launch="" if absolute else command,
                         process_names=[exe_name] if exe_name.endswith(".exe") else [],
                         window_pattern=name, category=category, allow_control=allow_control)
        self.apps.append(app)
        return app

    def remove(self, key: str) -> None:
        self.apps = [a for a in self.apps if a.key != key]

    def autodetect(self) -> list:
        found = []
        for app in self.apps:
            for template in _CANDIDATES.get(app.key, []):
                path = os.path.expandvars(template)
                if "%" not in path and Path(path).exists():
                    app.exe = path
                    found.append(app.name)
                    break
            else:
                if not app.exe and app.launch and shutil.which(app.launch):
                    found.append(app.name)
        return found
