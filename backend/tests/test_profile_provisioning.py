import sys

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.database import Base
from app.models.auth import AuthUser
from scripts import bootstrap_local_auth
from scripts import set_user_profile


def test_profile_assignment_preserves_existing_password_and_legacy_permissions(tmp_path, monkeypatch, capsys):
    database_url = f"sqlite:///{(tmp_path / 'profile-assignment.sqlite').as_posix()}"
    engine = create_engine(
        database_url,
        execution_options={"schema_translate_map": {"gold": None, "gold_v2": None}},
    )
    Base.metadata.create_all(bind=engine)
    with engine.begin() as connection:
        connection.execute(
            AuthUser.__table__.insert().values(
                id="existing", username="existing", password_hash="keep-this-hash",
                permissions=["orders:write"], is_active=True, profile=None,
            )
        )
    engine.dispose()

    monkeypatch.setattr(
        sys,
        "argv",
        ["set_user_profile.py", "--database-url", database_url, "--username", "existing", "--profile", "admin"],
    )
    assert set_user_profile.main() == 0
    assert "profile=null->admin" in capsys.readouterr().out

    verify = create_engine(
        database_url,
        execution_options={"schema_translate_map": {"gold": None, "gold_v2": None}},
    )
    try:
        with Session(verify) as db:
            user = db.scalar(select(AuthUser).where(AuthUser.id == "existing"))
            assert user is not None
            assert user.password_hash == "keep-this-hash"
            assert user.permissions == ["orders:write"]
            assert user.profile == "admin"
    finally:
        verify.dispose()


def test_bootstrap_does_not_promote_or_reset_existing_profileless_account(tmp_path, monkeypatch, capsys):
    database_url = f"sqlite:///{(tmp_path / 'bootstrap.sqlite').as_posix()}"
    credentials_path = tmp_path / "credentials.txt"
    engine = create_engine(
        database_url,
        execution_options={"schema_translate_map": {"gold": None, "gold_v2": None}},
    )
    Base.metadata.create_all(bind=engine)
    with engine.begin() as connection:
        connection.execute(
            AuthUser.__table__.insert().values(
                id="existing", username="losses", password_hash="existing-hash",
                permissions=["orders:write"], is_active=True, profile=None,
            )
        )
    engine.dispose()

    monkeypatch.setattr(
        sys,
        "argv",
        ["bootstrap_local_auth.py", "--database-url", database_url, "--output", str(credentials_path)],
    )
    assert bootstrap_local_auth.main() == 0
    capsys.readouterr()
    assert "losses username: losses" not in credentials_path.read_text(encoding="utf-8")
    verify = create_engine(
        database_url,
        execution_options={"schema_translate_map": {"gold": None, "gold_v2": None}},
    )
    try:
        with Session(verify) as db:
            existing = db.get(AuthUser, "existing")
            assert existing is not None
            assert existing.password_hash == "existing-hash"
            assert existing.permissions == ["orders:write"]
            assert existing.profile is None
    finally:
        verify.dispose()
