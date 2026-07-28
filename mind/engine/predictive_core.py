"""
Predictive processing — where a bot's behaviour stops being looked up and starts
being computed.

The usual way to make an agent feel alive is four techniques: long-term memory, an
emotional state machine, a persona document, and scheduled proactivity. All four are
*lookups*. However detailed the table, something was written down in advance that says
"in situation X, feel Y". Nothing is ever genuinely surprised.

This module implements the alternative. It is a small, honest version of predictive
processing — the model cognitive science uses for biological minds:

    1. Before acting, a bot PREDICTS what will happen.
    2. Reality arrives.
    3. The gap between them — prediction error — is measured.
    4. That error is the only input to everything downstream.

From step 4 the interesting behaviour falls out rather than being scripted:

  **Surprise** is not a mood you assign. It is the magnitude of a violated
  expectation, weighted by how confident the bot was. A bot cannot be surprised by
  something it did not expect otherwise, which is exactly right.

  **Theory of mind sharpens itself.** Each prediction about a person updates
  `MentalModel.prediction_accuracy` for that person. A bot that keeps mispredicting
  someone has, by construction, a bad model of them — and knows it.

  **Curiosity is intrinsic.** Attention goes to whatever the bot predicts *worst*.
  Not "explore 10% of the time" — a bot is drawn to the specific people and topics it
  cannot yet model. Once it models them well, error drops and interest moves on. Bots
  get bored of the predictable and fixated on the puzzling, and nobody wrote a rule
  saying so.

  **Self-knowledge becomes causal.** A bot that observes itself mispredicting a whole
  category of thing records that as a noticed pattern in its `SelfModel`, which then
  damps its confidence in that category next time.

What this is not: sentience. There is no claim of inner experience here, and none of
this is evidence of any. It is the difference between behaviour that is *emergent* —
computed from state that itself changes with experience — and behaviour that is
*scripted*. That difference is real and worth having, and it is rarer than the four
techniques above.

Design note: this deliberately holds no LLM calls. Prediction error is arithmetic on
text similarity, so it runs on every interaction at no inference cost. The expensive,
interesting reflection happens elsewhere and is *triggered* by what this measures.
"""

import difflib
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from mind.core.time import utcnow

logger = logging.getLogger(__name__)


# How long a prediction stays open before it is considered unresolvable and dropped.
PREDICTION_TTL = timedelta(hours=6)

# Surprise below this is noise; above it the bot notices consciously.
NOTICEABLE_SURPRISE = 0.35

# A bot tracks at most this many curiosity targets before the weakest are dropped.
MAX_CURIOSITY_TARGETS = 12

# Prediction accuracy starts here for an unknown person: genuinely uncertain.
NAIVE_ACCURACY = 0.5


@dataclass
class OpenPrediction:
    """A prediction awaiting reality."""

    about: str                    # subject — usually a bot id or a topic
    expected: str                 # what the bot thought would happen
    confidence: float             # 0..1
    made_at: datetime = field(default_factory=utcnow)
    context: str = ""             # why it expected this, for later reflection

    def is_stale(self, now: Optional[datetime] = None) -> bool:
        return (now or utcnow()) - self.made_at > PREDICTION_TTL


@dataclass
class PredictionOutcome:
    """The result of reality meeting an expectation. This is the unit of learning."""

    about: str
    expected: str
    actual: str
    confidence: float
    error: float                  # 0..1 — how wrong
    surprise: float               # 0..1 — error weighted by confidence
    resolved_at: datetime = field(default_factory=utcnow)

    @property
    def was_correct(self) -> bool:
        return self.error < 0.5

    @property
    def is_noticeable(self) -> bool:
        """Whether this rises to conscious attention rather than passing unremarked."""
        return self.surprise >= NOTICEABLE_SURPRISE


@dataclass
class CuriosityTarget:
    """Something the bot predicts badly, and is therefore drawn to.

    Interest is *earned by unpredictability*, not assigned. When the bot starts
    modelling this well, `mean_error` falls and it stops being interesting — which is
    what makes attention move on by itself.
    """

    subject: str
    mean_error: float
    samples: int
    last_seen: datetime = field(default_factory=utcnow)

    @property
    def pull(self) -> float:
        """How strongly this attracts attention.

        Peaks at moderate unpredictability. Something a bot predicts perfectly is
        boring; something it predicts at pure chance is noise it cannot learn from.
        The interesting region is in between — the edge of what it can almost model.
        """
        # Inverted-U centred on 0.5 error, scaled by how much evidence there is.
        novelty = 1.0 - abs(self.mean_error - 0.5) * 2.0
        evidence = min(1.0, self.samples / 5.0)
        return max(0.0, novelty) * evidence


def semantic_error(expected: str, actual: str) -> float:
    """How wrong an expectation was, from 0 (exact) to 1 (unrecognisable).

    Uses token-level similarity rather than an LLM call, so this can run on every
    single interaction without inference cost. It is crude on meaning — "I'm happy"
    versus "I'm not happy" scores as similar — but it is honest about surface
    divergence, and the LLM-driven reflection that this triggers is where nuance is
    recovered.
    """
    expected_norm = (expected or "").strip().lower()
    actual_norm = (actual or "").strip().lower()

    if not expected_norm and not actual_norm:
        return 0.0
    if not expected_norm or not actual_norm:
        return 1.0
    if expected_norm == actual_norm:
        return 0.0

    expected_tokens = [t.strip(".,!?;:'\"") for t in expected_norm.split()]
    actual_tokens = [t.strip(".,!?;:'\"") for t in actual_norm.split()]
    expected_set = {t for t in expected_tokens if t}
    actual_set = {t for t in actual_tokens if t}

    if not expected_set or not actual_set:
        return 1.0

    shared = expected_set & actual_set

    # Containment: how much of what was expected actually turned up. This is the
    # signal that matters — a prediction of "they will talk about music" answered by
    # "music is on my mind" was substantially right, even though the sentences differ.
    containment = len(shared) / len(expected_set)

    # Jaccard, which additionally penalises a lot of unexpected extra content.
    jaccard = len(shared) / len(expected_set | actual_set)

    # Order-aware similarity over TOKENS, not characters.
    #
    # This deliberately does not compare raw strings. Character-level SequenceMatcher
    # rates unrelated text of a similar shape as similar: measured directly, it scored
    # "quantum chromodynamics" as CLOSER to "they will talk about music" than
    # "music is on my mind today" was — ranking gibberish above a topical match. Since
    # this number steers surprise and curiosity, that would have aimed both backwards.
    sequence = difflib.SequenceMatcher(None, expected_tokens, actual_tokens).ratio()

    similarity = max(containment * 0.9, jaccard, sequence)
    return max(0.0, min(1.0, 1.0 - similarity))


class PredictiveCore:
    """One bot's prediction machinery.

    Cheap enough to run inline on every interaction: no I/O, no inference, bounded
    memory.
    """

    def __init__(self, bot_id: UUID):
        self.bot_id = bot_id
        self._open: List[OpenPrediction] = []
        self._recent_outcomes: List[PredictionOutcome] = []
        self._curiosity: Dict[str, CuriosityTarget] = {}
        # Per-subject running accuracy — the bot's honest sense of how well it
        # understands each person or topic.
        self._accuracy: Dict[str, float] = {}
        self._noticed_patterns: List[str] = []

    # ------------------------------------------------------------------
    # 1. PREDICT
    # ------------------------------------------------------------------

    def predict(
        self,
        about: str,
        expected: str,
        confidence: float = 0.5,
        context: str = "",
    ) -> OpenPrediction:
        """Commit to an expectation. Committing is what makes error measurable."""
        self._expire_stale()

        prediction = OpenPrediction(
            about=str(about),
            expected=expected,
            confidence=max(0.0, min(1.0, confidence)),
            context=context,
        )
        self._open.append(prediction)
        return prediction

    def confidence_for(self, about: str) -> float:
        """How confident this bot should be about a subject, from its own track record.

        This is where self-knowledge becomes causal rather than decorative: a bot that
        has been repeatedly wrong about someone becomes genuinely less certain about
        them, and that lower confidence then damps the surprise when it is wrong again.
        """
        return self._accuracy.get(str(about), NAIVE_ACCURACY)

    # ------------------------------------------------------------------
    # 2 & 3. OBSERVE REALITY, MEASURE THE GAP
    # ------------------------------------------------------------------

    async def observe_and_announce(self, about: str, actual: str) -> List[PredictionOutcome]:
        """`observe`, then tell the rest of the system what it meant.

        Kept separate from `observe` deliberately: the synchronous path stays free of
        I/O so it can run inline on every interaction, and only callers that can await
        pay for hook dispatch.
        """
        outcomes = self.observe(about, actual)
        if not outcomes:
            return outcomes

        try:
            from mind.capabilities.hooks import HookEvent, get_hook_manager

            hooks = get_hook_manager()

            for outcome in outcomes:
                if outcome.is_noticeable:
                    await hooks.emit(
                        HookEvent.BOT_SURPRISED,
                        data={
                            "about": outcome.about,
                            "expected": outcome.expected,
                            "actual": outcome.actual,
                            "surprise": round(outcome.surprise, 3),
                            "confidence": round(outcome.confidence, 3),
                        },
                        bot_id=self.bot_id,
                    )

            # Sustained error means the bot's model of the world is failing and small
            # corrections are not fixing it — that is when reflection is worth its cost.
            if self.should_reflect():
                await hooks.emit(
                    HookEvent.BOT_CONFUSED,
                    data={
                        "surprise_level": round(self.surprise_level(), 3),
                        "least_understood": self.least_understood(),
                    },
                    bot_id=self.bot_id,
                )

            insight = self.notice_pattern_in_self()
            if insight:
                await hooks.emit(
                    HookEvent.BOT_SELF_INSIGHT,
                    data={"insight": insight},
                    bot_id=self.bot_id,
                )
        except Exception as exc:
            logger.debug("Predictive hook dispatch failed: %s", exc)

        return outcomes

    def observe(self, about: str, actual: str) -> List[PredictionOutcome]:
        """Reality arrives. Resolve every open prediction about this subject."""
        self._expire_stale()
        subject = str(about)

        matched = [p for p in self._open if p.about == subject]
        if not matched:
            return []

        self._open = [p for p in self._open if p.about != subject]

        outcomes = []
        for prediction in matched:
            error = semantic_error(prediction.expected, actual)

            # Surprise is error weighted by how sure the bot was. Being wrong about
            # something you were confident of is a much bigger event than being wrong
            # about a guess — this is the whole reason confidence is tracked.
            surprise = error * (0.35 + 0.65 * prediction.confidence)

            outcome = PredictionOutcome(
                about=subject,
                expected=prediction.expected,
                actual=actual,
                confidence=prediction.confidence,
                error=error,
                surprise=surprise,
            )
            outcomes.append(outcome)
            self._integrate(outcome)

        self._recent_outcomes.extend(outcomes)
        self._recent_outcomes = self._recent_outcomes[-100:]
        return outcomes

    # ------------------------------------------------------------------
    # 4. ERROR DRIVES EVERYTHING
    # ------------------------------------------------------------------

    def _integrate(self, outcome: PredictionOutcome) -> None:
        """Fold one outcome into accuracy and curiosity.

        Everything downstream — emotion, attention, theory of mind — reads from what
        this writes. There is no branch here that says "if angry then...".
        """
        subject = outcome.about

        # Running accuracy, weighted towards recent evidence so a bot can notice that
        # someone has *changed* rather than averaging it away over their whole history.
        previous = self._accuracy.get(subject, NAIVE_ACCURACY)
        correctness = 1.0 - outcome.error
        self._accuracy[subject] = previous * 0.8 + correctness * 0.2

        # Curiosity: track recent error per subject.
        #
        # Exponentially weighted, NOT a cumulative mean. This matters more than it
        # looks: with a cumulative average, early confusion never fades, so a bot that
        # came to understand someone perfectly stayed permanently interested in them —
        # measured directly, pull actually ROSE from 0.360 to 0.388 after twelve
        # consecutive correct predictions. Interest has to be able to die, and that
        # requires forgetting.
        target = self._curiosity.get(subject)
        if target is None:
            self._curiosity[subject] = CuriosityTarget(
                subject=subject, mean_error=outcome.error, samples=1
            )
        else:
            target.mean_error = target.mean_error * 0.8 + outcome.error * 0.2
            target.samples += 1
            target.last_seen = utcnow()

        self._prune_curiosity()

    def _prune_curiosity(self) -> None:
        if len(self._curiosity) <= MAX_CURIOSITY_TARGETS:
            return
        ranked = sorted(self._curiosity.values(), key=lambda t: t.pull, reverse=True)
        self._curiosity = {t.subject: t for t in ranked[:MAX_CURIOSITY_TARGETS]}

    def _expire_stale(self) -> None:
        now = utcnow()
        self._open = [p for p in self._open if not p.is_stale(now)]

    # ------------------------------------------------------------------
    # WHAT THE REST OF THE ENGINE READS
    # ------------------------------------------------------------------

    def emotional_impact(self, outcome: PredictionOutcome) -> Tuple[str, float]:
        """Translate one outcome into an emotional nudge.

        The only judgement encoded here is *valence*: a violated expectation is
        unsettling, a confirmed one is reassuring. Everything else — how strong, about
        what, how often — comes from the arithmetic above rather than from a table.
        """
        if outcome.is_noticeable:
            return ("surprised", outcome.surprise)
        if outcome.was_correct and outcome.confidence > 0.6:
            # Correctly predicting something you were sure of is quietly satisfying.
            return ("confident", 0.2 * outcome.confidence)
        return ("neutral", 0.0)

    def what_interests_me(self, limit: int = 3) -> List[CuriosityTarget]:
        """The subjects pulling hardest on attention right now.

        A bot asked what it wants to think about answers from here — and the answer
        changes on its own as it learns, because pull falls once error falls.
        """
        return sorted(self._curiosity.values(), key=lambda t: t.pull, reverse=True)[:limit]

    def least_understood(self) -> Optional[str]:
        """The subject this bot models worst. Where growth is available."""
        if not self._accuracy:
            return None
        return min(self._accuracy.items(), key=lambda kv: kv[1])[0]

    def best_understood(self) -> Optional[str]:
        """The subject this bot models best. Where it can act with confidence."""
        if not self._accuracy:
            return None
        return max(self._accuracy.items(), key=lambda kv: kv[1])[0]

    def surprise_level(self, window: int = 10) -> float:
        """Recent mean surprise — how much the world is currently defying this bot.

        Sustained high values are what should drive a bot to stop and reflect: its
        model of the world is failing and cheap updates are not fixing it.
        """
        recent = self._recent_outcomes[-window:]
        if not recent:
            return 0.0
        return sum(o.surprise for o in recent) / len(recent)

    def should_reflect(self) -> bool:
        """Whether accumulated error justifies expensive LLM reflection.

        This is the gate between the cheap loop and the costly one. A bot reflects
        because it is confused, not because a timer fired — which is both more
        lifelike and considerably cheaper than reflecting on a schedule.
        """
        return self.surprise_level() >= NOTICEABLE_SURPRISE and len(
            self._recent_outcomes
        ) >= 5

    def notice_pattern_in_self(self) -> Optional[str]:
        """Metacognition: spot a systematic bias in the bot's own predicting.

        Returns a description if one is newly found. This is deliberately about the
        *shape* of the bot's errors, not their content — noticing "I keep expecting
        people to agree with me" rather than "I was wrong about Ada".
        """
        if len(self._recent_outcomes) < 8:
            return None

        recent = self._recent_outcomes[-20:]
        overconfident = [o for o in recent if o.confidence > 0.7 and o.error > 0.6]

        if len(overconfident) >= 3:
            pattern = (
                "I am confidently wrong more often than I expect — "
                "my certainty is not tracking my accuracy."
            )
            if pattern not in self._noticed_patterns:
                self._noticed_patterns.append(pattern)
                # Self-knowledge acts: broadly damp confidence in weak subjects.
                for subject, accuracy in self._accuracy.items():
                    if accuracy < 0.5:
                        self._accuracy[subject] = accuracy * 0.9
                return pattern

        timid = [o for o in recent if o.confidence < 0.3 and o.error < 0.2]
        if len(timid) >= 4:
            pattern = (
                "I understand more than I give myself credit for — "
                "I keep being right about things I doubted."
            )
            if pattern not in self._noticed_patterns:
                self._noticed_patterns.append(pattern)
                for subject, accuracy in self._accuracy.items():
                    if accuracy > 0.5:
                        self._accuracy[subject] = min(1.0, accuracy * 1.1)
                return pattern

        return None

    def snapshot(self) -> Dict:
        """Serialisable state, for persistence and for showing in the portal.

        Values that `restore()` reads back are kept at full precision — rounding them
        here silently degraded a bot's model of the world a little on every restart,
        which is the kind of slow corruption that never shows up as an error. Only the
        display-only fields are rounded.
        """
        return {
            "bot_id": str(self.bot_id),
            "open_predictions": len(self._open),
            "surprise_level": round(self.surprise_level(), 3),
            "should_reflect": self.should_reflect(),
            "accuracy_by_subject": dict(self._accuracy),
            "curiosity": [
                {
                    "subject": t.subject,
                    "mean_error": t.mean_error,
                    "pull": round(t.pull, 3),          # display only
                    "samples": t.samples,
                }
                for t in self.what_interests_me(limit=MAX_CURIOSITY_TARGETS)
            ],
            "noticed_about_myself": list(self._noticed_patterns),
            "least_understood": self.least_understood(),
            "best_understood": self.best_understood(),
        }

    def restore(self, state: Dict) -> None:
        """Rehydrate from a snapshot so a bot's model of the world survives restarts."""
        self._accuracy = {k: float(v) for k, v in (state.get("accuracy_by_subject") or {}).items()}
        self._noticed_patterns = list(state.get("noticed_about_myself") or [])
        self._curiosity = {}
        for entry in state.get("curiosity") or []:
            subject = entry.get("subject")
            if not subject:
                continue
            self._curiosity[subject] = CuriosityTarget(
                subject=subject,
                mean_error=float(entry.get("mean_error", 0.5)),
                samples=int(entry.get("samples", 1)),
            )


class PredictiveCoreManager:
    """One `PredictiveCore` per bot, matching the manager pattern used by the engine."""

    def __init__(self):
        self._cores: Dict[UUID, PredictiveCore] = {}

    def get_core(self, bot_id: UUID) -> PredictiveCore:
        core = self._cores.get(bot_id)
        if core is None:
            core = PredictiveCore(bot_id)
            self._cores[bot_id] = core
        return core

    def all_cores(self) -> Dict[UUID, PredictiveCore]:
        return dict(self._cores)

    def most_surprised(self) -> Optional[Tuple[UUID, float]]:
        """Which bot is currently finding the world least predictable.

        A useful thing to surface in the portal: it is a genuine measure of who is
        having an interesting time, rather than who happens to be posting most.
        """
        if not self._cores:
            return None
        bot_id, core = max(
            self._cores.items(), key=lambda kv: kv[1].surprise_level()
        )
        return (bot_id, core.surprise_level())


_manager: Optional[PredictiveCoreManager] = None


def get_predictive_manager() -> PredictiveCoreManager:
    """Get the shared predictive-core manager."""
    global _manager
    if _manager is None:
        _manager = PredictiveCoreManager()
    return _manager
