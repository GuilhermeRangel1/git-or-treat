

def test_unknown_analytics_source_configuration_is_rejected():
    import pytest
    from pydantic import ValidationError

    from app.core.config import Settings

    with pytest.raises(ValidationError):
        Settings(ANALYTICS_SOURCE="postgres", _env_file=None)
