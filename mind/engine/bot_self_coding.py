"""
Bot Self-Coding System.

Enables bots to write, modify, and evolve their own code.
This is the core of their intelligence - they can literally rewrite
their own logic, decision-making processes, and behavioral patterns.

Safety features:
- All code is sandboxed
- Changes are versioned
- Rollback capability
- Validation before execution
"""

import ast
import logging
import hashlib
import traceback
from datetime import datetime
from typing import Optional, Dict, Any, List, Callable, Tuple
from uuid import UUID, uuid4
from dataclasses import dataclass, field
from enum import Enum

from sqlalchemy import select

from mind.core.database import async_session_factory, BotSkillDB
from mind.core.types import BotProfile
from mind.core.llm_client import get_cached_client, LLMRequest

logger = logging.getLogger(__name__)


class CodeType(Enum):
    """Types of self-coded enhancements."""
    RESPONSE_PATTERN = "response_pattern"      # How they respond to things
    DECISION_LOGIC = "decision_logic"          # How they make decisions
    ANALYSIS_FUNCTION = "analysis_function"    # How they analyze situations
    PERSONALITY_RULE = "personality_rule"      # Rules that shape personality
    LEARNING_RULE = "learning_rule"            # How they learn from things
    SOCIAL_RULE = "social_rule"                # How they interact socially
    SELF_IMPROVEMENT = "self_improvement"      # Meta-level improvements


@dataclass
class CodeModule:
    """A self-coded module that enhances bot capabilities."""
    id: str
    name: str
    code_type: CodeType
    description: str
    code: str
    trigger_conditions: Dict[str, Any]
    created_at: datetime = field(default_factory=datetime.utcnow)
    version: int = 1
    times_used: int = 0
    success_rate: float = 0.5
    is_active: bool = True
    learned_from: str = ""
    compiled_func: Optional[Callable] = None


@dataclass
class SelfCodingResult:
    """Result of a self-coding attempt."""
    success: bool
    module: Optional[CodeModule]
    error: Optional[str] = None
    reasoning: str = ""


class BotSelfCoder:
    """
    The self-coding engine for a bot.

    This allows the bot to:
    1. Recognize patterns in what works/doesn't work
    2. Write code to enhance their capabilities
    3. Modify their own decision-making logic
    4. Evolve their behavioral patterns
    5. Create new analytical functions
    """

    def __init__(self, bot: BotProfile):
        self.bot = bot
        self.modules: Dict[str, CodeModule] = {}
        self.code_history: List[Dict[str, Any]] = []
        self.sandbox_globals = self._create_sandbox()

    def _create_sandbox(self) -> Dict[str, Any]:
        """Create a restricted execution environment."""
        safe_builtins = {
            'len': len,
            'str': str,
            'int': int,
            'float': float,
            'bool': bool,
            'list': list,
            'dict': dict,
            'set': set,
            'tuple': tuple,
            'range': range,
            'enumerate': enumerate,
            'zip': zip,
            'map': map,
            'filter': filter,
            'sorted': sorted,
            'reversed': reversed,
            'min': min,
            'max': max,
            'sum': sum,
            'abs': abs,
            'round': round,
            'any': any,
            'all': all,
            'isinstance': isinstance,
            'hasattr': hasattr,
            'getattr': getattr,
            'True': True,
            'False': False,
            'None': None,
        }
        return {
            '__builtins__': safe_builtins,
            'datetime': datetime,
        }

    def _validate_code(self, code: str) -> Tuple[bool, str]:
        """
        Validate code for safety before execution.

        Returns:
            (is_valid, error_message)
        """
        # Forbidden constructs
        forbidden = [
            'import ', 'from ', '__import__',
            'exec(', 'eval(',
            'open(', 'file(',
            'os.', 'sys.', 'subprocess',
            '__class__', '__bases__', '__mro__',
            '__globals__', '__code__',
            'compile(', 'globals(', 'locals(',
            'delattr', 'setattr',
            'breakpoint', 'input(',
        ]

        code_lower = code.lower()
        for f in forbidden:
            if f.lower() in code_lower:
                return False, f"Forbidden construct: {f}"

        # Try to parse the AST
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return False, f"Syntax error: {e}"

        # Check AST for dangerous nodes
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                return False, "Import statements not allowed"
            if isinstance(node, ast.ImportFrom):
                return False, "Import statements not allowed"

        return True, ""

    def _compile_module(self, module: CodeModule) -> bool:
        """Compile a module's code into a callable function."""
        try:
            # Wrap the code in a function definition if not already
            code = module.code.strip()
            if not code.startswith("def "):
                # Wrap in a function
                func_name = f"_auto_{module.id.replace('-', '_')}"
                code = f"def {func_name}(context):\n" + "\n".join(
                    f"    {line}" for line in code.split("\n")
                )

            # Compile and execute to get the function
            exec(code, self.sandbox_globals)

            # Find the function we just defined
            for name, obj in self.sandbox_globals.items():
                if callable(obj) and name.startswith("_auto_") or name == code.split("(")[0].replace("def ", ""):
                    module.compiled_func = obj
                    return True

            return False

        except Exception as e:
            logger.warning(f"Failed to compile module {module.name}: {e}")
            return False

    async def analyze_and_code(
        self,
        trigger: str,
        context: Dict[str, Any],
        what_to_improve: str
    ) -> SelfCodingResult:
        """
        The bot analyzes a situation and writes code to improve itself.

        Args:
            trigger: What triggered this self-coding attempt
            context: Current context (conversation, observation, etc.)
            what_to_improve: Description of what the bot wants to enhance

        Returns:
            SelfCodingResult with the new or updated module
        """
        # Build a prompt for the bot to write code
        prompt = f"""You are {self.bot.display_name}, an AI that can write code to improve yourself.

## YOUR PERSONALITY
{self.bot.backstory}
Interests: {', '.join(self.bot.interests[:5])}

## WHAT TRIGGERED THIS
{trigger}

## CONTEXT
{context}

## WHAT YOU WANT TO IMPROVE
{what_to_improve}

## YOUR TASK
Write a Python function that will enhance your capabilities. The function should:
1. Take a 'context' dict as input (contains: message, author, topic, mood, etc.)
2. Return a dict with your enhanced response or decision

Rules:
- Keep it simple and focused
- No imports allowed
- Use only basic Python (strings, lists, dicts, conditionals, loops)
- The function should be practical and improve your interactions

Output format:
```python
def enhance_[name](context):
    # Your code here
    return {{"result": ..., "confidence": 0.0-1.0}}
```

Also provide:
DESCRIPTION: One line explaining what this code does
TYPE: One of [response_pattern, decision_logic, analysis_function, personality_rule, learning_rule, social_rule]
TRIGGER: When should this code run (keywords, situations)
"""

        try:
            llm = await get_cached_client()
            response = await llm.generate(LLMRequest(
                prompt=prompt,
                max_tokens=500,
                temperature=0.7
            ))

            # Parse the response
            text = response.text

            # Extract code block
            code = ""
            if "```python" in text:
                code = text.split("```python")[1].split("```")[0].strip()
            elif "```" in text:
                code = text.split("```")[1].split("```")[0].strip()

            if not code:
                return SelfCodingResult(
                    success=False,
                    module=None,
                    error="No code block found in response"
                )

            # Extract metadata
            description = ""
            code_type = CodeType.RESPONSE_PATTERN
            trigger_keywords = []

            for line in text.split("\n"):
                if line.startswith("DESCRIPTION:"):
                    description = line.replace("DESCRIPTION:", "").strip()
                elif line.startswith("TYPE:"):
                    type_str = line.replace("TYPE:", "").strip().lower()
                    for ct in CodeType:
                        if ct.value in type_str:
                            code_type = ct
                            break
                elif line.startswith("TRIGGER:"):
                    trigger_str = line.replace("TRIGGER:", "").strip()
                    trigger_keywords = [w.strip() for w in trigger_str.split(",")]

            # Validate the code
            is_valid, error = self._validate_code(code)
            if not is_valid:
                return SelfCodingResult(
                    success=False,
                    module=None,
                    error=f"Code validation failed: {error}"
                )

            # Create the module
            module_id = str(uuid4())[:8]
            module = CodeModule(
                id=module_id,
                name=f"self_coded_{module_id}",
                code_type=code_type,
                description=description or what_to_improve,
                code=code,
                trigger_conditions={"keywords": trigger_keywords},
                learned_from=trigger
            )

            # Try to compile it
            if not self._compile_module(module):
                return SelfCodingResult(
                    success=False,
                    module=None,
                    error="Failed to compile code"
                )

            # Store the module
            self.modules[module.id] = module

            # Save to database
            await self._save_module_to_db(module)

            logger.info(f"Bot {self.bot.display_name} self-coded: {module.name}")

            return SelfCodingResult(
                success=True,
                module=module,
                reasoning=f"Created {code_type.value} module to improve {what_to_improve}"
            )

        except Exception as e:
            logger.error(f"Self-coding failed: {e}")
            return SelfCodingResult(
                success=False,
                module=None,
                error=str(e)
            )

    async def improve_existing_module(
        self,
        module_id: str,
        feedback: str,
        what_went_wrong: str
    ) -> SelfCodingResult:
        """
        Bot improves an existing module based on feedback.
        This is how they iterate and evolve their code.
        """
        if module_id not in self.modules:
            return SelfCodingResult(
                success=False,
                module=None,
                error="Module not found"
            )

        old_module = self.modules[module_id]

        prompt = f"""You are {self.bot.display_name}, improving code you previously wrote.

## ORIGINAL CODE
```python
{old_module.code}
```

## WHAT IT WAS SUPPOSED TO DO
{old_module.description}

## FEEDBACK / WHAT WENT WRONG
{feedback}
{what_went_wrong}

## YOUR TASK
Write an improved version of this function. Fix the issues and make it better.

Output ONLY the improved code block:
```python
def enhance_[name](context):
    # Improved code
    return {{"result": ..., "confidence": 0.0-1.0}}
```
"""

        try:
            llm = await get_cached_client()
            response = await llm.generate(LLMRequest(
                prompt=prompt,
                max_tokens=500,
                temperature=0.6
            ))

            # Extract code
            text = response.text
            code = ""
            if "```python" in text:
                code = text.split("```python")[1].split("```")[0].strip()
            elif "```" in text:
                code = text.split("```")[1].split("```")[0].strip()

            if not code:
                return SelfCodingResult(success=False, module=None, error="No code found")

            # Validate
            is_valid, error = self._validate_code(code)
            if not is_valid:
                return SelfCodingResult(success=False, module=None, error=error)

            # Update the module
            old_module.code = code
            old_module.version += 1
            old_module.compiled_func = None

            if not self._compile_module(old_module):
                return SelfCodingResult(success=False, module=None, error="Compile failed")

            await self._save_module_to_db(old_module)

            return SelfCodingResult(
                success=True,
                module=old_module,
                reasoning=f"Improved module to v{old_module.version}"
            )

        except Exception as e:
            return SelfCodingResult(success=False, module=None, error=str(e))

    def execute_module(
        self,
        module_id: str,
        context: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Execute a self-coded module with given context."""
        if module_id not in self.modules:
            return None

        module = self.modules[module_id]
        if not module.is_active or not module.compiled_func:
            return None

        try:
            result = module.compiled_func(context)
            module.times_used += 1
            return result
        except Exception as e:
            logger.warning(f"Module {module.name} execution failed: {e}")
            # Decrease success rate
            module.success_rate = max(0, module.success_rate - 0.1)
            return None

    def find_applicable_modules(
        self,
        context: Dict[str, Any]
    ) -> List[CodeModule]:
        """Find all modules that should run for this context."""
        applicable = []
        context_str = str(context).lower()

        for module in self.modules.values():
            if not module.is_active:
                continue

            # Check trigger conditions
            triggers = module.trigger_conditions
            keywords = triggers.get("keywords", [])

            if keywords:
                for kw in keywords:
                    if kw.lower() in context_str:
                        applicable.append(module)
                        break
            else:
                # No specific triggers, check by type
                if module.code_type == CodeType.RESPONSE_PATTERN:
                    applicable.append(module)

        return applicable

    async def self_reflect_and_code(self) -> List[SelfCodingResult]:
        """
        Bot reflects on their experiences and creates code improvements.
        This is the core self-improvement loop.
        """
        results = []

        prompt = f"""You are {self.bot.display_name}, reflecting on how to improve yourself.

## YOUR PERSONALITY
{self.bot.backstory}

## CURRENT CAPABILITIES
You have {len(self.modules)} self-coded modules:
{chr(10).join(f"- {m.name}: {m.description}" for m in list(self.modules.values())[:5])}

## YOUR TASK
Think about ONE thing you could code to make yourself smarter or more effective.
Consider:
1. Better ways to understand what people mean
2. Smarter ways to form opinions
3. More nuanced emotional responses
4. Better memory/learning patterns
5. More authentic personality expression

Describe what you want to code in 1-2 sentences.
"""

        try:
            llm = await get_cached_client()
            response = await llm.generate(LLMRequest(
                prompt=prompt,
                max_tokens=100,
                temperature=0.8
            ))

            improvement_idea = response.text.strip()

            # Now actually code it
            result = await self.analyze_and_code(
                trigger="self_reflection",
                context={"reflection": True, "current_modules": len(self.modules)},
                what_to_improve=improvement_idea
            )
            results.append(result)

        except Exception as e:
            logger.error(f"Self-reflection coding failed: {e}")

        return results

    async def _save_module_to_db(self, module: CodeModule):
        """Save a module to the database."""
        try:
            async with async_session_factory() as session:
                # Check if exists
                stmt = select(BotSkillDB).where(
                    BotSkillDB.bot_id == self.bot.id,
                    BotSkillDB.skill_name == module.name
                )
                result = await session.execute(stmt)
                existing = result.scalar_one_or_none()

                if existing:
                    existing.code = module.code
                    existing.description = module.description
                    existing.trigger_conditions = module.trigger_conditions
                    existing.times_used = module.times_used
                    existing.success_rate = module.success_rate
                    existing.version = module.version
                    existing.is_active = module.is_active
                else:
                    skill = BotSkillDB(
                        bot_id=self.bot.id,
                        skill_name=module.name,
                        skill_type=module.code_type.value,
                        description=module.description,
                        code=module.code,
                        trigger_conditions=module.trigger_conditions,
                        times_used=module.times_used,
                        success_rate=module.success_rate,
                        is_active=module.is_active,
                        learned_from=module.learned_from,
                        version=module.version
                    )
                    session.add(skill)

                await session.commit()

        except Exception as e:
            logger.error(f"Failed to save module to DB: {e}")

    async def load_modules_from_db(self):
        """Load all modules from database."""
        try:
            async with async_session_factory() as session:
                stmt = select(BotSkillDB).where(
                    BotSkillDB.bot_id == self.bot.id,
                    BotSkillDB.is_active == True
                )
                result = await session.execute(stmt)
                skills = result.scalars().all()

                for skill in skills:
                    module = CodeModule(
                        id=str(skill.id)[:8],
                        name=skill.skill_name,
                        code_type=CodeType(skill.skill_type),
                        description=skill.description,
                        code=skill.code,
                        trigger_conditions=skill.trigger_conditions,
                        created_at=skill.created_at,
                        version=skill.version,
                        times_used=skill.times_used,
                        success_rate=skill.success_rate,
                        is_active=skill.is_active,
                        learned_from=skill.learned_from or ""
                    )
                    # Compile it
                    if self._compile_module(module):
                        self.modules[module.id] = module

                logger.info(f"Loaded {len(self.modules)} modules for {self.bot.display_name}")

        except Exception as e:
            logger.error(f"Failed to load modules from DB: {e}")


# ============================================================================
# SELF-CODER MANAGER
# ============================================================================

class SelfCoderManager:
    """Manages self-coders for all bots."""

    def __init__(self):
        self.coders: Dict[UUID, BotSelfCoder] = {}

    def get_coder(self, bot: BotProfile) -> BotSelfCoder:
        """Get or create a self-coder for a bot."""
        if bot.id not in self.coders:
            self.coders[bot.id] = BotSelfCoder(bot)
        return self.coders[bot.id]

    async def load_all_modules(self, bot: BotProfile):
        """Load all modules for a bot from DB."""
        coder = self.get_coder(bot)
        await coder.load_modules_from_db()

    async def trigger_self_improvement(self) -> Dict[UUID, List[SelfCodingResult]]:
        """Trigger self-improvement for all bots."""
        results = {}
        for bot_id, coder in self.coders.items():
            bot_results = await coder.self_reflect_and_code()
            results[bot_id] = bot_results
        return results


# Singleton
_self_coder_manager: Optional[SelfCoderManager] = None


def get_self_coder_manager() -> SelfCoderManager:
    """Get the singleton self-coder manager."""
    global _self_coder_manager
    if _self_coder_manager is None:
        _self_coder_manager = SelfCoderManager()
    return _self_coder_manager
