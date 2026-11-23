from dataclasses import dataclass

from .agent_workflows.planner import Planner
from .agent_workflows.tools import ToolBox
from .apps.launcher import AppLauncher
from .apps.registry import AppRegistry
from .config import Settings, data_dir
from .files.manager import FileManager
from .history import History
from .mail.service import MailService
from .memory import Memory
from .scheduler import Scheduler
from .llm.engine import LLMEngine
from .web.browser import BrowserService
from .windows.control import WindowController


@dataclass
class Services:
    settings: Settings
    history: History
    registry: AppRegistry
    windows: WindowController
    launcher: AppLauncher
    files: FileManager
    browser: BrowserService
    llm: LLMEngine
    memory: Memory = None
    scheduler: Scheduler = None
    mail: MailService = None
    toolbox: ToolBox = None
    planner: Planner = None


def build_services(settings: Settings = None, **overrides) -> Services:
    root = data_dir()
    settings = settings or Settings.load()
    windows = overrides.get("windows") or WindowController()
    services = Services(
        settings=settings,
        history=overrides.get("history") or History(root / "historique.sqlite3"),
        registry=overrides.get("registry") or AppRegistry(root / "applications.json"),
        windows=windows,
        launcher=overrides.get("launcher") or AppLauncher(windows),
        files=overrides.get("files") or FileManager(settings, root / "dernier_rangement.json"),
        browser=overrides.get("browser") or BrowserService(settings, root / "navigateur"),
        llm=overrides.get("llm"),
        memory=overrides.get("memory") or Memory(root / "memoire.sqlite3"),
        scheduler=overrides.get("scheduler") or Scheduler(root / "programmations.json"),
        mail=overrides.get("mail") or MailService(settings),
    )
    if services.llm is None:
        services.llm = LLMEngine(settings, memory=services.memory)
    services.toolbox = ToolBox(services)
    services.planner = Planner(services.toolbox, services.llm, settings, services.registry)
    return services
