import json
import os
import sys
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

APP_NAME = "ELIOT"


def _cle_emergent() -> str:
    """Clé lue en local. Elle n'est pas dans le code publié."""
    env = os.environ.get("EMERGENT_LLM_KEY", "").strip()
    if env:
        return env
    fichier = Path(__file__).resolve().parent.parent / ".secrets" / "emergent_llm_key"
    if fichier.is_file():
        return fichier.read_text(encoding="utf-8").strip()
    return ""


EMERGENT_LLM_KEY = _cle_emergent()

CLAUDE_MODELS = {
    "claude-sonnet-4-5-20250929": "Claude Sonnet 4.5 (recommandé)",
    "claude-sonnet-4-6": "Claude Sonnet 4.6",
    "claude-haiku-4-5-20251001": "Claude Haiku 4.5 (rapide)",
    "claude-opus-4-5-20251101": "Claude Opus 4.5 (puissant)",
}
PROVIDERS = {
    "emergent": "Clé Emergent intégrée",
    "anthropic": "Ma propre clé Anthropic",
    "demo": "Mode démonstration (sans IA)",
}
VOICE_ENGINES = {
    "openai": "Voix réaliste OpenAI (secours Hortense)",
    "hortense": "Microsoft Hortense (hors ligne)",
    "none": "Aucune voix",
}
OPENAI_VOICES = ["nova", "alloy", "ash", "coral", "echo", "fable", "onyx", "sage", "shimmer"]
DEFAULT_DOMAINS = [
    "duckduckgo.com", "wikipedia.org", "google.com", "github.com", "linkedin.com",
    "youtube.com", "lemonde.fr", "service-public.fr", "meteofrance.com",
]


def data_dir() -> Path:
    base = os.environ.get("ELIOT_HOME") or os.path.join(os.environ.get("APPDATA") or str(Path.home()), APP_NAME)
    path = Path(base)
    path.mkdir(parents=True, exist_ok=True)
    return path


def resource_path(rel: str) -> Path:
    base = getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent)
    return Path(base) / rel


def _default_folders() -> list:
    home = Path.home()
    return [str(home / name) for name in ("Desktop", "Documents", "Downloads")]


@dataclass
class Settings:
    user_name: str = ""
    ai_provider: str = "emergent"
    model: str = "claude-sonnet-4-5-20250929"
    voice_engine: str = "openai"
    openai_voice: str = "nova"
    tts_model: str = "tts-1"
    speak_replies: bool = True
    allow_all_domains: bool = False
    allow_search_results: bool = True
    allowed_domains: list = field(default_factory=lambda: list(DEFAULT_DOMAINS))
    allowed_folders: list = field(default_factory=_default_folders)
    adaptive_workflows: bool = True
    confirm_actions: bool = False
    max_steps: int = 12
    max_task_seconds: int = 300
    wake_word: bool = True
    wake_confirm_online: bool = True
    voice_followup: bool = True
    keep_in_tray: bool = True
    outlook_enabled: bool = True
    gmail_address: str = ""
    path: str = field(default="", repr=False)

    @classmethod
    def load(cls, path=None) -> "Settings":
        path = Path(path or data_dir() / "settings.json")
        data = {}
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                data = {}
        known = {f.name for f in fields(cls)} - {"path"}
        settings = cls(**{k: v for k, v in data.items() if k in known})
        settings.path = str(path)
        return settings

    def save(self) -> None:
        data = asdict(self)
        data.pop("path")
        Path(self.path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
