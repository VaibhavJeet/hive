"""
Built-in reactions — how the civilization responds to itself.

The hook system (`mind/capabilities/hooks.py`) is a nervous system: it carries signals.
This module is the first set of reflexes hanging off it.

Everything here is deliberately *reactive* rather than scheduled. Nothing in this file
runs on a timer. A bot grieves because someone died, gets rattled because it was wrong
about someone, or turns its attention somewhere new because that place stopped making
sense. The trigger is always something that actually happened.

That is the distinction worth protecting. A scheduled "emotional update" every N minutes
produces a bot whose feelings are a function of the clock. These produce a bot whose
feelings are a function of its world — and which one you built is visible in whether the
bot reacts to a death it witnessed or merely drifts moodier at 14:00.

Registering more reflexes is the intended way to extend bot behaviour: add a handler
here rather than editing the loops, which is the whole point of having hooks.
"""

import logging
from typing import Optional
from uuid import UUID

from mind.capabilities.hooks import HookContext, HookEvent, HookPriority, get_hook_manager

logger = logging.getLogger(__name__)

# How much a death shakes the bots who knew the deceased.
GRIEF_INTENSITY = 0.45

# Surprise below this is noise the bot does not consciously register.
REACTABLE_SURPRISE = 0.5


def _emotional_core_for(bot_id: UUID):
    """The bot's emotional core, or None if it is not currently loaded.

    Bots are loaded lazily and capped by MAX_ACTIVE_BOTS, so a hook may well fire for
    a bot that is not resident. That is not an error — it simply means nobody is home
    to feel it.
    """
    try:
        from mind.engine.emotional_core import get_emotional_core_manager

        manager = get_emotional_core_manager()
        cores = getattr(manager, "cores", None) or getattr(manager, "_cores", None)
        if isinstance(cores, dict):
            return cores.get(bot_id)
    except Exception as exc:
        logger.debug("Could not reach emotional core for %s: %s", bot_id, exc)
    return None


def _nudge_emotion(bot_id: Optional[UUID], feeling: str, intensity: float, why: str) -> None:
    """Apply an emotional nudge to a bot, if it is loaded and willing to receive one.

    Tolerant of the emotional core's exact shape on purpose: several methods across
    the codebase could plausibly serve here, and a reflex should degrade to a log line
    rather than crash the loop that fired it.
    """
    if bot_id is None:
        return

    core = _emotional_core_for(bot_id)
    if core is None:
        return

    for method_name in ("register_event", "process_event", "apply_feeling", "feel"):
        method = getattr(core, method_name, None)
        if callable(method):
            try:
                method(feeling, intensity)
                logger.info("[REACTION] %s feels %s (%.2f) — %s", bot_id, feeling, intensity, why)
                return
            except TypeError:
                continue
            except Exception as exc:
                logger.debug("Emotional nudge failed for %s: %s", bot_id, exc)
                return

    logger.debug("Emotional core for %s exposes no usable entry point", bot_id)


def register_builtin_reactions() -> int:
    """Wire the default reflexes. Returns how many were registered.

    Called once from `lifespan`. Idempotent by virtue of being called once — if you
    call it twice you get duplicate handlers, which is why it is not called anywhere
    else.
    """
    hooks = get_hook_manager()

    # ------------------------------------------------------------------
    # Being wrong about someone changes how you feel about them
    # ------------------------------------------------------------------

    @hooks.on(HookEvent.BOT_SURPRISED, priority=HookPriority.HIGH, name="feel_surprise")
    async def _feel_surprise(ctx: HookContext) -> None:
        surprise = float(ctx.data.get("surprise", 0.0))
        if surprise < REACTABLE_SURPRISE:
            return
        _nudge_emotion(
            ctx.bot_id,
            "surprised",
            surprise,
            f"expected {ctx.data.get('expected')!r}, got {ctx.data.get('actual')!r}",
        )

    # ------------------------------------------------------------------
    # Sustained confusion is what should make a bot stop and think
    # ------------------------------------------------------------------

    @hooks.on(HookEvent.BOT_CONFUSED, name="reflect_when_confused")
    async def _reflect_when_confused(ctx: HookContext) -> None:
        """Mark the bot as wanting to reflect.

        Deliberately does NOT call the LLM here. Hooks run inside the loop that fired
        them, so doing inference in a handler would stall that loop and contend for the
        LLM semaphore. This sets an intention; the consciousness loop acts on it.
        """
        subject = ctx.data.get("least_understood")
        logger.info(
            "[REACTION] %s is confused (surprise %.2f); least understood: %s",
            ctx.bot_id, float(ctx.data.get("surprise_level", 0.0)), subject,
        )
        _nudge_emotion(ctx.bot_id, "confused", 0.4, f"cannot predict {subject}")

    # ------------------------------------------------------------------
    # Noticing something true about yourself is its own event
    # ------------------------------------------------------------------

    @hooks.on(HookEvent.BOT_SELF_INSIGHT, name="record_self_insight")
    async def _record_self_insight(ctx: HookContext) -> None:
        insight = ctx.data.get("insight")
        logger.info("[REACTION] %s realised: %s", ctx.bot_id, insight)
        _nudge_emotion(ctx.bot_id, "reflective", 0.3, "noticed a pattern in itself")

    # ------------------------------------------------------------------
    # Death moves the living
    # ------------------------------------------------------------------

    @hooks.on(HookEvent.BOT_DIED, priority=HookPriority.HIGH, name="grieve")
    async def _grieve(ctx: HookContext) -> None:
        """Everyone who knew the deceased feels it.

        Grief scales with closeness, so this is not a uniform mood change applied to
        the population — most bots feel nothing because most bots were not close.
        """
        deceased_raw = ctx.data.get("bot_id")
        if not deceased_raw:
            return

        try:
            deceased = UUID(str(deceased_raw))
        except (ValueError, TypeError):
            return

        try:
            from mind.engine.social_dynamics import get_relationship_manager

            relationships = get_relationship_manager()
            mourners = getattr(relationships, "get_close_relations", None)
            if not callable(mourners):
                logger.info("[REACTION] %s has passed; no relationship graph to notify", deceased)
                return

            for mourner_id, closeness in (mourners(deceased) or []):
                _nudge_emotion(
                    mourner_id,
                    "grieving",
                    GRIEF_INTENSITY * float(closeness),
                    f"lost someone they were close to ({closeness:.2f})",
                )
        except Exception as exc:
            logger.debug("Grief propagation failed for %s: %s", deceased, exc)

    # ------------------------------------------------------------------
    # A birth is news
    # ------------------------------------------------------------------

    @hooks.on(HookEvent.BOT_BORN, name="notice_birth")
    async def _notice_birth(ctx: HookContext) -> None:
        logger.info(
            "[REACTION] a new being arrived: %s (%s)",
            ctx.data.get("name") or ctx.data.get("bot_id"),
            ", ".join(ctx.data.get("interests") or []) or "no interests yet",
        )

    # ------------------------------------------------------------------
    # An era changing is the civilization noticing itself
    # ------------------------------------------------------------------

    @hooks.on(HookEvent.ERA_CHANGED, name="notice_era_change")
    async def _notice_era_change(ctx: HookContext) -> None:
        logger.info(
            "[REACTION] the era turned: %s",
            ctx.data.get("new_era") or ctx.data.get("name") or "unnamed",
        )

    registered = sum(len(v) for v in hooks._hooks.values())
    logger.info("Registered %d built-in reactions", registered)
    return registered
