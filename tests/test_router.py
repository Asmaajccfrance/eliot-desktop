import pytest

from eliot.commands.router import clean, parse, split_segments


@pytest.mark.parametrize("text,kind,target", [
    ("Eliot, ouvre Firefox", "open_app", "Firefox"),
    ("ouvre firefox s'il te plaît", "open_app", "firefox"),
    ("Hey Eliot lance le Bloc-notes", "open_app", "Bloc-notes"),
    ("peux-tu ouvrir l'application Cursor ?", "open_app", "Cursor"),
    ("démarre Word", "open_app", "Word"),
    ("active la fenêtre Firefox", "activate_window", "Firefox"),
    ("bascule sur Cursor", "activate_window", "Cursor"),
    ("mets au premier plan le bloc-notes", "activate_window", "le bloc-notes"),
    ("liste les fenêtres ouvertes", "list_windows", ""),
    ("quelles fenêtres sont ouvertes ?", "list_windows", ""),
    ("ferme la calculatrice", "close_app", "calculatrice"),
    ("recherche la météo à Paris", "web_search", "la météo à Paris"),
    ("cherche sur internet des recettes de crêpes", "web_search", "des recettes de crêpes"),
    ("va sur wikipedia.org", "open_url", "wikipedia.org"),
    ("ouvre lemonde.fr", "open_url", "lemonde.fr"),
    ("ouvre le premier résultat", "open_result", "1"),
    ("ouvre le 3e résultat", "open_result", "3"),
    ("lis la page", "read_page", ""),
    ("résume cette page", "read_page", ""),
    ("range le dossier Téléchargements", "organize_folder", "Téléchargements"),
    ("organise les fichiers du dossier documents", "organize_folder", "documents"),
    ("liste les fichiers du bureau", "list_folder", "bureau"),
    ("ouvre le dossier documents", "open_folder", "documents"),
    ("annule le rangement", "undo", ""),
    ("appuie sur ctrl s", "press_keys", "ctrl s"),
    ("quelle heure est-il ?", "time", ""),
    ("stop", "stop", ""),
    ("Eliot, arrête-toi", "stop", ""),
    ("quelles applications sont autorisées ?", "list_apps", ""),
    ("raconte-moi une blague", "chat", ""),
    ("Qui a écrit Les Misérables ?", "chat", ""),
])
def test_parse(text, kind, target):
    intent = parse(text)
    assert intent.kind == kind
    if target:
        assert intent.target == target


def test_open_is_not_list_windows():
    """Régression V0.5 : « ouvre Firefox » listait les fenêtres au lieu d'ouvrir Firefox."""
    assert parse("Eliot, ouvre Firefox").kind == "open_app"
    assert parse("Firefox").kind == "chat"


def test_type_text_with_target_preserves_case():
    intent = parse("écris Bonjour Marie ! dans le Bloc-notes")
    assert intent.kind == "type_text"
    assert intent.text == "Bonjour Marie !"
    assert intent.target == "Bloc-notes"


def test_type_text_without_target():
    intent = parse("tape « Réunion à 14h »")
    assert intent.text == "Réunion à 14h" and intent.target == ""


def test_click_intent():
    intent = parse("clique sur le bouton Enregistrer dans Word")
    assert intent.kind == "click" and intent.text == "Enregistrer" and intent.target == "Word"


def test_multi_step_is_task():
    assert parse("Eliot, ouvre Firefox et recherche cette information").kind == "task"
    assert parse("ouvre le bloc-notes puis écris bonjour").kind == "task"
    assert parse("vérifie si mon site fonctionne").kind == "task"


def test_split_segments():
    assert split_segments("ouvre Firefox et recherche la météo, puis lis la page") == [
        "ouvre Firefox", "recherche la météo", "lis la page"]
    assert split_segments("recherche pain et beurre") == ["recherche pain et beurre"]


def test_clean_keeps_alignment():
    orig, low = clean("Eliot, peux-tu ÉCRIRE Été ?")
    assert orig == "ÉCRIRE Été" and low == "ecrire ete"
