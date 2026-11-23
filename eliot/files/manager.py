"""Accès aux dossiers autorisés : lister, ranger par catégorie, annuler."""
import json
import os
import shutil
import sys
from pathlib import Path

from ..text import simplify

CATEGORIES = {
    "Images": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg", ".heic", ".tif", ".tiff", ".ico"},
    "Documents": {".pdf", ".doc", ".docx", ".odt", ".txt", ".rtf", ".md"},
    "Tableurs": {".xls", ".xlsx", ".ods", ".csv"},
    "Présentations": {".ppt", ".pptx", ".odp", ".key"},
    "Archives": {".zip", ".rar", ".7z", ".tar", ".gz"},
    "Audio": {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac"},
    "Vidéos": {".mp4", ".mov", ".avi", ".mkv", ".webm", ".wmv"},
    "Code": {".py", ".js", ".ts", ".html", ".css", ".json", ".xml", ".java", ".c", ".cpp", ".cs", ".php", ".sql"},
    "Installateurs": {".exe", ".msi", ".bat", ".cmd"},
}
ALIASES = {
    "bureau": ["Desktop", "Bureau", "OneDrive/Desktop", "OneDrive/Bureau"],
    "documents": ["Documents", "OneDrive/Documents"],
    "mes documents": ["Documents", "OneDrive/Documents"],
    "telechargements": ["Downloads", "Téléchargements"],
    "telechargement": ["Downloads", "Téléchargements"],
    "downloads": ["Downloads"],
    "images": ["Pictures", "Images", "OneDrive/Pictures"],
    "photos": ["Pictures", "Images"],
    "musique": ["Music", "Musique"],
    "videos": ["Videos", "Vidéos"],
}


class FileAccessError(Exception):
    pass


def category_of(path: Path) -> str:
    ext = path.suffix.lower()
    return next((cat for cat, exts in CATEGORIES.items() if ext in exts), "Autres")


class FileManager:
    def __init__(self, settings, undo_path):
        self.settings = settings
        self.undo_path = Path(undo_path)

    def allowed_roots(self) -> list:
        return [Path(p).expanduser().resolve() for p in self.settings.allowed_folders if p]

    def is_allowed(self, path: Path) -> bool:
        path = Path(path).resolve()
        for root in self.allowed_roots():
            try:
                path.relative_to(root)
                return True
            except ValueError:
                continue
        return False

    def resolve(self, name: str) -> Path:
        raw = (name or "").strip().strip("\"'«» ")
        key = simplify(raw)
        candidates = []
        if key in ALIASES:
            candidates = [Path.home() / rel for rel in ALIASES[key]]
        elif os.path.isabs(os.path.expandvars(raw)):
            candidates = [Path(os.path.expandvars(raw))]
        else:
            for root in self.allowed_roots():
                candidates.append(root / raw)
                if simplify(root.name) == key:
                    candidates.insert(0, root)
        path = next((c for c in candidates if c.is_dir()), None)
        if path is None:
            raise FileAccessError(f"Je ne trouve pas le dossier « {raw} ».")
        if not self.is_allowed(path):
            raise FileAccessError(f"Le dossier « {path} » n'est pas autorisé. Ajoute-le dans « Dossiers autorisés ».")
        return path.resolve()

    def list(self, name: str) -> tuple:
        path = self.resolve(name)
        entries = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        return path, [p for p in entries if not p.name.startswith(".")]

    def plan_organize(self, name: str) -> tuple:
        path = self.resolve(name)
        plan = []
        taken = set()
        for item in sorted(path.iterdir()):
            if not item.is_file() or item.name.startswith(".") or item.name.lower() == "desktop.ini":
                continue
            dest_dir = path / category_of(item)
            dest = dest_dir / item.name
            stem, n = item.stem, 2
            while dest.exists() or str(dest) in taken:
                dest = dest_dir / f"{stem} ({n}){item.suffix}"
                n += 1
            taken.add(str(dest))
            plan.append((str(item), str(dest)))
        return path, plan

    def apply(self, plan: list) -> int:
        done = []
        for src, dst in plan:
            Path(dst).parent.mkdir(parents=True, exist_ok=True)
            shutil.move(src, dst)
            done.append([src, dst])
        self.undo_path.write_text(json.dumps(done, ensure_ascii=False, indent=1), encoding="utf-8")
        return len(done)

    def undo_last(self) -> int:
        if not self.undo_path.exists():
            return 0
        moves = json.loads(self.undo_path.read_text(encoding="utf-8"))
        restored = 0
        for src, dst in reversed(moves):
            if Path(dst).exists() and not Path(src).exists():
                shutil.move(dst, src)
                restored += 1
                parent = Path(dst).parent
                if parent.exists() and not any(parent.iterdir()):
                    parent.rmdir()
        self.undo_path.unlink()
        return restored

    def open_in_explorer(self, name: str) -> Path:
        path = self.resolve(name)
        if sys.platform != "win32":
            raise FileAccessError("L'Explorateur n'est disponible que sous Windows.")
        os.startfile(str(path))
        return path
