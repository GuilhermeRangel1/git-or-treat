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


def test_presentation_bootstrap_resets_only_selected_local_password(tmp_path, monkeypatch, capsys):
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    from app.core.database import Base
    from app.core.passwords import hash_password, verify_password
    from app.core.platform_access import PlatformProfile
    from app.models.auth import AuthUser

    database_url = f"sqlite:///{(tmp_path / 'presentation.sqlite').as_posix()}"
    engine = create_engine(database_url, execution_options={
        "schema_translate_map": {"gold": None, "gold_v2": None, "gold_cadastro": None}
    })
    Base.metadata.create_all(bind=engine)
    with Session(engine) as db, db.begin():
        db.add(AuthUser(
            id="existing-commercial", username="comercial-demo", password_hash=hash_password("old-password"),
            permissions=["orders:write"], is_active=True, profile=PlatformProfile.COMMERCIAL.value,
        ))
    engine.dispose()

    credentials_path = tmp_path / "credentials.txt"
    monkeypatch.setattr(sys, "argv", [
        "bootstrap_local_auth.py", "--database-url", database_url,
        "--output", str(credentials_path), "--commercial-username", "comercial-demo",
    ])
    monkeypatch.setattr(bootstrap_local_auth.settings, "APP_ENV", "development")
    monkeypatch.setenv("DOCKER_BOOTSTRAP", "true")
    monkeypatch.setenv("LOCAL_PRESENTATION_ACCOUNTS", "true")
    monkeypatch.setenv("LOCAL_PRESENTATION_PASSWORD", "senha123")

    assert bootstrap_local_auth.main() == 0
    assert "commercial username: comercial-demo" in credentials_path.read_text(encoding="utf-8")
    assert "commercial password: senha123" in credentials_path.read_text(encoding="utf-8")
    assert "senha123" not in capsys.readouterr().out

    verify = create_engine(database_url, execution_options={
        "schema_translate_map": {"gold": None, "gold_v2": None, "gold_cadastro": None}
    })
    try:
        with Session(verify) as db:
            account = db.scalar(select(AuthUser).where(AuthUser.username == "comercial-demo"))
            assert account is not None
            assert verify_password("senha123", account.password_hash)
            assert account.profile == PlatformProfile.COMMERCIAL.value
            assert account.permissions == ["orders:write"]
            assert account.is_active is True
    finally:
        verify.dispose()
