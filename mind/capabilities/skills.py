"""
Skills System - Modular, pluggable capabilities for bots.

Skills are self-contained units of functionality that bots can use.
Examples: weather lookup, code execution, calendar management, etc.

Skills can be:
- Built-in (shipped with the platform)
- Community (installed from registry)
- Custom (user-defined)
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional
from pathlib import Path
import importlib.util
import json

logger = logging.getLogger(__name__)


class SkillCategory(str, Enum):
    """Categories of skills."""
    INFORMATION = "information"  # Weather, news, search
    PRODUCTIVITY = "productivity"  # Calendar, reminders, notes
    COMMUNICATION = "communication"  # Email, messaging
    DEVELOPMENT = "development"  # Code, git, APIs
    MEDIA = "media"  # Images, audio, video
    UTILITY = "utility"  # Calculations, conversions
    ENTERTAINMENT = "entertainment"  # Games, jokes, trivia
    CUSTOM = "custom"


@dataclass
class SkillParameter:
    """A parameter for a skill."""
    name: str
    description: str
    type: str = "string"  # string, number, boolean, array, object
    required: bool = False
    default: Any = None
    enum: Optional[list] = None


@dataclass
class SkillDefinition:
    """Definition/metadata for a skill."""
    id: str
    name: str
    description: str
    version: str = "1.0.0"
    category: SkillCategory = SkillCategory.UTILITY
    author: str = ""
    parameters: list[SkillParameter] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)
    requires_api_key: bool = False
    api_key_env_var: Optional[str] = None

    def to_tool_schema(self) -> dict:
        """Convert to OpenAI/Anthropic tool schema format."""
        properties = {}
        required = []

        for param in self.parameters:
            properties[param.name] = {
                "type": param.type,
                "description": param.description,
            }
            if param.enum:
                properties[param.name]["enum"] = param.enum
            if param.required:
                required.append(param.name)

        return {
            "type": "function",
            "function": {
                "name": self.id,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                }
            }
        }


@dataclass
class SkillResult:
    """Result from executing a skill."""
    success: bool
    data: Any = None
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    def to_text(self) -> str:
        """Format result as text for bot consumption."""
        if not self.success:
            return f"Error: {self.error}"
        if isinstance(self.data, str):
            return self.data
        if isinstance(self.data, dict):
            return json.dumps(self.data, indent=2)
        return str(self.data)


class Skill(ABC):
    """
    Abstract base class for skills.

    Implement this to create custom skills.
    """

    @property
    @abstractmethod
    def definition(self) -> SkillDefinition:
        """Get the skill definition."""
        pass

    @abstractmethod
    async def execute(self, **params) -> SkillResult:
        """Execute the skill with given parameters."""
        pass

    async def validate_params(self, **params) -> Optional[str]:
        """Validate parameters. Returns error message if invalid."""
        for param in self.definition.parameters:
            if param.required and param.name not in params:
                return f"Missing required parameter: {param.name}"
        return None


class WeatherSkill(Skill):
    """Get weather information for a location."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key

    @property
    def definition(self) -> SkillDefinition:
        return SkillDefinition(
            id="weather",
            name="Weather",
            description="Get current weather and forecast for a location",
            category=SkillCategory.INFORMATION,
            parameters=[
                SkillParameter(
                    name="location",
                    description="City name or coordinates",
                    type="string",
                    required=True,
                ),
                SkillParameter(
                    name="units",
                    description="Temperature units",
                    type="string",
                    enum=["celsius", "fahrenheit"],
                    default="celsius",
                ),
            ],
            examples=[
                "What's the weather in Tokyo?",
                "Will it rain in London tomorrow?",
            ],
            requires_api_key=True,
            api_key_env_var="WEATHER_API_KEY",
        )

    async def execute(self, location: str, units: str = "celsius", **kwargs) -> SkillResult:
        """Get weather for location."""
        # Simplified implementation - in production, use actual weather API
        import aiohttp

        if not self.api_key:
            return SkillResult(
                success=False,
                error="Weather API key not configured"
            )

        try:
            async with aiohttp.ClientSession() as session:
                # Using OpenWeatherMap API as example
                url = "https://api.openweathermap.org/data/2.5/weather"
                params = {
                    "q": location,
                    "appid": self.api_key,
                    "units": "metric" if units == "celsius" else "imperial",
                }

                async with session.get(url, params=params) as resp:
                    if resp.status != 200:
                        return SkillResult(
                            success=False,
                            error=f"Weather API error: {resp.status}"
                        )

                    data = await resp.json()

                    return SkillResult(
                        success=True,
                        data={
                            "location": data["name"],
                            "temperature": data["main"]["temp"],
                            "feels_like": data["main"]["feels_like"],
                            "humidity": data["main"]["humidity"],
                            "description": data["weather"][0]["description"],
                            "units": units,
                        }
                    )

        except Exception as e:
            return SkillResult(success=False, error=str(e))


class CalculatorSkill(Skill):
    """Perform mathematical calculations."""

    @property
    def definition(self) -> SkillDefinition:
        return SkillDefinition(
            id="calculator",
            name="Calculator",
            description="Perform mathematical calculations",
            category=SkillCategory.UTILITY,
            parameters=[
                SkillParameter(
                    name="expression",
                    description="Mathematical expression to evaluate",
                    type="string",
                    required=True,
                ),
            ],
            examples=[
                "Calculate 15% of 200",
                "What is 2^10?",
            ],
        )

    async def execute(self, expression: str, **kwargs) -> SkillResult:
        """Evaluate mathematical expression."""
        import math
        import re

        try:
            # Sanitize - only allow safe math operations
            allowed = set("0123456789+-*/().^ ")
            if not all(c in allowed or c.isalpha() for c in expression):
                return SkillResult(
                    success=False,
                    error="Invalid characters in expression"
                )

            # Replace ^ with ** for exponentiation
            expr = expression.replace("^", "**")

            # Create safe evaluation context
            safe_dict = {
                "abs": abs,
                "round": round,
                "min": min,
                "max": max,
                "sum": sum,
                "pow": pow,
                "sqrt": math.sqrt,
                "sin": math.sin,
                "cos": math.cos,
                "tan": math.tan,
                "log": math.log,
                "log10": math.log10,
                "pi": math.pi,
                "e": math.e,
            }

            result = eval(expr, {"__builtins__": {}}, safe_dict)

            return SkillResult(
                success=True,
                data={"expression": expression, "result": result}
            )

        except Exception as e:
            return SkillResult(success=False, error=f"Calculation error: {e}")


class SkillRegistry:
    """
    Registry for managing and discovering skills.

    Handles skill registration, discovery, and execution.
    """

    def __init__(self):
        self._skills: dict[str, Skill] = {}
        self._register_builtin_skills()

    def _register_builtin_skills(self) -> None:
        """Register built-in skills."""
        self.register(CalculatorSkill())
        # WeatherSkill requires API key, register when configured
        # self.register(WeatherSkill(api_key=...))

    def register(self, skill: Skill) -> None:
        """Register a skill."""
        skill_id = skill.definition.id
        if skill_id in self._skills:
            logger.warning(f"Overwriting existing skill: {skill_id}")
        self._skills[skill_id] = skill
        logger.info(f"Registered skill: {skill_id}")

    def unregister(self, skill_id: str) -> bool:
        """Unregister a skill."""
        if skill_id in self._skills:
            del self._skills[skill_id]
            return True
        return False

    def get(self, skill_id: str) -> Optional[Skill]:
        """Get a skill by ID."""
        return self._skills.get(skill_id)

    def list_skills(
        self,
        category: Optional[SkillCategory] = None
    ) -> list[SkillDefinition]:
        """List all registered skills."""
        skills = []
        for skill in self._skills.values():
            defn = skill.definition
            if category is None or defn.category == category:
                skills.append(defn)
        return skills

    def get_tool_schemas(self) -> list[dict]:
        """Get all skills as tool schemas for LLM function calling."""
        return [skill.definition.to_tool_schema() for skill in self._skills.values()]

    async def execute(self, skill_id: str, **params) -> SkillResult:
        """Execute a skill by ID."""
        skill = self.get(skill_id)
        if not skill:
            return SkillResult(
                success=False,
                error=f"Skill not found: {skill_id}"
            )

        # Validate parameters
        error = await skill.validate_params(**params)
        if error:
            return SkillResult(success=False, error=error)

        # Execute
        try:
            return await skill.execute(**params)
        except Exception as e:
            logger.error(f"Skill execution error ({skill_id}): {e}")
            return SkillResult(success=False, error=str(e))

    def load_from_directory(self, directory: Path) -> int:
        """
        Load skills from a directory.

        Each .py file should contain a class that extends Skill.
        Returns the number of skills loaded.
        """
        loaded = 0

        if not directory.exists():
            return 0

        for file_path in directory.glob("*.py"):
            if file_path.name.startswith("_"):
                continue

            try:
                spec = importlib.util.spec_from_file_location(
                    file_path.stem, file_path
                )
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                    # Find Skill subclasses
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if (isinstance(attr, type) and
                            issubclass(attr, Skill) and
                            attr is not Skill):
                            skill = attr()
                            self.register(skill)
                            loaded += 1

            except Exception as e:
                logger.error(f"Failed to load skill from {file_path}: {e}")

        return loaded


# Global registry instance
_global_registry: Optional[SkillRegistry] = None


def get_skill_registry() -> SkillRegistry:
    """Get the global skill registry."""
    global _global_registry
    if _global_registry is None:
        _global_registry = SkillRegistry()
    return _global_registry
