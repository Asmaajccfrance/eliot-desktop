"""Analyse d'un projet de code : détection du type, lancement des tests, sortie pour Claude."""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


class ProjectError(Exception):
    pass


def _python(path: Path) -> str:
    for venv in (".venv", "venv", "env"):
        exe = path / venv / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        if exe.exists():
            return str(exe)
    if not getattr(sys, "frozen", False):
        return sys.executable
    found = shutil.which("python") or shutil.which("py")
    if not found:
        raise ProjectError("Python est introuvable sur ce PC pour lancer les tests du projet.")
    return found


def detect(path: Path) -> tuple:
    pkg = path / "package.json"
    if pkg.exists():
        try:
            scripts = json.loads(pkg.read_text(encoding="utf-8")).get("scripts", {})
        except ValueError:
            scripts = {}
        npm = shutil.which("npm") or "npm"
        if "test" in scripts:
            return "JavaScript (npm test)", [npm, "test", "--silent"]
        if "lint" in scripts:
            return "JavaScript (npm run lint)", [npm, "run", "lint"]
        if "build" in scripts:
            return "JavaScript (npm run build)", [npm, "run", "build"]
    has_tests = any((path / n).exists() for n in ("pytest.ini", "tests", "test", "conftest.py")) or \
        any(path.glob("test_*.py"))
    if has_tests or (path / "pyproject.toml").exists() or (path / "setup.cfg").exists():
        return "Python (pytest)", [_python(path), "-m", "pytest", "-q", "--maxfail=20", "--color=no", "-p", "no:cacheprovider"]
    if any(path.glob("*.py")) or any(path.glob("*/*.py")):
        return "Python (vérification de syntaxe)", [_python(path), "-m", "compileall", "-q", "."]
    raise ProjectError("Je ne reconnais pas ce type de projet (ni package.json, ni projet Python).")


def run_checks(path: Path, timeout: int = 240) -> dict:
    kind, cmd = detect(path)
    flags = 0x08000000 if sys.platform == "win32" else 0
    env = dict(os.environ, PYTHONIOENCODING="utf-8", CI="1", FORCE_COLOR="0", NO_COLOR="1", PYTHONDONTWRITEBYTECODE="1")
    try:
        proc = subprocess.run(cmd, cwd=str(path), capture_output=True, text=True, encoding="utf-8", errors="replace",
                              timeout=timeout, creationflags=flags, env=env, shell=sys.platform == "win32" and
                              cmd[0].lower().endswith(("npm", "npm.cmd")))
    except subprocess.TimeoutExpired:
        return {"kind": kind, "ok": False, "code": -1, "output": f"Délai dépassé ({timeout} s)."}
    except OSError as exc:
        raise ProjectError(f"Impossible de lancer {' '.join(cmd[:2])} : {exc}") from exc
    output = re.sub(r"\x1b\[[0-9;]*m", "", ((proc.stdout or "") + "\n" + (proc.stderr or ""))).strip()
    return {"kind": kind, "ok": proc.returncode == 0, "code": proc.returncode, "output": output[-6000:]}
