import pytest

from eliot.files.manager import FileAccessError


def test_organize_and_undo(services, tmp_path):
    zone = tmp_path / "zone"
    for name in ("photo.JPG", "cv.pdf", "budget.xlsx", "notes.txt", "inconnu.xyz"):
        (zone / name).write_text("x")
    path, plan = services.files.plan_organize(str(zone))
    assert len(plan) == 5
    result = services.toolbox.run("organize_folder", {"folder": str(zone)})
    assert "5 fichiers" in result
    assert (zone / "Images" / "photo.JPG").exists()
    assert (zone / "Documents" / "cv.pdf").exists()
    assert (zone / "Tableurs" / "budget.xlsx").exists()
    assert (zone / "Autres" / "inconnu.xyz").exists()
    assert "5 fichiers" in services.toolbox.run("undo_organize", {})
    assert (zone / "photo.JPG").exists() and not (zone / "Images").exists()


def test_collision_names(services, tmp_path):
    zone = tmp_path / "zone"
    (zone / "Images").mkdir()
    (zone / "Images" / "a.png").write_text("old")
    (zone / "a.png").write_text("new")
    _, plan = services.files.plan_organize(str(zone))
    assert plan[0][1].endswith("a (2).png")


def test_folder_outside_allowed_is_refused(services, tmp_path):
    outside = tmp_path / "secret"
    outside.mkdir()
    with pytest.raises(FileAccessError):
        services.files.resolve(str(outside))


def test_list_folder(services, tmp_path):
    (tmp_path / "zone" / "rapport.docx").write_text("x")
    (tmp_path / "zone" / "Sous").mkdir()
    out = services.toolbox.run("list_folder", {"folder": "zone"})
    assert "rapport.docx" in out and "[dossier] Sous" in out
