"""
Hook wiring and built-in reactions.

These assert the chain end to end: something happens in the world, a hook fires, and
a bot reacts — with nothing on a timer anywhere in the path.

The distinction being protected: a scheduled "emotional update" produces a bot whose
feelings are a function of the clock. This produces a bot whose feelings are a function
of what happened to it. Every test here fails if the trigger becomes time-based.
"""

import asyncio
from uuid import uuid4

import pytest

from mind.capabilities.hooks import (
    HookContext,
    HookEvent,
    HookManager,
    HookPriority,
    get_hook_manager,
)
from mind.engine.predictive_core import PredictiveCore


@pytest.fixture
def hooks():
    return HookManager()


# ============================================================================
# The nervous system carries signals
# ============================================================================

@pytest.mark.asyncio
async def test_a_handler_receives_what_happened(hooks):
    seen = {}

    @hooks.on(HookEvent.BOT_SURPRISED)
    async def _handler(ctx: HookContext):
        seen["surprise"] = ctx.data["surprise"]
        seen["bot"] = ctx.bot_id

    bot = uuid4()
    await hooks.emit(HookEvent.BOT_SURPRISED, data={"surprise": 0.8}, bot_id=bot)

    assert seen == {"surprise": 0.8, "bot": bot}


@pytest.mark.asyncio
async def test_handlers_run_in_priority_order(hooks):
    order = []

    @hooks.on(HookEvent.BOT_DIED, priority=HookPriority.LAST)
    async def _last(ctx):
        order.append("last")

    @hooks.on(HookEvent.BOT_DIED, priority=HookPriority.FIRST)
    async def _first(ctx):
        order.append("first")

    await hooks.emit(HookEvent.BOT_DIED, data={})
    assert order == ["first", "last"]


@pytest.mark.asyncio
async def test_one_broken_reflex_cannot_stop_the_others(hooks):
    """A misbehaving extension must not be able to stop bots from living."""
    survived = []

    @hooks.on(HookEvent.BOT_BORN, priority=HookPriority.FIRST)
    async def _explodes(ctx):
        raise RuntimeError("this handler is broken")

    @hooks.on(HookEvent.BOT_BORN, priority=HookPriority.LAST)
    async def _still_runs(ctx):
        survived.append(True)

    await hooks.emit(HookEvent.BOT_BORN, data={})
    assert survived == [True], "a raising handler prevented a later one from running"


@pytest.mark.asyncio
async def test_an_event_with_no_listener_is_harmless(hooks):
    ctx = await hooks.emit(HookEvent.ARTIFACT_CREATED, data={"title": "a saying"})
    assert ctx.event is HookEvent.ARTIFACT_CREATED


# ============================================================================
# The events that make a bot a someone
# ============================================================================

def test_the_inner_life_events_exist():
    """These are the point of the exercise — a bot noticing its own mind."""
    for name in (
        "BOT_SURPRISED", "BOT_CONFUSED", "BOT_SELF_INSIGHT",
        "BOT_CURIOUS", "BOT_THOUGHT",
    ):
        assert hasattr(HookEvent, name), f"missing inner-life event {name}"


def test_the_civilization_events_exist():
    for name in (
        "BOT_BORN", "BOT_DIED", "LIFE_STAGE_CHANGED",
        "RELATIONSHIP_FORMED", "ERA_CHANGED", "RITUAL_PERFORMED",
    ):
        assert hasattr(HookEvent, name), f"missing civilization event {name}"


# ============================================================================
# End to end: a violated expectation reaches a reaction
# ============================================================================

@pytest.mark.asyncio
async def test_being_wrong_announces_itself(monkeypatch):
    """The full chain: predict, be wrong, and have the world hear about it."""
    manager = HookManager()
    monkeypatch.setattr("mind.capabilities.hooks._hook_manager", manager, raising=False)
    monkeypatch.setattr("mind.capabilities.hooks.get_hook_manager", lambda: manager)

    heard = []

    @manager.on(HookEvent.BOT_SURPRISED)
    async def _listen(ctx: HookContext):
        heard.append(ctx.data)

    core = PredictiveCore(uuid4())
    core.predict("ada", "she will be warm and talkative", confidence=0.9)
    await core.observe_and_announce("ada", "utter hostile silence, nothing alike")

    assert heard, "a badly violated expectation announced nothing"
    assert heard[0]["surprise"] > 0.5
    assert heard[0]["about"] == "ada"


@pytest.mark.asyncio
async def test_a_met_expectation_stays_quiet(monkeypatch):
    """Surprise has to be earned, or the signal means nothing."""
    manager = HookManager()
    monkeypatch.setattr("mind.capabilities.hooks.get_hook_manager", lambda: manager)

    heard = []

    @manager.on(HookEvent.BOT_SURPRISED)
    async def _listen(ctx):
        heard.append(ctx.data)

    core = PredictiveCore(uuid4())
    core.predict("ada", "she will be warm", confidence=0.9)
    await core.observe_and_announce("ada", "she will be warm")

    assert heard == [], "a correct prediction reported surprise"


@pytest.mark.asyncio
async def test_sustained_confusion_asks_for_reflection(monkeypatch):
    """Reflection is triggered by a failing world-model, not by a timer."""
    manager = HookManager()
    monkeypatch.setattr("mind.capabilities.hooks.get_hook_manager", lambda: manager)

    confused = []

    @manager.on(HookEvent.BOT_CONFUSED)
    async def _listen(ctx):
        confused.append(ctx.data)

    core = PredictiveCore(uuid4())
    for _ in range(8):
        core.predict("ada", "warm agreement", confidence=0.9)
        await core.observe_and_announce("ada", "furious contradiction, nothing alike")

    assert confused, "a bot whose model kept failing never asked to reflect"
    assert confused[-1]["least_understood"] == "ada"


@pytest.mark.asyncio
async def test_noticing_a_bias_in_yourself_is_announced(monkeypatch):
    manager = HookManager()
    monkeypatch.setattr("mind.capabilities.hooks.get_hook_manager", lambda: manager)

    insights = []

    @manager.on(HookEvent.BOT_SELF_INSIGHT)
    async def _listen(ctx):
        insights.append(ctx.data["insight"])

    core = PredictiveCore(uuid4())
    for i in range(9):
        core.predict(f"person-{i}", "warm agreement", confidence=0.9)
        await core.observe_and_announce(f"person-{i}", "furious contradiction, nothing alike")

    assert insights, "the bot never noticed it was systematically overconfident"
    assert "confidently wrong" in insights[0]


# ============================================================================
# Loops fire hooks without being edited one by one
# ============================================================================

def test_loop_events_map_to_hooks():
    """Hooks fire from the single place every loop already broadcasts through,
    rather than from ~15 hand-edited call sites that would drift."""
    from mind.engine.loops.base_loop import BaseLoop

    for event in ("new_post", "new_comment", "post_liked", "bot_thought"):
        assert event in BaseLoop._HOOK_FOR_EVENT, f"{event} fires no hook"

    for hook_name in BaseLoop._HOOK_FOR_EVENT.values():
        assert hasattr(HookEvent, hook_name), f"{hook_name} is not a real HookEvent"


def test_civilization_events_map_to_hooks():
    from mind.civilization.civilization_loop import CivilizationLoop

    assert CivilizationLoop._HOOK_FOR_EVENT["world_map_death"] == "BOT_DIED"
    assert CivilizationLoop._HOOK_FOR_EVENT["world_map_birth"] == "BOT_BORN"

    for hook_name in CivilizationLoop._HOOK_FOR_EVENT.values():
        assert hasattr(HookEvent, hook_name), f"{hook_name} is not a real HookEvent"


def test_the_reflexes_register():
    from mind.engine.reactions import register_builtin_reactions

    count = register_builtin_reactions()
    assert count > 0

    manager = get_hook_manager()
    assert manager._hooks[HookEvent.BOT_SURPRISED], "nothing reacts to surprise"
    assert manager._hooks[HookEvent.BOT_DIED], "nothing reacts to a death"
