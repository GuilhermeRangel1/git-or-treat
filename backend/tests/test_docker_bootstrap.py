import sys

import pytest

from scripts import bootstrap_docker, bootstrap_local_auth


def test_stage_preserves_csv_and_separates_cadastro(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "manifest.json").write_text('{"schema_version":"gold-csv-v2"}')
    for name in (*bootstrap_docker.TABLES, "cadastro_titular_uc"):
        folder = source / name
        folder.mkdir()
        (folder / "part.csv").write_bytes(b"coluna\nvalor\n")
        (folder / "_SUCCESS").touch()
    (source / "cadastro_titular_uc" / "manifest.json").write_text("{}")
    target = tmp_path / "analytical"
    target.mkdir()
    cadastro = bootstrap_docker.stage_package(source, target)
    assert {p.name for p in target.iterdir()} == {"manifest.json", *bootstrap_docker.TABLES}
    assert (target / "faturas_uc" / "part.csv").read_bytes() == b"coluna\nvalor\n"
    assert cadastro is not None and (cadastro / "manifest.json").is_file()
    assert (source / "cadastro_titular_uc" / "_SUCCESS").exists()


def test_stage_rejects_unexpected_root_instead_of_ignoring_it(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "unexpected.csv").touch()
    with pytest.raises(ValueError):
        bootstrap_docker.stage_package(source, tmp_path / "target")


def test_bootstrap_rejects_other_database_before_any_command(monkeypatch):
    monkeypatch.setenv("DOCKER_BOOTSTRAP", "true")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://gold_loader:secret@other:5432/v_energy")
    calls = []
    monkeypatch.setattr(bootstrap_docker, "run", lambda *args: calls.append(args))
    assert bootstrap_docker.main() == 1
    assert calls == []


def test_presentation_requires_explicit_docker_opt_in(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "argv", ["bootstrap_local_auth.py", "--output", str(tmp_path / "credentials.txt")])
    monkeypatch.setenv("LOCAL_PRESENTATION_ACCOUNTS", "true")
    monkeypatch.setenv("LOCAL_PRESENTATION_PASSWORD", "senha123")
    monkeypatch.delenv("DOCKER_BOOTSTRAP", raising=False)
    assert bootstrap_local_auth.main() == 1
    assert not (tmp_path / "credentials.txt").exists()
