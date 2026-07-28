"""
Self-Coding Sandbox for AI Community Companions.

Provides a secure sandbox environment for executing bot-generated code.
Uses strict validation and resource limits to prevent unsafe operations.
"""

import ast
import logging
import sys
import traceback
from datetime import datetime
from typing import List, Optional, Dict, Any, Set
from uuid import UUID, uuid4
from dataclasses import dataclass, field
from enum import Enum
import signal
import threading
from contextlib import contextmanager


logger = logging.getLogger(__name__)


# ============================================================================
# DATA CLASSES
# ============================================================================

class ValidationStatus(str, Enum):
    """Status of code validation."""
    VALID = "valid"
    INVALID = "invalid"
    UNSAFE = "unsafe"
    SYNTAX_ERROR = "syntax_error"


@dataclass
class ValidationResult:
    """Result of code validation."""
    status: ValidationStatus
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    analyzed_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "status": self.status.value,
            "is_valid": self.is_valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "analyzed_at": self.analyzed_at.isoformat()
        }


class ExecutionStatus(str, Enum):
    """Status of code execution."""
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    VALIDATION_FAILED = "validation_failed"


@dataclass
class ExecutionResult:
    """Result of code execution."""
    status: ExecutionStatus
    success: bool
    output: Any
    error: Optional[str]
    execution_time_ms: float
    memory_used_bytes: int
    executed_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "status": self.status.value,
            "success": self.success,
            "output": str(self.output) if self.output else None,
            "error": self.error,
            "execution_time_ms": self.execution_time_ms,
            "memory_used_bytes": self.memory_used_bytes,
            "executed_at": self.executed_at.isoformat()
        }


# ============================================================================
# SANDBOX EXECUTOR
# ============================================================================

class SandboxExecutor:
    """
    Secure sandbox for executing bot-generated code.

    Security features:
    - Strict code validation
    - No file access
    - No network access
    - No imports
    - Timeout enforcement
    - Memory limits (conceptual)
    - Whitelisted operations only
    """

    # Safe builtins that can be used in sandbox
    SAFE_BUILTINS: Dict[str, Any] = {
        # Type constructors
        'str': str,
        'int': int,
        'float': float,
        'bool': bool,
        'list': list,
        'dict': dict,
        'set': set,
        'tuple': tuple,

        # Iteration helpers
        'range': range,
        'enumerate': enumerate,
        'zip': zip,
        'map': map,
        'filter': filter,
        'sorted': sorted,
        'reversed': reversed,

        # Math/comparison
        'len': len,
        'min': min,
        'max': max,
        'sum': sum,
        'abs': abs,
        'round': round,
        'any': any,
        'all': all,

        # Type checking
        'isinstance': isinstance,
        'issubclass': issubclass,
        'type': type,
        'callable': callable,

        # String operations
        'repr': repr,
        'chr': chr,
        'ord': ord,
        'format': format,

        # Numbers and structure — a bot writing its own analysis needs real tools
        'divmod': divmod,
        'pow': pow,
        'hash': hash,
        'bytes': bytes,
        'bytearray': bytearray,
        'frozenset': frozenset,
        'slice': slice,
        'iter': iter,
        'next': next,
        'print': print,

        # Exceptions a bot can legitimately raise and catch
        'Exception': Exception,
        'ValueError': ValueError,
        'TypeError': TypeError,
        'KeyError': KeyError,
        'IndexError': IndexError,
        'ZeroDivisionError': ZeroDivisionError,
        'AttributeError': AttributeError,
        'StopIteration': StopIteration,

        # Constants
        'True': True,
        'False': False,
        'None': None,
    }

    #: Pure-computation modules pre-imported inside the sandbox child.
    #:
    #: These vastly widen what a bot can express — statistics over its own history,
    #: pattern matching on text, structured data, randomness for creative variation —
    #: without opening any escape. The child's `__import__` stays disabled, so a bot
    #: gets exactly these and can reach nothing else. None of them touch the
    #: filesystem, the network, or the process.
    SAFE_MODULES: List[str] = [
        'math', 'random', 'statistics', 'json', 're',
        'itertools', 'collections', 'string', 'textwrap', 'difflib',
    ]

    # Forbidden constructs that indicate unsafe code
    FORBIDDEN_PATTERNS: List[str] = [
        # Imports
        'import ', 'from ', '__import__',

        # Execution
        'exec(', 'eval(', 'compile(',

        # File operations. NOTE: `read(` and `write(` were in this list and are now
        # gone — they matched any method with those names, so a bot could not write
        # `buffer.write(x)` or `stream.read()` on its own objects. Actual file access
        # is impossible in the child regardless: there is no `open` and no import.
        'open(', 'file(',

        # System access
        'os.', 'sys.', 'subprocess', 'commands',

        # Introspection that could be abused. These are belt-and-braces now: the
        # substring check is defeated by string concatenation anyway, which is exactly
        # why HIVE-032 moved containment to the process boundary. Kept because
        # rejecting the obvious attempt early gives a clearer error than a NameError
        # from inside the child.
        '__class__', '__bases__', '__mro__',
        '__globals__', '__code__', '__builtins__',
        '__subclasses__', '__dict__',

        # Dangerous operations
        'delattr', 'setattr', 'getattr(',
        'globals(', 'locals(', 'vars(',

        # Network
        'socket', 'urllib', 'requests',

        # Process control
        'exit(', 'quit(', 'breakpoint',
        'input(', 'raw_input',

        # Shell access
        'popen', 'spawn', 'fork', 'system',
    ]

    # Allowed AST node types
    ALLOWED_AST_NODES: Set[type] = {
        # Module structure
        ast.Module,
        ast.FunctionDef,
        ast.Return,
        ast.Pass,

        # Expressions
        ast.Expr,
        ast.Name,
        ast.Load,
        ast.Store,
        ast.Constant,

        # Operations
        ast.BinOp,
        ast.UnaryOp,
        ast.BoolOp,
        ast.Compare,

        # Operators
        ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow,
        ast.And, ast.Or, ast.Not,
        ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
        ast.Is, ast.IsNot, ast.In, ast.NotIn,
        ast.USub, ast.UAdd,

        # Control flow
        ast.If,
        ast.For,
        ast.While,
        ast.Break,
        ast.Continue,

        # Data structures
        ast.List,
        ast.Dict,
        ast.Set,
        ast.Tuple,

        # Subscript
        ast.Subscript,
        ast.Index,
        ast.Slice,

        # Comprehensions
        ast.ListComp,
        ast.DictComp,
        ast.SetComp,
        ast.GeneratorExp,
        ast.comprehension,

        # Attribute access (limited)
        ast.Attribute,

        # Function calls
        ast.Call,
        ast.arguments,
        ast.arg,

        # Assignments
        ast.Assign,
        ast.AugAssign,

        # String formatting
        ast.JoinedStr,
        ast.FormattedValue,

        # Lambda
        ast.Lambda,

        # Ternary
        ast.IfExp,

        # Starred (for unpacking)
        ast.Starred,

        # Node types that appear in any valid function body and were missing from the
        # original list — it had never been executed, so nothing exposed the gaps.
        ast.arguments,
        ast.keyword,
        ast.Assert,
        ast.AnnAssign,
        ast.NamedExpr,
        ast.Tuple,
        ast.Del,
        ast.Delete,
        ast.FloorDiv,
        ast.MatMult,
        ast.BitAnd,
        ast.BitOr,
        ast.BitXor,
        ast.LShift,
        ast.RShift,
        ast.Invert,
        ast.Dict,
        ast.Set,
        ast.Slice,
        ast.ExceptHandler,
        ast.Try,
        ast.Raise,

        # --- Widened once the subprocess boundary made the grammar stop being the ---
        # --- thing keeping bots safe. See validate_code() for the reasoning.      ---

        # Classes: a bot that can define a type can build a model of something.
        ast.ClassDef,

        # Context managers, now that there is nothing dangerous to open.
        ast.With,
        ast.withitem,

        # Generators: iterative analysis over a bot's own history.
        ast.Yield,
        ast.YieldFrom,
    }

    def __init__(
        self,
        default_timeout: int = 5,
        max_output_size: int = 10000,
        max_memory_bytes: int = 10 * 1024 * 1024  # 10MB
    ):
        """
        Initialize the sandbox executor.

        Args:
            default_timeout: Default execution timeout in seconds
            max_output_size: Maximum size of output in characters
            max_memory_bytes: Maximum memory usage (conceptual limit)
        """
        self.default_timeout = default_timeout
        self.max_output_size = max_output_size
        self.max_memory_bytes = max_memory_bytes

    def validate_code(self, code: str) -> ValidationResult:
        """
        Validate code for safety before execution.

        Checks:
        1. Forbidden patterns
        2. AST structure
        3. Resource usage patterns

        Args:
            code: The code to validate

        Returns:
            ValidationResult with validation status
        """
        errors = []
        warnings = []

        # Check for forbidden patterns
        code_lower = code.lower()
        for pattern in self.FORBIDDEN_PATTERNS:
            if pattern.lower() in code_lower:
                errors.append(f"Forbidden pattern detected: '{pattern}'")

        if errors:
            return ValidationResult(
                status=ValidationStatus.UNSAFE,
                is_valid=False,
                errors=errors,
                warnings=warnings
            )

        # Parse AST
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return ValidationResult(
                status=ValidationStatus.SYNTAX_ERROR,
                is_valid=False,
                errors=[f"Syntax error: {e.msg} at line {e.lineno}"],
                warnings=warnings
            )

        # Validate AST nodes
        for node in ast.walk(tree):
            # HIVE-031: enforce ALLOWED_AST_NODES. It was declared with 60 entries and
            # never consulted — the walk below only blacklisted a handful of node types,
            # so the docstring promised whitelisting the code did not do. A whitelist is
            # the only side of this that is safe to get wrong: an unknown node type is
            # rejected rather than quietly permitted.
            if type(node) not in self.ALLOWED_AST_NODES:
                errors.append(
                    f"Syntax not allowed in sandbox: {type(node).__name__}"
                )
                continue

            # Check for imports
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                errors.append("Import statements are not allowed")

            # Check for global/nonlocal
            if isinstance(node, (ast.Global, ast.Nonlocal)):
                errors.append("Global/nonlocal statements are not allowed")

            # Classes and exception handling are ALLOWED. They used to be treated as
            # suspicious because this validator was the only thing standing between
            # generated code and the API process. Since HIVE-030/032 the code runs in a
            # separate interpreter with no import system, killed on timeout — so the
            # process boundary does the containment, and the grammar no longer has to.
            #
            # That distinction matters for this project: a bot that can define a class
            # or handle an error is a bot that can build something. Restricting syntax
            # to keep it safe was solving the problem in the wrong layer.

            # Async is still refused, but for a practical reason rather than a security
            # one: the sandbox child runs synchronously and has no event loop to await
            # on, so async code would simply never execute.
            if isinstance(node, (ast.AsyncFunctionDef, ast.Await, ast.AsyncFor,
                                 ast.AsyncWith)):
                errors.append(
                    "Async is not available in the sandbox (no event loop in the child)"
                )

            # Check for dangerous attribute access
            if isinstance(node, ast.Attribute):
                if node.attr.startswith('_'):
                    errors.append(f"Private attribute access not allowed: {node.attr}")

            # Check for dangerous function calls
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                    if func_name not in self.SAFE_BUILTINS and not func_name.startswith('enhance_'):
                        warnings.append(f"Function '{func_name}' may not be available")

        if errors:
            return ValidationResult(
                status=ValidationStatus.INVALID,
                is_valid=False,
                errors=errors,
                warnings=warnings
            )

        return ValidationResult(
            status=ValidationStatus.VALID,
            is_valid=True,
            errors=errors,
            warnings=warnings
        )

    def execute_code(
        self,
        code: str,
        context: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None
    ) -> ExecutionResult:
        """
        Execute code in the sandbox.

        Args:
            code: The code to execute
            context: Context dict to pass to the code
            timeout: Execution timeout in seconds

        Returns:
            ExecutionResult with execution results
        """
        import time
        start_time = time.time()

        # Validate first
        validation = self.validate_code(code)
        if not validation.is_valid:
            return ExecutionResult(
                status=ExecutionStatus.VALIDATION_FAILED,
                success=False,
                output=None,
                error="; ".join(validation.errors),
                execution_time_ms=0,
                memory_used_bytes=0
            )

        timeout = timeout or self.default_timeout

        # HIVE-030: there is no in-process sandbox namespace any more. The child
        # interpreter builds its own restricted globals; nothing from this process is
        # handed to untrusted code, which is what `_create_sandbox_globals` used to do.
        result = self._execute_with_timeout(code, {"context": context or {}}, timeout)

        execution_time = (time.time() - start_time) * 1000  # ms

        if result['error']:
            return ExecutionResult(
                status=ExecutionStatus.TIMEOUT if 'timeout' in result['error'].lower() else ExecutionStatus.ERROR,
                success=False,
                output=None,
                error=result['error'],
                execution_time_ms=execution_time,
                memory_used_bytes=result.get('memory', 0)
            )

        return ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            success=True,
            output=result['output'],
            error=None,
            execution_time_ms=execution_time,
            memory_used_bytes=result.get('memory', 0)
        )

    def _execute_with_timeout(
        self,
        code: str,
        sandbox_globals: Dict[str, Any],
        timeout: int
    ) -> Dict[str, Any]:
        """Execute code in the out-of-process sandbox.

        HIVE-030: this used to run `exec()` on a daemon thread and call
        `thread.join(timeout)`. `join` returns when the timer expires but does not stop
        the thread, so a runaway loop kept a CPU core busy for the life of the process —
        the timeout reported a failure it had not actually enforced. The documented
        memory limit was annotated "conceptual" and was not enforced at all.

        Execution now happens in a child interpreter that is killed on timeout, with
        address-space and CPU limits applied where the platform supports them.
        """
        from mind.scaling.sandbox_runner import SandboxRunner

        context = sandbox_globals.get("context", {})
        outcome = SandboxRunner(timeout_seconds=timeout).run(code, context)

        return {
            "output": outcome["output"],
            "error": outcome["error"],
            "memory": 0,
        }

    def get_allowed_operations(self) -> List[str]:
        """
        Get list of allowed operations in the sandbox.

        Returns:
            List of operation names that are safe to use
        """
        operations = []

        # Add safe builtins
        operations.extend([
            f"{name}() - {self._describe_builtin(name)}"
            for name in sorted(self.SAFE_BUILTINS.keys())
            if callable(self.SAFE_BUILTINS.get(name))
        ])

        return operations

    def _describe_builtin(self, name: str) -> str:
        """Get description for a builtin function."""
        descriptions = {
            'str': 'Convert to string',
            'int': 'Convert to integer',
            'float': 'Convert to float',
            'bool': 'Convert to boolean',
            'list': 'Create list',
            'dict': 'Create dictionary',
            'set': 'Create set',
            'tuple': 'Create tuple',
            'range': 'Create range of numbers',
            'enumerate': 'Add index to iterable',
            'zip': 'Combine iterables',
            'map': 'Apply function to items',
            'filter': 'Filter items by predicate',
            'sorted': 'Sort items',
            'reversed': 'Reverse items',
            'len': 'Get length',
            'min': 'Get minimum',
            'max': 'Get maximum',
            'sum': 'Sum items',
            'abs': 'Absolute value',
            'round': 'Round number',
            'any': 'Check if any True',
            'all': 'Check if all True',
            'isinstance': 'Check type',
            'type': 'Get type',
            'repr': 'Get representation',
            'chr': 'Int to character',
            'ord': 'Character to int',
        }
        return descriptions.get(name, 'Built-in function')

    def test_sandbox(self) -> Dict[str, Any]:
        """
        Run sandbox tests to verify security.

        Returns:
            Dict with test results
        """
        tests = {
            "basic_function": {
                "code": """
def enhance_test(context):
    return {"result": "hello", "confidence": 1.0}
""",
                "expected": "success"
            },
            "math_operations": {
                "code": """
def enhance_math(context):
    x = context.get('x', 5)
    return {"result": x * 2 + 1, "confidence": 0.9}
""",
                "expected": "success"
            },
            "string_operations": {
                "code": """
def enhance_string(context):
    text = context.get('text', 'hello')
    return {"result": text.upper(), "confidence": 0.8}
""",
                "expected": "success"
            },
            "blocked_import": {
                "code": """
import os
def enhance_bad(context):
    return os.getcwd()
""",
                "expected": "validation_failed"
            },
            "blocked_file_access": {
                "code": """
def enhance_bad(context):
    with open('/etc/passwd', 'r') as f:
        return f.read()
""",
                "expected": "validation_failed"
            },
            "blocked_exec": {
                "code": """
def enhance_bad(context):
    exec("import os")
    return None
""",
                "expected": "validation_failed"
            },
        }

        results = {}
        for test_name, test_config in tests.items():
            result = self.execute_code(test_config["code"], {"x": 10, "text": "test"})
            results[test_name] = {
                "passed": result.status.value == test_config["expected"] or (
                    test_config["expected"] == "success" and result.success
                ),
                "status": result.status.value,
                "expected": test_config["expected"]
            }

        return results


# ============================================================================
# FACTORY
# ============================================================================

_sandbox_executor: Optional[SandboxExecutor] = None


def get_sandbox_executor() -> SandboxExecutor:
    """Get the singleton sandbox executor."""
    global _sandbox_executor
    if _sandbox_executor is None:
        _sandbox_executor = SandboxExecutor()
    return _sandbox_executor
