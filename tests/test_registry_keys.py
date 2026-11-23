from eliot.apps.registry import AppRegistry
from eliot.windows.keys import escape_text, to_send_keys


def test_find_aliases(tmp_path):
    reg = AppRegistry(tmp_path / "apps.json")
    assert reg.find("Firefox").key == "firefox"
    assert reg.find("le bloc-notes").key == "notepad"
    assert reg.find("l'application vs code").key == "vscode"
    assert reg.find("firefoks").key == "firefox"
    assert reg.find("Cursor").key == "cursor"
    assert reg.find("logiciel inexistant") is None


def test_add_save_reload(tmp_path):
    reg = AppRegistry(tmp_path / "apps.json")
    app = reg.add("Mon Outil", r"C:\Outils\outil.exe", allow_control=True)
    reg.get("firefox").enabled = False
    reg.save()
    again = AppRegistry(tmp_path / "apps.json")
    assert again.find("mon outil").key == app.key
    assert again.get(app.key).process_names == ["outil.exe"]
    assert again.get("firefox").enabled is False
    again.remove(app.key)
    assert again.find("mon outil") is None


def test_send_keys():
    assert to_send_keys("ctrl s") == "^s"
    assert to_send_keys("Ctrl+Maj+N") == "^+n"
    assert to_send_keys("entrée") == "{ENTER}"
    assert to_send_keys("alt f4") == "%{F4}"
    assert escape_text("a+b (c)") == "a{+}b {(}c{)}"
