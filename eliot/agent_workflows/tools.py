"""Boîte à outils d'ELIOT : chaque action possible, son niveau de risque et ses garde-fous."""
import time
from dataclasses import dataclass
from typing import Callable
from urllib.parse import quote_plus

from ..dev.project import ProjectError, run_checks
from ..mail.accounts import MailError
from ..text import simplify
from .models import ACT, MODIFY, READ


class ToolError(Exception):
    pass


@dataclass
class Tool:
    name: str
    description: str
    params: dict
    risk: str
    func: Callable


class ToolBox:
    def __init__(self, services):
        self.s = services
        self.tools = {}
        r = self._register
        r("open_app", "Ouvre une application autorisée, ou l'active si elle est déjà ouverte.",
          {"name": "nom de l'application"}, ACT, self.open_app,
          lambda a: f"Ouvrir {a.get('name', '')}")
        r("activate_window", "Met au premier plan la fenêtre d'une application autorisée (l'ouvre si besoin).",
          {"title": "nom de l'application ou titre de fenêtre"}, ACT, self.activate_window,
          lambda a: f"Activer la fenêtre {a.get('title', '')}")
        r("list_windows", "Liste les fenêtres ouvertes appartenant aux applications autorisées.", {}, READ,
          self.list_windows, lambda a: "Lister les fenêtres ouvertes")
        r("close_app", "Ferme une application autorisée.", {"name": "nom de l'application"}, MODIFY,
          self.close_app, lambda a: f"Fermer {a.get('name', '')}")
        r("type_text", "Écrit du texte au clavier dans une application autorisée (fenêtre active si window vide).",
          {"text": "texte à écrire", "window": "application cible (optionnel)"}, MODIFY, self.type_text,
          lambda a: f"Écrire « {a.get('text', '')[:60]} »" + (f" dans {a['window']}" if a.get("window") else ""))
        r("press_keys", "Envoie un raccourci clavier (ex : ctrl+s, entrée, alt+tab).",
          {"keys": "raccourci", "window": "application cible (optionnel)"}, MODIFY, self.press_keys,
          lambda a: f"Appuyer sur {a.get('keys', '')}")
        r("click_element", "Clique sur un bouton ou un menu par son nom dans une application autorisée.",
          {"name": "texte du bouton", "window": "application cible (optionnel)"}, MODIFY, self.click_element,
          lambda a: f"Cliquer sur « {a.get('name', '')} »")
        r("click_at", "Clique à une position de l'écran (x, y) dans la fenêtre active autorisée.",
          {"x": "abscisse", "y": "ordonnée"}, MODIFY, self.click_at,
          lambda a: f"Cliquer à la position ({a.get('x')}, {a.get('y')})")
        r("web_search", "Recherche sur Internet (DuckDuckGo) dans le navigateur d'ELIOT.", {"query": "requête"},
          READ, self.web_search, lambda a: f"Rechercher « {a.get('query', '')} »")
        r("search_in_app", "Lance une recherche web dans un navigateur installé (Firefox, Chrome, Edge).",
          {"name": "navigateur", "query": "requête"}, ACT, self.search_in_app,
          lambda a: f"Rechercher « {a.get('query', '')} » dans {a.get('name', '')}")
        r("open_url", "Ouvre une adresse web autorisée dans le navigateur d'ELIOT.", {"url": "adresse"}, ACT,
          self.open_url, lambda a: f"Ouvrir {a.get('url', '')}")
        r("open_result", "Ouvre le n-ième résultat de la dernière recherche.", {"index": "numéro (1 à 8)"}, ACT,
          self.open_result, lambda a: f"Ouvrir le résultat n°{a.get('index', 1)}")
        r("read_page", "Lit le texte de la page ouverte dans le navigateur d'ELIOT.", {}, READ, self.read_page,
          lambda a: "Lire la page ouverte")
        r("list_folder", "Liste le contenu d'un dossier autorisé (bureau, documents, téléchargements…).",
          {"folder": "dossier"}, READ, self.list_folder, lambda a: f"Lister le dossier {a.get('folder', '')}")
        r("open_folder", "Ouvre un dossier autorisé dans l'Explorateur.", {"folder": "dossier"}, ACT,
          self.open_folder, lambda a: f"Ouvrir le dossier {a.get('folder', '')}")
        r("organize_folder", "Range les fichiers d'un dossier autorisé dans des sous-dossiers par type.",
          {"folder": "dossier"}, MODIFY, self.organize_folder,
          lambda a: f"Ranger les fichiers du dossier {a.get('folder', '')}")
        r("undo_organize", "Annule le dernier rangement de dossier.", {}, MODIFY, self.undo_organize,
          lambda a: "Annuler le dernier rangement")
        r("open_in_app", "Ouvre un dossier/projet autorisé dans une application (Cursor, VS Code, Explorateur).",
          {"name": "application", "target": "dossier ou projet"}, ACT, self.open_in_app,
          lambda a: f"Ouvrir {a.get('target', '')} dans {a.get('name', '')}")
        r("read_file", "Lit un fichier texte d'un dossier autorisé (code, notes…).", {"path": "chemin du fichier"}, READ,
          self.read_file, lambda a: f"Lire le fichier {a.get('path', '')}")
        r("analyze_project", "Lance les tests/vérifications d'un projet de code (dossier autorisé) et renvoie la sortie.",
          {"folder": "dossier du projet"}, MODIFY, self.analyze_project,
          lambda a: f"Lancer les tests du projet {a.get('folder', '')}")
        r("check_emails", "Liste les e-mails non lus (Outlook et/ou Gmail configurés).",
          {"account": "outlook, gmail ou vide pour tous", "count": "nombre max (défaut 10)"}, READ, self.check_emails,
          lambda a: "Consulter les nouveaux e-mails" + (f" ({a['account']})" if a.get("account") else ""))
        r("read_email", "Lit le contenu complet d'un e-mail de la dernière liste.", {"index": "numéro de l'e-mail"}, READ,
          self.read_email, lambda a: f"Lire l'e-mail n°{a.get('index', 1)}")
        r("prepare_replies", "Rédige avec Claude des réponses aux e-mails de la dernière liste (sans les envoyer).",
          {"instructions": "consignes de ton/contenu (optionnel)"}, READ, self.prepare_replies,
          lambda a: "Préparer les réponses aux e-mails")
        r("send_reply", "Envoie réellement la réponse préparée pour l'e-mail n°index.", {"index": "numéro de l'e-mail"},
          MODIFY, self.send_reply, lambda a: f"Envoyer la réponse à l'e-mail n°{a.get('index', 1)}")
        r("save_drafts", "Enregistre les réponses préparées dans les brouillons de la messagerie.", {}, ACT,
          self.save_drafts, lambda a: "Enregistrer les réponses en brouillons")
        r("wait", "Attend quelques secondes (chargement).", {"seconds": "durée (max 10)"}, READ, self.wait,
          lambda a: f"Patienter {a.get('seconds', 2)} s")

    def _register(self, name, description, params, risk, func, describe):
        tool = Tool(name, description, params, risk, func)
        tool.describe = describe
        self.tools[name] = tool

    def describe_for_llm(self) -> str:
        lines = []
        for t in self.tools.values():
            params = ", ".join(f"{k}: {v}" for k, v in t.params.items()) or "aucun paramètre"
            lines.append(f"- {t.name} ({t.risk}) : {t.description} Paramètres : {params}")
        return "\n".join(lines)

    def describe_step(self, name: str, args: dict) -> str:
        return self.tools[name].describe(args)

    def run(self, name: str, args: dict) -> str:
        tool = self.tools.get(name)
        if tool is None:
            raise ToolError(f"Outil inconnu : {name}.")
        kwargs = {k: v for k, v in (args or {}).items() if k in tool.params}
        try:
            return tool.func(**kwargs)
        except TypeError as exc:
            raise ToolError(f"Paramètres invalides pour {name} : {exc}") from exc

    # --- applications et fenêtres -------------------------------------------------
    def _app(self, name: str):
        app = self.s.registry.find(name)
        if app is None:
            raise ToolError(f"« {name} » ne fait pas partie des applications autorisées. "
                            "Ajoute-la dans « Applications ».")
        if not app.enabled:
            raise ToolError(f"{app.name} est désactivée dans « Applications ».")
        return app

    def open_app(self, name: str) -> str:
        return self.s.launcher.open(self._app(name))

    def activate_window(self, title: str) -> str:
        app = self.s.registry.find(title)
        if app is not None:
            app = self._app(title)
            if self.s.launcher.is_running(app):
                if self.s.windows.activate(app.window_pattern or app.name, process_names=app.process_names):
                    return f"La fenêtre {app.name} est au premier plan."
            return self.s.launcher.open(app)
        info = self.s.windows.find(title)
        if info and self._allowed_window(info):
            self.s.windows.activate(title)
            return f"La fenêtre « {info['title']} » est au premier plan."
        raise ToolError(f"Je ne trouve aucune fenêtre autorisée correspondant à « {title} ».")

    def _allowed_window(self, info: dict, need_control: bool = False):
        proc = (info.get("process") or "").lower()
        title = simplify(info.get("title", ""))
        for app in self.s.registry.enabled():
            by_proc = proc and proc in [p.lower() for p in app.process_names]
            by_title = any(simplify(p) and simplify(p) in title for p in app.window_pattern.split("|"))
            if by_proc or by_title:
                return app if (app.allow_control or not need_control) else None
        return None

    def list_windows(self) -> str:
        allowed = [(w, self._allowed_window(w)) for w in self.s.windows.list_windows()]
        allowed = [(w, a) for w, a in allowed if a]
        if not allowed:
            return "Aucune fenêtre d'application autorisée n'est ouverte."
        return "Fenêtres ouvertes :\n" + "\n".join(f"• {a.name} — {w['title']}" for w, a in allowed)

    def close_app(self, name: str) -> str:
        return self.s.launcher.close(self._app(name))

    def _control_target(self, window: str = "") -> dict:
        if window:
            app = self._app(window)
            if not app.allow_control:
                raise ToolError(f"Le contrôle clavier/souris de {app.name} n'est pas autorisé. "
                                "Coche « Contrôle » dans « Applications ».")
            info = self.s.windows.activate(app.window_pattern or app.name, process_names=app.process_names)
            if not info:
                self.s.launcher.open(app)
                time.sleep(1.5)
                info = self.s.windows.activate(app.window_pattern or app.name, process_names=app.process_names)
            if not info:
                raise ToolError(f"Je n'ai pas trouvé la fenêtre de {app.name}.")
            return info
        info = self.s.windows.foreground()
        if not self._allowed_window(info, need_control=True):
            raise ToolError(f"La fenêtre active (« {info.get('title') or 'inconnue'} ») n'est pas autorisée au contrôle. "
                            "Précise l'application, par exemple « écris bonjour dans le Bloc-notes ».")
        return info

    def type_text(self, text: str, window: str = "") -> str:
        info = self._control_target(window)
        self.s.windows.type_text(text)
        return f"J'ai écrit le texte dans « {info['title']} »."

    def press_keys(self, keys: str, window: str = "") -> str:
        info = self._control_target(window)
        try:
            self.s.windows.press_keys(keys)
        except ValueError as exc:
            raise ToolError(str(exc)) from exc
        return f"Raccourci {keys} envoyé à « {info['title']} »."

    def click_element(self, name: str, window: str = "") -> str:
        info = self._control_target(window)
        try:
            label = self.s.windows.click_element(info["handle"], name)
        except Exception as exc:
            raise ToolError(f"Je n'ai pas trouvé « {name} » dans « {info['title']} ».") from exc
        return f"J'ai cliqué sur « {label} »."

    def click_at(self, x, y) -> str:
        info = self._control_target("")
        self.s.windows.click_at(int(x), int(y))
        return f"Clic effectué en ({x}, {y}) dans « {info['title']} »."

    # --- internet -------------------------------------------------------------------
    def web_search(self, query: str) -> str:
        results = self.s.browser.search(query)
        if not results:
            return f"Aucun résultat pour « {query} »."
        lines = [f"{i}. {r['title']} — {r['url']}" for i, r in enumerate(results, 1)]
        return f"Résultats pour « {query} » :\n" + "\n".join(lines)

    def search_in_app(self, name: str, query: str) -> str:
        app = self._app(name)
        if not app.is_browser:
            raise ToolError(f"{app.name} n'est pas un navigateur.")
        url = "https://duckduckgo.com/?kl=fr-fr&q=" + quote_plus(query)
        self.s.launcher.open_with(app, url)
        return f"J'ai lancé la recherche « {query} » dans {app.name}."

    def open_url(self, url: str) -> str:
        title = self.s.browser.open(url)
        return f"Page ouverte : {title}"

    def open_result(self, index=1) -> str:
        url, title = self.s.browser.open_result(int(index))
        return f"Page ouverte : {title} ({url})"

    def read_page(self) -> str:
        page = self.s.browser.read()
        return f"Page « {page['title']} » ({page['url']}) :\n{page['text']}"

    # --- dossiers -------------------------------------------------------------------
    def list_folder(self, folder: str) -> str:
        path, entries = self.s.files.list(folder)
        if not entries:
            return f"Le dossier {path} est vide."
        shown = [("[dossier] " if e.is_dir() else "") + e.name for e in entries[:40]]
        more = f"\n… et {len(entries) - 40} autres éléments." if len(entries) > 40 else ""
        return f"{path} contient {len(entries)} éléments :\n" + "\n".join(shown) + more

    def open_folder(self, folder: str) -> str:
        return f"J'ai ouvert {self.s.files.open_in_explorer(folder)} dans l'Explorateur."

    def organize_folder(self, folder: str) -> str:
        path, plan = self.s.files.plan_organize(folder)
        if not plan:
            return f"Il n'y a aucun fichier à ranger dans {path}."
        count = self.s.files.apply(plan)
        cats = sorted({p[1].split("\\" if "\\" in p[1] else "/")[-2] for p in plan})
        return (f"J'ai rangé {count} fichiers de {path} dans : {', '.join(cats)}. "
                "Dis « annule le rangement » pour revenir en arrière.")

    def undo_organize(self) -> str:
        restored = self.s.files.undo_last()
        return f"J'ai remis {restored} fichiers à leur place." if restored else "Il n'y a aucun rangement à annuler."

    # --- projets de code ------------------------------------------------------------
    def _target_path(self, target: str):
        try:
            return self.s.files.resolve(target)
        except Exception as exc:
            raise ToolError(str(exc)) from exc

    def open_in_app(self, name: str, target: str) -> str:
        app = self._app(name)
        path = self._target_path(target)
        if app.key == "explorer":
            return f"J'ai ouvert {self.s.files.open_in_explorer(str(path))} dans l'Explorateur."
        return self.s.launcher.open_with(app, str(path))

    def read_file(self, path: str) -> str:
        from pathlib import Path
        file = Path(path)
        if not file.is_absolute():
            matches = [r / path for r in self.s.files.allowed_roots() if (r / path).is_file()]
            file = matches[0] if matches else file
        if not file.is_file() or not self.s.files.is_allowed(file):
            raise ToolError(f"Fichier introuvable ou hors des dossiers autorisés : {path}")
        if file.stat().st_size > 400_000:
            raise ToolError("Fichier trop volumineux pour être lu.")
        text = file.read_text(encoding="utf-8", errors="replace")
        return f"{file} :\n{text[:9000]}"

    def analyze_project(self, folder: str) -> str:
        path = self._target_path(folder)
        try:
            result = run_checks(path)
        except ProjectError as exc:
            raise ToolError(str(exc)) from exc
        verdict = "aucune erreur détectée" if result["ok"] else f"des erreurs ont été détectées (code {result['code']})"
        return f"Projet {path} — {result['kind']} : {verdict}.\nSortie :\n{result['output']}"

    # --- e-mails ----------------------------------------------------------------------
    def check_emails(self, account: str = "", count=10) -> str:
        try:
            mails = self.s.mail.check(account, int(count or 10))
        except MailError as exc:
            raise ToolError(str(exc)) from exc
        if not mails:
            return "Aucun nouvel e-mail."
        lines = [f"{i}. [{m.account}] {m.date} — {m.sender} — {m.subject}\n   {m.body[:160]}" for i, m in enumerate(mails, 1)]
        warn = ("\n" + " ".join(self.s.mail.errors)) if getattr(self.s.mail, "errors", None) else ""
        return f"{len(mails)} e-mail(s) non lu(s) :\n" + "\n".join(lines) + warn

    def read_email(self, index=1) -> str:
        try:
            m = self.s.mail.get(int(index))
        except MailError as exc:
            raise ToolError(str(exc)) from exc
        return f"De : {m.sender} <{m.sender_addr}>\nDate : {m.date}\nSujet : {m.subject}\n\n{m.body}"

    def prepare_replies(self, instructions: str = "") -> str:
        try:
            drafts = self.s.mail.prepare(self.s.llm, instructions)
        except MailError as exc:
            raise ToolError(str(exc)) from exc
        if not drafts:
            return "Aucun e-mail ne semble nécessiter de réponse."
        parts = []
        for idx, text in sorted(drafts.items()):
            m = self.s.mail.get(idx)
            parts.append(f"Réponse n°{idx} à {m.sender} (« {m.subject} ») :\n{text}")
        return ("\n\n".join(parts) + "\n\nDis « envoie la réponse N » pour l'envoyer, ou « enregistre les brouillons ».")

    def send_reply(self, index=1) -> str:
        try:
            return self.s.mail.send(int(index))
        except MailError as exc:
            raise ToolError(str(exc)) from exc

    def save_drafts(self) -> str:
        try:
            count = self.s.mail.save_drafts()
        except MailError as exc:
            raise ToolError(str(exc)) from exc
        return f"{count} réponse(s) enregistrée(s) dans les brouillons." if count else "Aucune réponse préparée."

    def wait(self, seconds=2) -> str:
        time.sleep(max(0.0, min(float(seconds), 10.0)))
        return f"Attente de {seconds} s terminée."
