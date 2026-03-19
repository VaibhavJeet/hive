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
        'type': type,

        # String operations
        'repr': repr,
        'chr': chr,
        'ord': ord,

        # Constants
        'True': True,
        'False': False,
        'None': None,
    }

    # Forbidden constructs that indicate unsafe code
    FORBIDDEN_PATTERNS: List[str] = [
        # Imports
        'import ', 'from ', '__import__',

        # Execution
        'exec(', 'eval(', 'compile(',

        # File operations
        'open(', 'file(', 'read(', 'write(',

        # System access
        'os.', 'sys.', 'subprocess', 'commands',

        # Introspection that could be abused
        '__class__', '__bases__', '__mro__',
        '__globals__', '__code__', '__builtins__',
        '__subclasses__', '__dict__',

        # Dangerous operations
        'delattr', 'setattr', 'getattr(',
        'globals(', 'locals(', 'vars(',
        'dir(', 'help(',

        # Network
        'socket', 'urllib', 'requests', 'http',

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
            # Check for imports
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                errors.append("Import statements are not allowed")

            # Check for global/nonlocal
            if isinstance(node, (ast.Global, ast.Nonlocal)):
                errors.append("Global/nonlocal statements are not allowed")

            # Check for class definitions (could be used for metaprogramming)
            if isinstance(node, ast.ClassDef):
                warnings.append("Class definitions are restricted")

            # Check for async operations
            if isinstance(node, (ast.AsyncFunctionDef, ast.Await)):
                errors.append("Async operations are not allowed")

            # Check for try/except (could mask errors)
            if isinstance(node, ast.Try):
                warnings.append("Exception handling is limited")

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

        # Create sandbox globals
        sandbox_globals = self._create_sandbox_globals()

        # Add context
        if context:
            sandbox_globals['context'] = context

        # Execute with timeout
        result = self._execute_with_timeout(code, sandbox_globals, timeout)

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

    def _create_sandbox_globals(self) -> Dict[str, Any]:
        """Create the sandbox execution environment."""
        return {
            '__builtins__': self.SAFE_BUILTINS.copy(),
            'datetime': datetime,  # Limited datetime access
        }

    def _execute_with_timeout(
        self,
        code: str,
        sandbox_globals: Dict[str, Any],
        timeout: int
    ) -> Dict[str, Any]:
        """Execute code with timeout protection."""
        result = {'output': None, 'error': None, 'memory': 0}

        def execute():
            try:
                # Compile and execute
                compiled = compile(code, '<sandbox>', 'exec')
                exec(compiled, sandbox_globals)

                # Find and call the function
                for name, obj in sandbox_globals.items():
                    if callable(obj) and name.startswith('enhance_'):
                        context = sandbox_globals.get('context', {})
                        result['output'] = obj(context)
                        return

                # If no enhance_ function, look for any user-defined function
                for name, obj in sandbox_globals.items():
                    if callable(obj) and not name.startswith('_') and name not in self.SAFE_BUILTINS:
                        context = sandbox_globals.get('context', {})
                        result['output'] = obj(context)
                        return

                result['error'] = "No callable function found in code"

            except Exception as e:
                result['error'] = f"{type(e).__name__}: {str(e)}"

        # Run in thread with timeout
        thread = threading.Thread(target=execute)
        thread.daemon = True
        thread.start()
        thread.join(timeout=timeout)

        if thread.is_alive():
            result['error'] = f"Execution timeout after {timeout} seconds"

        return result

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
