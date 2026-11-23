"""Contrôle des fenêtres Windows via UI Automation (pywinauto)."""
import re
import sys
import time

from ..text import simplify
from .keys import escape_text, to_send_keys

IS_WINDOWS = sys.platform == "win32"


class PlatformError(Exception):
    pass


def _require_windows():
    if not IS_WINDOWS:
        raise PlatformError("Le contrôle des fenêtres n'est disponible que sous Windows.")


def _proc_name(pid: int) -> str:
    try:
        import psutil
        return psutil.Process(pid).name()
    except Exception:
        return ""


class WindowController:
    def list_windows(self) -> list:
        _require_windows()
        from pywinauto import Desktop
        out = []
        for win in Desktop(backend="uia").windows():
            try:
                title = win.window_text()
                if title and win.is_visible() and title not in {"Program Manager"}:
                    out.append({"title": title, "process": _proc_name(win.process_id()), "handle": win.handle})
            except Exception:
                continue
        return out

    def find(self, pattern: str = "", process_names=None):
        procs = {p.lower() for p in (process_names or [])}
        alternatives = [simplify(p) for p in (pattern or "").split("|") if simplify(p)]
        for info in self.list_windows():
            if procs and info["process"].lower() in procs:
                return info
            title = simplify(info["title"])
            if any(alt in title for alt in alternatives):
                return info
        return None

    def _wrapper(self, handle):
        from pywinauto import Application
        return Application(backend="uia").connect(handle=handle).window(handle=handle)

    def activate(self, pattern: str = "", process_names=None):
        info = self.find(pattern, process_names)
        if not info:
            return None
        win = self._wrapper(info["handle"])
        try:
            if win.is_minimized():
                win.restore()
        except Exception:
            pass
        win.set_focus()
        return info

    def foreground(self) -> dict:
        _require_windows()
        import ctypes
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        length = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return {"title": buf.value, "process": _proc_name(pid.value), "handle": hwnd}

    def type_text(self, text: str) -> None:
        _require_windows()
        from pywinauto.keyboard import send_keys
        time.sleep(0.25)
        send_keys(escape_text(text), with_spaces=True, with_newlines=True, pause=0.01)

    def press_keys(self, combo: str) -> None:
        _require_windows()
        from pywinauto.keyboard import send_keys
        time.sleep(0.2)
        send_keys(to_send_keys(combo))

    def click_element(self, handle, name: str) -> str:
        _require_windows()
        win = self._wrapper(handle)
        ctrl = win.child_window(title_re=f"(?i).*{re.escape(name)}.*", found_index=0)
        ctrl.wait("exists", timeout=4)
        label = ctrl.window_text() or name
        ctrl.click_input()
        return label

    def click_at(self, x: int, y: int) -> None:
        _require_windows()
        from pywinauto import mouse
        mouse.click(button="left", coords=(int(x), int(y)))
