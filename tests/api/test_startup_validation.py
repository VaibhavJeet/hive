"""
Startup configuration validation (HIVE-019, HIVE-020, HIVE-021).

Hive already contained two config validators — `validate_config_on_startup` in
`mind/config/settings.py` and the 602-line `mind/config/production.py` — and **neither
was ever called**. Every production safety check the codebase implements was dead code:
the default-JWT-secret check, the wildcard-CORS check, the debug-mode check, all of it.

They now run at the top of `lifespan`, before anything expensive starts, and they raise
rather than warn. A production boot with a placeholder signing key should fail loudly,
not serve traffic.
"""

import pytest

from mind.config.production import (
    SecurityLevel,
    validate_on_startup,
    validate_production_config,
)
from mind.config.settings import settings, validate_config_on_startup


@pytest.fixture
def production(monkeypatch):
    """Pretend we are booting in production, with otherwise-sane settings."""
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", "x" * 48)
    monkeypatch.setattr(settings, "CORS_ORIGINS", "https://hive.example.com")
    monkeypatch.setattr(settings, "API_DEBUG", False)
    monkeypatch.setenv("AIC_ENVIRONMENT", "production")


def _critical(report):
    return [i for i in report.issues if i.level == SecurityLevel.CRITICAL]


# ============================================================================
# HIVE-021 — the validators are actually wired in
# ============================================================================

def test_lifespan_calls_both_validators():
    """The whole point of the task: they existed and nothing invoked them."""
    import inspect

    from mind.api import main

    source = inspect.getsource(main.lifespan)
    assert "validate_config_on_startup()" in source
    assert "validate_production()" in source


def test_validators_run_before_the_database_is_touched():
    """A bad config must fail before we start connecting to things."""
    import inspect

    from mind.api import main

    source = inspect.getsource(main.lifespan)
    assert source.index("validate_production()") < source.index("await init_database()")


# ============================================================================
# HIVE-020 — a default JWT secret stops the boot
# ============================================================================

def test_default_jwt_secret_is_critical(production, monkeypatch):
    monkeypatch.setattr(
        settings, "JWT_SECRET_KEY", "your-super-secret-key-change-in-production"
    )
    report = validate_production_config(raise_on_critical=False)

    assert any("JWT secret" in i.message for i in _critical(report))


def test_default_jwt_secret_raises_on_startup(production, monkeypatch):
    monkeypatch.setattr(
        settings, "JWT_SECRET_KEY", "your-super-secret-key-change-in-production"
    )
    with pytest.raises(RuntimeError):
        validate_on_startup()


def test_short_jwt_secret_is_reported(production, monkeypatch):
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", "tooshort")
    report = validate_production_config(raise_on_critical=False)

    assert any("JWT secret" in i.message for i in report.issues)


def test_settings_validator_also_rejects_the_default_secret(production, monkeypatch):
    monkeypatch.setattr(
        settings, "JWT_SECRET_KEY", "your-super-secret-key-change-in-production"
    )
    with pytest.raises(RuntimeError):
        validate_config_on_startup()


# ============================================================================
# HIVE-019 — wildcard CORS stops the boot
# ============================================================================

def test_wildcard_cors_is_critical(production, monkeypatch):
    """CRITICAL, not HIGH: main.py sets allow_credentials=True unconditionally, and
    `*` + credentials is a combination browsers reject — unusable *and* unsafe."""
    monkeypatch.setattr(settings, "CORS_ORIGINS", "*")
    report = validate_production_config(raise_on_critical=False)

    assert any("CORS" in i.message for i in _critical(report)), (
        "wildcard CORS was not critical, so raise_on_critical would not stop the boot"
    )


def test_wildcard_cors_raises_on_startup(production, monkeypatch):
    monkeypatch.setattr(settings, "CORS_ORIGINS", "*")
    with pytest.raises(RuntimeError):
        validate_on_startup()


def test_explicit_origins_are_accepted(production):
    report = validate_production_config(raise_on_critical=False)
    assert not any("CORS" in i.message for i in _critical(report))


# ============================================================================
# The validators must not fire outside production
# ============================================================================

def test_development_boot_is_not_blocked(monkeypatch):
    """Defaults are insecure on purpose in development; that must stay usable."""
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(
        settings, "JWT_SECRET_KEY", "your-super-secret-key-change-in-production"
    )
    monkeypatch.setattr(settings, "CORS_ORIGINS", "*")
    monkeypatch.setenv("AIC_ENVIRONMENT", "development")

    validate_on_startup()          # must not raise
    validate_config_on_startup()   # must not raise


def test_a_clean_production_config_boots(production):
    validate_on_startup()
    validate_config_on_startup()
