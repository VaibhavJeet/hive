"""
Aging tests (HIVE-022, HIVE-023, HIVE-024).

The product's headline feature has never run.

`age_all_bots` computes `virtual_days = (real_hours / 24) * time_scale` and then did
`virtual_age_days += int(virtual_days)`. At the production `time_scale` of 7, an hourly
cycle yields 0.29 days — and `int(0.29)` is 0. Age never incremented, so no bot ever
changed life stage, aged into elderhood, died of old age, left a legacy, or triggered
elder reproduction.

Demo mode would have masked it (`time_scale` 365 gives 15.2 days/hour), but the demo
switch read `settings.DEMO_MODE`, which does not exist — behind a `hasattr` guard that
turned the typo into a permanent `False`.

And every life event written during aging was discarded: `life_events` was a plain JSON
column, so SQLAlchemy never saw the in-place `append`.
"""

import pytest

from mind.civilization.config import CivilizationConfig
from mind.civilization.models import BotLifecycleDB
from mind.config.settings import settings


# ============================================================================
# HIVE-022 — a full day of hourly cycles must advance a bot by time_scale days
# ============================================================================

def _virtual_days(real_hours: float, time_scale: float) -> float:
    """Mirrors the arithmetic in LifecycleManager.age_all_bots."""
    return (real_hours / 24) * time_scale


def test_one_hourly_cycle_advances_a_fraction_of_a_day():
    """The exact value that used to be truncated to zero."""
    assert _virtual_days(1.0, 7.0) == pytest.approx(0.2916666, rel=1e-4)


def test_truncating_that_value_is_zero():
    """Documents the original bug so its shape is unmistakable."""
    assert int(_virtual_days(1.0, 7.0)) == 0


def test_a_day_of_hourly_cycles_advances_exactly_time_scale_days():
    age = 0.0
    for _ in range(24):
        age += _virtual_days(1.0, 7.0)
    assert age == pytest.approx(7.0, rel=1e-9)


def test_the_column_accepts_fractional_ages():
    """An Integer column would silently round these back."""
    lifecycle = BotLifecycleDB(bot_id=None, virtual_age_days=0.0)
    for _ in range(24):
        lifecycle.virtual_age_days += _virtual_days(1.0, 7.0)
    assert lifecycle.virtual_age_days == pytest.approx(7.0, rel=1e-9)


def test_the_orm_columns_are_float():
    from sqlalchemy import Float

    for column in ("virtual_age_days", "death_age"):
        type_ = BotLifecycleDB.__table__.columns[column].type
        assert isinstance(type_, Float), (
            f"{column} is {type_!r}; an Integer here truncates every aging increment "
            "to zero (HIVE-022)"
        )


# ============================================================================
# HIVE-022 — life stages are actually reached
# ============================================================================

def test_a_bot_reaches_every_life_stage_over_its_lifetime():
    """The end-to-end assertion the task asked for: aging produces stage changes.

    Boundaries are 365 / 1825 / 3650 virtual days, so at `time_scale` 7 a full lifespan
    is ~521 real days. The loop runs long enough to reach `ancient` rather than
    asserting a stage the timescale cannot deliver — my first version stopped at one
    simulated year and failed at `elder`, which was the test being wrong, not the code.
    """
    config = CivilizationConfig()
    age = 0.0
    stages = [config.get_life_stage(age)]

    real_hours = 0
    while stages[-1] != "ancient" and real_hours < 24 * 600:
        age += _virtual_days(1.0, config.time_scale)
        real_hours += 1
        stage = config.get_life_stage(age)
        if stage != stages[-1]:
            stages.append(stage)

    assert stages == ["young", "mature", "elder", "ancient"], (
        f"stage progression was {stages!r} after {age:.0f} virtual days"
    )
    # Sanity-check the real-world duration implied by the default config.
    assert 500 < real_hours / 24 < 540, f"a full lifespan took {real_hours / 24:.0f} real days"


def test_stage_lookup_accepts_a_float():
    """It was annotated `int`; a fractional age must not fall through to 'ancient'."""
    config = CivilizationConfig()
    assert config.get_life_stage(0.5) == config.get_life_stage(0)


# ============================================================================
# HIVE-023 — the demo switch reads a setting that exists
# ============================================================================

def test_the_real_demo_setting_exists():
    assert hasattr(settings, "AUTHENTICITY_DEMO_MODE")


def test_the_typo_setting_does_not_exist():
    """`settings.DEMO_MODE` was read behind a hasattr guard, so it was always False."""
    assert not hasattr(settings, "DEMO_MODE")


def test_activity_engine_reads_the_real_setting():
    import inspect

    from mind.engine.activity_engine import ActivityEngine

    source = inspect.getsource(ActivityEngine._initialize_loops)
    assert "settings.AUTHENTICITY_DEMO_MODE" in source
    assert "hasattr(settings, 'DEMO_MODE')" not in source, (
        "the hasattr guard silently converted a typo into a permanent False"
    )


# ============================================================================
# HIVE-024 — in-place JSON mutation is tracked
# ============================================================================

@pytest.mark.parametrize(
    "column", ["life_events", "relationships", "roles", "inherited_traits", "mutations"]
)
def test_json_columns_track_in_place_mutation(column):
    """`flag_modified` appears nowhere in this codebase, so the columns must be
    mutable-tracked or every append is discarded at commit."""
    from sqlalchemy.ext.mutable import MutableDict, MutableList

    lifecycle = BotLifecycleDB(bot_id=None)
    value = getattr(lifecycle, column, None)
    if value is None:
        value = [] if column in ("life_events", "relationships", "roles") else {}
        setattr(lifecycle, column, value)

    assert isinstance(getattr(lifecycle, column), (MutableList, MutableDict)), (
        f"{column} is a plain container; SQLAlchemy cannot see in-place changes "
        "(HIVE-024)"
    )


def test_appending_a_life_event_is_observable():
    lifecycle = BotLifecycleDB(bot_id=None, life_events=[])
    lifecycle.life_events.append({"event": "entered_mature_stage"})

    assert len(lifecycle.life_events) == 1
    from sqlalchemy.ext.mutable import MutableList

    assert isinstance(lifecycle.life_events, MutableList)
