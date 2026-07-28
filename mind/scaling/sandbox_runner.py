"""
Out-of-process runner for bot-generated code (HIVE-030, HIVE-032).

The previous design ran generated code with `exec()` in the API process, guarded by a
substring denylist, and enforced its timeout with `thread.join(timeout)` — which returns
when the timer expires but does **not** stop the thread. A runaway loop kept a CPU core
busy for the life of the process, and any escape from the denylist ran with the full
privileges of the server.

This runs the code in a child interpreter that can actually be killed. Two independent
barriers, neither trusted alone:

1. `SandboxExecutor.validate_code` — AST whitelist, applied before anything runs. A
   static check against adversarial input is a losing game by itself.
2. This runner — a separate process, a hard kill on timeout, imports disabled inside the
   child, and address-space/CPU limits where the platform provides them. This is what
   makes a validator bypass survivable rather than fatal.

**Why `subprocess` and not `multiprocessing`:** on Windows (and anywhere using the
`spawn` start method) `multiprocessing` re-imports the parent module in the child, which
here means importing the whole `mind` package — database engine included — for every
sandbox call. The child below imports nothing from this project; it reads a JSON job on
stdin and writes a JSON result to stdout.

The JSON boundary also means no object graph crosses into untrusted code, which is a
property worth having on its own.
"""

import json
import logging
import subprocess
import sys
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 5
DEFAULT_MEMORY_LIMIT_BYTES = 256 * 1024 * 1024

# Runs in a bare interpreter with no project imports. Kept as source rather than a file
# so there is nothing on disk for anything else to import or tamper with.
_CHILD_SOURCE = r'''
import builtins, json, sys

def _limit(memory_bytes, cpu_seconds):
    try:
        import resource
    except ImportError:
        return  # Windows: the process boundary and the kill still apply
    for what, value in ((resource.RLIMIT_AS, memory_bytes),
                        (resource.RLIMIT_CPU, cpu_seconds)):
        try:
            resource.setrlimit(what, (value, value))
        except (ValueError, OSError):
            pass

def main():
    job = json.loads(sys.stdin.read())
    _limit(job["memory_limit"], job["cpu_seconds"])

    # Pure-computation modules, imported BEFORE __import__ is disabled. A bot gets
    # exactly these and can reach nothing else. None of them touch the filesystem,
    # the network, or the process — but together they are the difference between a
    # bot that can only do arithmetic and one that can do statistics over its own
    # history, match patterns in what it reads, and be randomly creative.
    provided = {}
    for name in job.get("modules", []):
        try:
            provided[name] = __import__(name)
        except ImportError:
            pass

    allowed = {
        "len": len, "str": str, "int": int, "float": float, "bool": bool,
        "list": list, "dict": dict, "set": set, "tuple": tuple, "range": range,
        "enumerate": enumerate, "zip": zip, "map": map, "filter": filter,
        "sorted": sorted, "reversed": reversed, "min": min, "max": max,
        "sum": sum, "abs": abs, "round": round, "any": any, "all": all,
        "isinstance": isinstance, "issubclass": issubclass, "type": type,
        "callable": callable, "repr": repr, "chr": chr, "ord": ord,
        "format": format, "divmod": divmod, "pow": pow, "hash": hash,
        "bytes": bytes, "bytearray": bytearray, "frozenset": frozenset,
        "slice": slice, "iter": iter, "next": next,
        # Exceptions a bot can legitimately raise and catch.
        "Exception": Exception, "ValueError": ValueError, "TypeError": TypeError,
        "KeyError": KeyError, "IndexError": IndexError,
        "ZeroDivisionError": ZeroDivisionError, "AttributeError": AttributeError,
        "StopIteration": StopIteration, "RuntimeError": RuntimeError,
        "True": True, "False": False, "None": None,
    }

    def _no_imports(*a, **k):
        raise ImportError("imports are not available in the sandbox")

    builtins.__import__ = _no_imports

    g = {"__builtins__": dict(allowed)}
    g.update(provided)
    try:
        exec(compile(job["code"], "<sandbox>", "exec"), g)

        target = None
        for name, obj in g.items():
            if not callable(obj) or name.startswith("__") or name in allowed:
                continue
            if name in provided:
                continue  # a provided module is not the bot's entry point
            # HIVE-025: the original selected with
            #   callable(obj) and name.startswith("_auto_") or name == <string split>
            # which parses as (A and B) or C, so a non-callable global matching a
            # fragile string expression could be chosen. Prefer a declared entry point,
            # then fall back to the single user-defined function.
            if name.startswith("enhance_") or name.startswith("_auto_"):
                target = obj
                break
            if target is None:
                target = obj

        if target is None:
            print(json.dumps({"status": "error",
                              "error": "No callable function found in code"}))
            return

        print(json.dumps({"status": "ok", "output": target(job["context"])}))
    except MemoryError:
        print(json.dumps({"status": "error", "error": "Sandbox exceeded its memory limit"}))
    except BaseException as exc:
        print(json.dumps({"status": "error",
                          "error": "%s: %s" % (type(exc).__name__, exc)}))

main()
'''


class SandboxRunner:
    """Runs untrusted code in a killable child interpreter."""

    #: Pure-computation modules made available to bot code. Kept in sync with
    #: SandboxExecutor.SAFE_MODULES; see that docstring for why these are safe.
    DEFAULT_MODULES = [
        "math", "random", "statistics", "json", "re",
        "itertools", "collections", "string", "textwrap", "difflib",
    ]

    def __init__(
        self,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        memory_limit_bytes: int = DEFAULT_MEMORY_LIMIT_BYTES,
        modules: Optional[list] = None,
    ):
        self.timeout_seconds = timeout_seconds
        self.memory_limit_bytes = memory_limit_bytes
        self.modules = list(self.DEFAULT_MODULES if modules is None else modules)

    def run(
        self,
        code: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute `code`, returning `{"success", "output", "error"}`.

        Never raises: a sandbox failure is a result, not an exception, so generated code
        cannot break the request that triggered it.
        """
        try:
            job = json.dumps(
                {
                    "code": code,
                    "context": context or {},
                    "memory_limit": self.memory_limit_bytes,
                    "cpu_seconds": self.timeout_seconds,
                    "modules": self.modules,
                }
            )
        except (TypeError, ValueError) as exc:
            return {
                "success": False,
                "output": None,
                "error": f"Context is not JSON-serialisable: {exc}",
            }

        try:
            completed = subprocess.run(
                [sys.executable, "-I", "-S", "-c", _CHILD_SOURCE],
                input=job,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            # subprocess.run kills the child on timeout — the behaviour
            # thread.join() could not provide.
            return {
                "success": False,
                "output": None,
                "error": f"Execution timeout after {self.timeout_seconds} seconds",
            }
        except OSError as exc:
            return {"success": False, "output": None, "error": f"Sandbox failed: {exc}"}

        stdout = (completed.stdout or "").strip()
        if not stdout:
            detail = (completed.stderr or "").strip()[:200] or "no output"
            return {"success": False, "output": None, "error": f"Sandbox failed: {detail}"}

        try:
            payload = json.loads(stdout.splitlines()[-1])
        except ValueError:
            return {
                "success": False,
                "output": None,
                "error": "Sandbox produced unreadable output",
            }

        if payload.get("status") == "ok":
            return {"success": True, "output": payload.get("output"), "error": None}

        error = payload.get("error", "unknown sandbox error")
        logger.warning("Sandbox execution failed: %s", error)
        return {"success": False, "output": None, "error": error}


_runner: Optional[SandboxRunner] = None


def get_sandbox_runner() -> SandboxRunner:
    """Get the shared sandbox runner."""
    global _runner
    if _runner is None:
        _runner = SandboxRunner()
    return _runner
