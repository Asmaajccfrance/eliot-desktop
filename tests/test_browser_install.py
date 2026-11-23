import os
from pathlib import Path

import pytest

from eliot.web import browser


def test_browsers_dir_ignores_frozen_zero_path(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", "0")
    path = browser.browsers_dir()
    assert path == tmp_path / "ms-playwright"
    assert path.is_dir()
    assert os.environ["PLAYWRIGHT_BROWSERS_PATH"] == str(path)


def test_browsers_dir_keeps_an_explicit_folder(monkeypatch, tmp_path):
    custom = tmp_path / "navigateurs"
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(custom))
    assert browser.browsers_dir() == custom
    assert custom.is_dir()


def test_missing_chromium_is_installed_before_launch(monkeypatch, tmp_path):
    exe = tmp_path / "chromium-1255" / "chrome-win64" / "chrome.exe"
    calls = []

    def fake_install():
        calls.append("install")
        exe.parent.mkdir(parents=True, exist_ok=True)
        exe.write_bytes(b"x")

    monkeypatch.setattr(browser, "install_chromium", fake_install)
    monkeypatch.setattr(browser, "browsers_dir", lambda: tmp_path)
    monkeypatch.setattr(browser, "chromium_executable", lambda: exe)

    class PW:
        def start(self):
            return "driver"

    import playwright.sync_api as sync_api
    monkeypatch.setattr(sync_api, "sync_playwright", lambda: PW())

    class Service(browser.BrowserService):
        def __init__(self):
            self._pw = None

    service = Service()
    service._start_playwright()
    assert calls == ["install"]
    assert service._pw == "driver"
    assert exe.is_file()


def test_install_chromium_uses_the_user_folder(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("PLAYWRIGHT_BROWSERS_PATH", raising=False)
    seen = {}

    def fake_run(cmd, env, check, creationflags):
        seen["cmd"] = cmd
        seen["env"] = env
        assert check is True

    monkeypatch.setattr(browser.subprocess, "run", fake_run)
    monkeypatch.setattr(
        "playwright._impl._driver.compute_driver_executable",
        lambda: (r"C:\node.exe", r"C:\cli.js"),
    )
    browser.install_chromium()
    assert seen["cmd"][-2:] == ["install", "chromium"]
    assert seen["env"]["PLAYWRIGHT_BROWSERS_PATH"] == str(tmp_path / "ms-playwright")


def test_install_failure_is_a_browser_error(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("PLAYWRIGHT_BROWSERS_PATH", raising=False)

    def fake_run(*_args, **_kwargs):
        raise OSError("node introuvable")

    monkeypatch.setattr(browser.subprocess, "run", fake_run)
    monkeypatch.setattr(
        "playwright._impl._driver.compute_driver_executable",
        lambda: ("node", "cli.js"),
    )
    with pytest.raises(browser.BrowserError, match="Installation de Chromium impossible"):
        browser.install_chromium()
