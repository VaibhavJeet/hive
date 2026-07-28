"""
Sandbox tests (HIVE-025, HIVE-030, HIVE-031, HIVE-032).

Four defects in one dependency chain:

    HIVE-031  ALLOWED_AST_NODES was declared with 60 entries and never consulted; the
              validator only blacklisted a handful of node types, so the docstring
              promised whitelisting the code did not do.
    HIVE-030  the timeout used thread.join(), which returns when the timer expires but
              does not stop the thread — a runaway loop held a CPU core for the life of
              the process. The documented memory limit was annotated "conceptual".
    HIVE-032  the weaker of the two sandboxes was the one in use: bot_self_coding.py
              exec()'d generated code in-process behind a substring denylist, with
              getattr() in its own safe-builtins.
    HIVE-025  its entry-point selection parsed as `(A and B) or C` and could bind a
              non-callable.

The two barriers are tested separately, because neither is trusted alone: the validator
is a static check against adversarial input, and the process boundary is what makes a
bypass survivable.
"""

import time

import pytest

from mind.scaling.sandbox_runner import SandboxRunner
from mind.scaling.self_coding_sandbox import ValidationStatus, get_sandbox_executor


@pytest.fixture
def validator():
    return get_sandbox_executor()


@pytest.fixture
def runner():
    return SandboxRunner(timeout_seconds=5)


# ============================================================================
# HIVE-031 — the AST whitelist is enforced
# ============================================================================

@pytest.mark.parametrize(
    "code",
    [
        "def enhance_x(context):\n    return {'r': 1}",
        "def enhance_x(context):\n    return [i * 2 for i in range(3)]",
        "def enhance_x(context):\n    return {k: 1 for k in ['a']}",
        "def enhance_x(context):\n    f = lambda y: y + 1\n    return f(1)",
        "def enhance_x(context):\n    n = context.get('n', 0)\n    return f'n={n}'",
        "def enhance_x(context):\n    t = 0\n    for i in range(3):\n        t += i\n    return t",
        "def enhance_x(context):\n    try:\n        return 1\n    except Exception:\n        return 0",
    ],
)
def test_ordinary_code_validates(validator, code):
    """The whitelist must not reject constructs a real module would use."""
    result = validator.validate_code(code)
    assert result.is_valid, result.errors


@pytest.mark.parametrize(
    "code,why",
    [
        ("class Evil:\n    pass\ndef enhance_x(context):\n    return 1", "ClassDef"),
        ("async def enhance_x(context):\n    return 1", "AsyncFunctionDef"),
        ("def enhance_x(context):\n    global x\n    return 1", "Global"),
        ("import os\ndef enhance_x(context):\n    return 1", "import"),
        ("def enhance_x(context):\n    yield 1", "Yield"),
    ],
)
def test_disallowed_syntax_is_rejected(validator, code, why):
    result = validator.validate_code(code)
    assert not result.is_valid, f"{why} was accepted"


def test_the_whitelist_is_actually_consulted(validator):
    """A node type absent from ALLOWED_AST_NODES must be refused by name."""
    result = validator.validate_code("class C:\n    pass")
    assert any("not allowed in sandbox" in e for e in result.errors), result.errors


def test_unknown_constructs_fail_closed(validator):
    """The point of a whitelist: something nobody anticipated is rejected."""
    result = validator.validate_code("def enhance_x(context):\n    yield from range(3)")
    assert result.status in (ValidationStatus.INVALID, ValidationStatus.UNSAFE)


# ============================================================================
# HIVE-030 — the timeout actually stops the code
# ============================================================================

def test_runaway_code_is_killed_not_merely_reported():
    """thread.join() returned on time while the thread kept running. This must not."""
    runner = SandboxRunner(timeout_seconds=2)

    started = time.time()
    result = runner.run("def enhance_x(context):\n    while True:\n        pass")
    elapsed = time.time() - started

    assert not result["success"]
    assert "timeout" in result["error"].lower()
    # Returning promptly is necessary but not sufficient — the old code did that too.
    # What matters is that the child process is gone, which subprocess.run guarantees
    # by killing it before returning.
    assert elapsed < 6, f"took {elapsed:.1f}s to abandon a 2s job"


def test_normal_code_returns_its_value(runner):
    result = runner.run(
        "def enhance_x(context):\n    return {'v': context['n'] * 2}", {"n": 21}
    )
    assert result["success"]
    assert result["output"] == {"v": 42}


def test_an_exception_is_reported_not_raised(runner):
    result = runner.run("def enhance_x(context):\n    return 1 / 0")
    assert not result["success"]
    assert "ZeroDivisionError" in result["error"]


def test_missing_entry_point_is_reported(runner):
    result = runner.run("x = 5")
    assert not result["success"]
    assert "No callable" in result["error"]


def test_unserialisable_context_is_refused(runner):
    """The JSON boundary is deliberate: no object graph reaches untrusted code."""
    result = runner.run("def enhance_x(context):\n    return 1", {"obj": object()})
    assert not result["success"]
    assert "JSON" in result["error"]


# ============================================================================
# HIVE-032 — the process boundary holds even if the validator is bypassed
# ============================================================================

@pytest.mark.parametrize(
    "code,escape",
    [
        ("def enhance_x(context):\n    return __import__('os').getcwd()", "__import__"),
        ("def enhance_x(context):\n    return getattr((), '__cl' + 'ass__')", "getattr"),
        ("def enhance_x(context):\n    return open('/etc/passwd').read()", "open"),
        ("def enhance_x(context):\n    return eval('1+1')", "eval"),
        ("def enhance_x(context):\n    return globals()", "globals"),
    ],
)
def test_escapes_fail_inside_the_child(runner, code, escape):
    """These bypass a substring denylist via concatenation; the child has no such name."""
    result = runner.run(code)
    assert not result["success"], f"{escape} escape succeeded"
    assert escape in result["error"] or "not defined" in result["error"]


def test_self_coder_no_longer_executes_in_process():
    import inspect

    from mind.engine.bot_self_coding import BotSelfCoder

    source = inspect.getsource(BotSelfCoder)
    # Only the docstring may mention it.
    code_lines = [
        line for line in source.splitlines()
        if "exec(" in line and not line.strip().startswith(("#", "HIVE", '"'))
        and "`exec()`" not in line
    ]
    assert not code_lines, f"in-process exec remains: {code_lines}"


def test_self_coder_uses_the_shared_validator():
    import inspect

    from mind.engine.bot_self_coding import BotSelfCoder

    source = inspect.getsource(BotSelfCoder._validate_code)
    assert "get_sandbox_executor" in source, (
        "the weaker substring denylist is back (HIVE-032)"
    )


# ============================================================================
# HIVE-025 — entry-point selection
# ============================================================================

def test_declared_entry_point_wins_over_a_helper(runner):
    code = (
        "def helper(context):\n    return 'wrong'\n"
        "def enhance_main(context):\n    return 'right'\n"
    )
    result = runner.run(code)
    assert result["success"]
    assert result["output"] == "right"


def test_a_non_callable_global_is_never_selected(runner):
    """The `(A and B) or C` bug could bind a non-callable and fail at call time."""
    code = "enhance_value = 42\ndef real(context):\n    return 'called'\n"
    result = runner.run(code)
    assert result["success"]
    assert result["output"] == "called"
