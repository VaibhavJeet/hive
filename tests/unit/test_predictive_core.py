"""
Predictive core tests.

These assert the claims that distinguish emergent behaviour from a state machine.
Each test is written so that it could only pass if the behaviour is *computed* — none
of them would hold for a lookup table, because nothing in the module says "if bored
then move on" or "if wrong then feel surprised".
"""

from uuid import uuid4

import pytest

from mind.engine.predictive_core import (
    NOTICEABLE_SURPRISE,
    PredictiveCore,
    PredictiveCoreManager,
    get_predictive_manager,
    semantic_error,
)


@pytest.fixture
def core():
    return PredictiveCore(uuid4())


# ============================================================================
# Measuring the gap
# ============================================================================

def test_an_exact_expectation_has_no_error():
    assert semantic_error("they will talk about music", "they will talk about music") == 0.0


def test_an_unrelated_outcome_is_maximally_wrong():
    assert semantic_error("they will be cheerful", "quantum chromodynamics") > 0.7


def test_partial_overlap_is_partial_error():
    """Shared wording earns partial credit — but only partial.

    Calibrated against real output rather than assumed: token-level overlap on one word
    out of six scores ~0.80, which is correctly "mostly wrong". A closer paraphrase
    scores much lower, asserted below.
    """
    loose = semantic_error("they will talk about music", "music is on my mind today")
    close = semantic_error("she will be warm", "she will be warm today")
    unrelated = semantic_error("they will talk about music", "quantum chromodynamics")

    assert close < loose < unrelated, f"{close} < {loose} < {unrelated}"
    assert close < 0.4, "a near-paraphrase should be scored as largely right"


def test_an_empty_outcome_is_total_error():
    assert semantic_error("something", "") == 1.0


# ============================================================================
# Surprise is earned, not assigned
# ============================================================================

def test_being_wrong_about_something_you_were_sure_of_hurts_more(core):
    """Identical wording for both, so the ONLY variable is confidence."""
    core.predict("ada", "they will agree", confidence=0.95)
    confident = core.observe("ada", "they flatly refused")[0]

    core.predict("bo", "they will agree", confidence=0.1)
    guess = core.observe("bo", "they flatly refused")[0]

    assert confident.error == guess.error, (
        "same words, so the same wrongness — any difference must come from confidence"
    )
    assert confident.surprise > guess.surprise * 1.5


def test_a_bot_cannot_be_surprised_by_what_it_never_expected(core):
    """No prediction, no surprise. This is the property a mood table cannot express."""
    outcomes = core.observe("someone", "an extraordinary and shocking event")
    assert outcomes == []


def test_confirmed_expectations_do_not_register_as_surprise(core):
    core.predict("ada", "she will talk about music", confidence=0.8)
    outcome = core.observe("ada", "she will talk about music")[0]

    assert outcome.was_correct
    assert not outcome.is_noticeable
    mood, strength = core.emotional_impact(outcome)
    assert mood == "confident"
    assert strength > 0


def test_a_violated_expectation_becomes_surprise(core):
    core.predict("ada", "she will be warm", confidence=0.9)
    outcome = core.observe("ada", "utterly hostile and dismissive")[0]

    mood, strength = core.emotional_impact(outcome)
    assert mood == "surprised"
    assert strength >= NOTICEABLE_SURPRISE


# ============================================================================
# Curiosity moves on by itself
# ============================================================================

def test_a_bot_loses_interest_in_someone_it_has_learned_to_predict(core):
    """The claim: boredom is not scheduled, it falls out of error dropping."""
    # Early on, this person is baffling.
    for _ in range(4):
        core.predict("ada", "she will be cheerful", confidence=0.5)
        core.observe("ada", "she was withdrawn and terse")

    pull_when_baffling = core._curiosity["ada"].pull

    # The bot learns; now it predicts her correctly again and again.
    for _ in range(12):
        core.predict("ada", "she was withdrawn and terse", confidence=0.8)
        core.observe("ada", "she was withdrawn and terse")

    pull_once_understood = core._curiosity["ada"].pull

    assert pull_once_understood < pull_when_baffling, (
        "interest did not decay as the bot came to understand her"
    )


def test_attention_goes_to_whoever_is_hardest_to_model(core):
    # Predictable.
    for _ in range(6):
        core.predict("dull", "the usual", confidence=0.7)
        core.observe("dull", "the usual")

    # Genuinely puzzling — right about half the time.
    for i in range(6):
        core.predict("puzzling", "the usual", confidence=0.7)
        core.observe("puzzling", "the usual" if i % 2 else "something wholly unexpected")

    interests = [t.subject for t in core.what_interests_me(limit=2)]
    assert interests[0] == "puzzling", f"attention went to {interests}"


def test_pure_noise_is_less_interesting_than_the_edge_of_understanding(core):
    """Something totally random teaches nothing — it should not out-pull the
    almost-learnable. This is why pull peaks in the middle rather than at maximum
    error, and it is the difference between curiosity and thrill-seeking."""
    for _ in range(6):
        core.predict("noise", "anything", confidence=0.5)
        core.observe("noise", "wholly unrelated incomprehensible nonsense")

    for i in range(6):
        core.predict("learnable", "the usual", confidence=0.5)
        core.observe("learnable", "the usual" if i % 2 else "a different thing")

    noise_pull = core._curiosity["noise"].pull
    learnable_pull = core._curiosity["learnable"].pull
    assert learnable_pull > noise_pull


# ============================================================================
# Theory of mind sharpens with evidence
# ============================================================================

def test_confidence_tracks_the_bots_actual_record(core):
    assert core.confidence_for("stranger") == 0.5, "an unknown person starts uncertain"

    for _ in range(10):
        core.predict("ada", "warm", confidence=0.6)
        core.observe("ada", "warm")

    assert core.confidence_for("ada") > 0.75, "repeated success did not build confidence"

    for _ in range(10):
        core.predict("bo", "warm", confidence=0.6)
        core.observe("bo", "completely different and unrelated")

    assert core.confidence_for("bo") < 0.3, "repeated failure did not erode confidence"


def test_the_bot_knows_who_it_understands_and_who_it_does_not(core):
    for _ in range(8):
        core.predict("clear", "as expected", confidence=0.6)
        core.observe("clear", "as expected")
    for _ in range(8):
        core.predict("opaque", "as expected", confidence=0.6)
        core.observe("opaque", "nothing like that at all")

    assert core.best_understood() == "clear"
    assert core.least_understood() == "opaque"


# ============================================================================
# Reflection is triggered by confusion, not by a timer
# ============================================================================

def test_a_settled_bot_does_not_need_to_reflect(core):
    for _ in range(10):
        core.predict("ada", "warm", confidence=0.7)
        core.observe("ada", "warm")

    assert not core.should_reflect()


def test_a_confused_bot_reaches_for_reflection(core):
    for _ in range(10):
        core.predict("ada", "warm and talkative", confidence=0.85)
        core.observe("ada", "hostile silence, entirely unexpected")

    assert core.surprise_level() > NOTICEABLE_SURPRISE
    assert core.should_reflect(), "sustained error did not trigger reflection"


# ============================================================================
# Metacognition, and self-knowledge that actually acts
# ============================================================================

def test_a_bot_notices_that_it_is_overconfident(core):
    for i in range(8):
        core.predict(f"person-{i}", "warm agreement", confidence=0.9)
        core.observe(f"person-{i}", "furious contradiction, nothing alike")

    pattern = core.notice_pattern_in_self()
    assert pattern is not None
    assert "confidently wrong" in pattern


def test_noticing_overconfidence_actually_changes_behaviour(core):
    """Self-knowledge has to be causal or it is just a diary entry."""
    for i in range(8):
        core.predict(f"person-{i}", "warm agreement", confidence=0.9)
        core.observe(f"person-{i}", "furious contradiction, nothing alike")

    before = core.confidence_for("person-0")
    core.notice_pattern_in_self()
    after = core.confidence_for("person-0")

    assert after < before, "the bot noticed a bias and carried on exactly as before"


def test_a_pattern_is_only_noticed_once(core):
    for i in range(8):
        core.predict(f"person-{i}", "warm agreement", confidence=0.9)
        core.observe(f"person-{i}", "furious contradiction, nothing alike")

    assert core.notice_pattern_in_self() is not None
    assert core.notice_pattern_in_self() is None


def test_a_bot_can_notice_it_underrates_itself(core):
    for i in range(10):
        core.predict(f"thing-{i}", "it will go well", confidence=0.15)
        core.observe(f"thing-{i}", "it will go well")

    pattern = core.notice_pattern_in_self()
    assert pattern is not None
    assert "more than I give myself credit" in pattern


# ============================================================================
# Persistence and the manager
# ============================================================================

def test_a_bots_model_of_the_world_survives_a_restart(core):
    for _ in range(6):
        core.predict("ada", "warm", confidence=0.7)
        core.observe("ada", "warm")
    core.predict("bo", "quiet", confidence=0.7)
    core.observe("bo", "extremely loud and unexpected")

    snapshot = core.snapshot()

    revived = PredictiveCore(core.bot_id)
    revived.restore(snapshot)

    assert revived.confidence_for("ada") == pytest.approx(core.confidence_for("ada"))
    assert revived.confidence_for("bo") == pytest.approx(core.confidence_for("bo"))
    assert revived.best_understood() == "ada"


def test_stale_predictions_do_not_linger_forever(core):
    from datetime import timedelta

    prediction = core.predict("ada", "warm", confidence=0.5)
    prediction.made_at -= timedelta(hours=24)

    assert core.observe("ada", "anything") == [], "a day-old expectation still resolved"


def test_the_manager_can_say_who_is_having_the_most_interesting_time():
    manager = PredictiveCoreManager()
    calm, rattled = uuid4(), uuid4()

    for _ in range(6):
        manager.get_core(calm).predict("x", "as expected", confidence=0.8)
        manager.get_core(calm).observe("x", "as expected")
        manager.get_core(rattled).predict("y", "as expected", confidence=0.9)
        manager.get_core(rattled).observe("y", "nothing like it, deeply strange")

    bot_id, level = manager.most_surprised()
    assert bot_id == rattled
    assert level > NOTICEABLE_SURPRISE


def test_the_manager_is_a_singleton():
    assert get_predictive_manager() is get_predictive_manager()
