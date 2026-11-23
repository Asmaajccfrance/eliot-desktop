"""Navigateur Chromium visible (Playwright) avec un profil séparé des navigateurs personnels."""
import json
import logging
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

log = logging.getLogger("eliot")


class BrowserError(Exception):
    pass


def normalize_url(url: str) -> str:
    url = url.strip().strip("\"'«» ")
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url
    return url


def ddg_target(href: str) -> str:
    if "uddg=" in href:
        query = parse_qs(urlparse(href).query)
        if query.get("uddg"):
            return unquote(query["uddg"][0])
    if href.startswith("//"):
        return "https:" + href
    return href


def browsers_dir() -> Path:
    """Dossier Chromium partagé avec `playwright install`.

    Dans l'exe, Playwright force sinon PLAYWRIGHT_BROWSERS_PATH=0 et cherche
    chrome.exe sous `_internal\\playwright\\driver\\package\\.local-browsers`.
    """
    raw = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "")
    if raw and raw != "0":
        path = Path(raw)
    else:
        local = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        path = Path(local) / "ms-playwright"
    path.mkdir(parents=True, exist_ok=True)
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(path)
    return path


def chromium_executable() -> Path:
    import playwright
    meta = Path(playwright.__file__).parent / "driver" / "package" / "browsers.json"
    revision = "1255"
    try:
        browsers = json.loads(meta.read_text(encoding="utf-8"))["browsers"]
        revision = next(b["revision"] for b in browsers if b["name"] == "chromium")
    except (OSError, json.JSONDecodeError, StopIteration, KeyError):
        pass
    root = browsers_dir() / f"chromium-{revision}"
    for name in ("chrome-win64", "chrome-win"):
        exe = root / name / "chrome.exe"
        if exe.is_file():
            return exe
    return root / "chrome-win64" / "chrome.exe"


def install_chromium() -> None:
    browsers_dir()
    from playwright._impl._driver import compute_driver_executable, get_driver_env
    exe = compute_driver_executable()
    cmd = list(exe) if isinstance(exe, (tuple, list)) else [str(exe)]
    flags = 0x08000000 if sys.platform == "win32" else 0
    log.info("Installation de Chromium dans %s", os.environ.get("PLAYWRIGHT_BROWSERS_PATH"))
    try:
        subprocess.run(cmd + ["install", "chromium"], env=get_driver_env(), check=True, creationflags=flags)
    except Exception as exc:
        raise BrowserError(f"Installation de Chromium impossible : {exc}") from exc


class BrowserService:
    def __init__(self, settings, profile_dir, headless=False):
        self.settings = settings
        self.profile_dir = str(profile_dir)
        self.headless = headless
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="eliot-browser")
        self._pw = None
        self._ctx = None
        self._page = None
        self.last_results = []

    def _call(self, fn, *args):
        return self._pool.submit(fn, *args).result(timeout=420)

    def domain_allowed(self, url: str) -> bool:
        if self.settings.allow_all_domains:
            return True
        host = (urlparse(url).hostname or "").lower()
        return any(host == d or host.endswith("." + d) for d in (x.strip().lower() for x in self.settings.allowed_domains) if d)

    def _launch(self):
        args = [] if self.headless else ["--start-maximized"]
        return self._pw.chromium.launch_persistent_context(
            self.profile_dir, headless=self.headless, locale="fr-FR",
            no_viewport=not self.headless, args=args)

    def _start_playwright(self):
        browsers_dir()
        if not chromium_executable().is_file():
            install_chromium()
        if self._pw is None:
            from playwright.sync_api import sync_playwright
            self._pw = sync_playwright().start()

    def _ensure_page(self):
        if self._page is not None and not self._page.is_closed():
            return self._page
        if self._ctx is not None:
            try:
                self._page = self._ctx.new_page()
                return self._page
            except Exception:
                self._ctx = None
        self._start_playwright()
        try:
            self._ctx = self._launch()
        except Exception as exc:
            if "Executable doesn't exist" not in str(exc) and "playwright install" not in str(exc):
                raise BrowserError(f"Impossible de démarrer Chromium : {exc}") from exc
            install_chromium()
            self._ctx = self._launch()
        self._page = self._ctx.pages[0] if self._ctx.pages else self._ctx.new_page()
        return self._page

    def _goto(self, url: str) -> str:
        page = self._ensure_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
        except Exception as exc:
            raise BrowserError(f"La page n'a pas pu se charger : {str(exc).splitlines()[0]}") from exc
        try:
            page.wait_for_load_state("networkidle", timeout=6000)
        except Exception:
            pass
        try:
            page.bring_to_front()
        except Exception:
            pass
        return page.title() or url

    def search(self, query: str) -> list:
        return self._call(self._search, query)

    def _search(self, query: str) -> list:
        self._goto("https://html.duckduckgo.com/html/?kl=fr-fr&q=" + quote_plus(query))
        items = self._page.eval_on_selector_all(
            "a.result__a", "els => els.slice(0, 8).map(e => ({title: e.innerText.trim(), url: e.href}))")
        self.last_results = [{"title": i["title"], "url": ddg_target(i["url"])} for i in items if i.get("url")]
        return self.last_results

    def open(self, url: str, trusted: bool = False) -> str:
        url = normalize_url(url)
        if not trusted and not self.domain_allowed(url):
            host = urlparse(url).hostname
            raise BrowserError(f"Le domaine {host} n'est pas autorisé. Ajoute-le dans Paramètres > Internet.")
        return self._call(self._goto, url)

    def open_result(self, index: int) -> tuple:
        if not self.last_results:
            raise BrowserError("Je n'ai pas encore de résultats de recherche.")
        if not 1 <= index <= len(self.last_results):
            raise BrowserError(f"Il n'y a que {len(self.last_results)} résultats.")
        url = self.last_results[index - 1]["url"]
        return url, self.open(url, trusted=self.settings.allow_search_results)

    def read(self) -> dict:
        return self._call(self._read)

    def _read(self) -> dict:
        if self._page is None or self._page.is_closed():
            raise BrowserError("Aucune page n'est ouverte dans le navigateur d'ELIOT.")
        try:
            text = self._page.inner_text("body", timeout=10000)
        except Exception as exc:
            raise BrowserError(f"Lecture de la page impossible : {str(exc).splitlines()[0]}") from exc
        text = re.sub(r"\n\s*\n+", "\n", re.sub(r"[ \t]+", " ", text)).strip()
        return {"title": self._page.title(), "url": self._page.url, "text": text[:8000]}

    def shutdown(self) -> None:
        def _close():
            for obj in (self._ctx, self._pw):
                try:
                    if obj is self._pw and obj is not None:
                        obj.stop()
                    elif obj is not None:
                        obj.close()
                except Exception:
                    pass
        if self._pw is not None:
            try:
                self._pool.submit(_close).result(timeout=10)
            except Exception:
                pass
        self._pool.shutdown(wait=False)
