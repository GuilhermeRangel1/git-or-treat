"""Core configuration and database connectivity, imported on demand."""

from importlib import import_module

__all__ = ["settings", "Base", "engine", "get_db", "SessionLocal"]


def __getattr__(name: str):
    if name == "settings":
        return import_module("app.core.config").settings
    if name in {"Base", "engine", "get_db", "SessionLocal"}:
        return getattr(import_module("app.core.database"), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
