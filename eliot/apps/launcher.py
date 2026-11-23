import os
import subprocess
import sys
import time

IS_WINDOWS = sys.platform == "win32"


class AppError(Exception):
    pass


class AppLauncher:
    def __init__(self, windows):
        self.windows = windows

    def running_processes(self, app) -> list:
        import psutil
        names = {n.lower() for n in app.process_names}
        if not names:
            return []
        procs = []
        for proc in psutil.process_iter(["name"]):
            try:
                if (proc.info["name"] or "").lower() in names:
                    procs.append(proc)
            except (psutil.Error, KeyError):
                continue
        return procs

    def is_running(self, app) -> bool:
        return bool(self.running_processes(app))

    def _activate(self, app) -> bool:
        try:
            return bool(self.windows.activate(app.window_pattern or app.name, process_names=app.process_names))
        except Exception:
            return False

    def _spawn(self, command: str, *args: str) -> None:
        if not IS_WINDOWS:
            raise AppError("Le lancement d'applications n'est disponible que sous Windows.")
        try:
            if os.path.isabs(command):
                subprocess.Popen([command, *args], cwd=os.path.dirname(command))
            elif args:
                subprocess.Popen(["cmd", "/c", "start", "", command, *args], creationflags=0x08000000)
            else:
                os.startfile(command)
        except OSError as exc:
            raise AppError(f"Windows n'a pas pu lancer « {command} » : {exc.strerror or exc}") from exc

    def open(self, app) -> str:
        if self.is_running(app) and self._activate(app):
            return f"{app.name} était déjà ouvert : je l'ai mis au premier plan."
        command = app.command()
        if not command:
            raise AppError(f"Je ne connais pas l'emplacement de {app.name}. Indique son chemin dans « Applications ».")
        self._spawn(command)
        for _ in range(20):
            time.sleep(0.4)
            if self._activate(app):
                return f"{app.name} est ouvert."
        return f"J'ai lancé {app.name}."

    def open_with(self, app, target: str) -> str:
        command = app.command()
        if not command:
            raise AppError(f"Je ne connais pas l'emplacement de {app.name}.")
        self._spawn(command, target)
        return f"J'ai ouvert {target} dans {app.name}."

    def close(self, app) -> str:
        procs = self.running_processes(app)
        if not procs:
            return f"{app.name} n'est pas ouvert."
        for proc in procs:
            try:
                proc.terminate()
            except Exception:
                continue
        return f"J'ai fermé {app.name}."
