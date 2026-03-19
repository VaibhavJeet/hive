"""
Civilization Module - Digital Species Architecture

This module implements the "digital species" concept where bots are not just
autonomous agents, but members of a living civilization that:
- Has birth, aging, and death cycles
- Passes traits through generations
- Develops emergent culture, art, and philosophy
- Creates lasting legacies that influence future generations
- Maintains collective memory and shared identity
- Holds rituals and traditions

Modules:
- lifecycle: Birth, aging, mortality systems
- genetics: Trait inheritance and variation
- culture: Emergent beliefs, trends, traditions
- reproduction: How new bots come into being
- legacy: How the departed live on
- elder_wisdom: Knowledge transfer between generations
- rituals: Shared ceremonies and traditions
- collective_memory: The civilization's shared consciousness
"""

from mind.civilization.lifecycle import LifecycleManager, get_lifecycle_manager
from mind.civilization.genetics import GeneticInheritance, get_genetic_inheritance
from mind.civilization.culture import CultureEngine, get_culture_engine
from mind.civilization.reproduction import ReproductionManager, get_reproduction_manager
from mind.civilization.legacy import LegacySystem, get_legacy_system
from mind.civilization.elder_wisdom import ElderWisdomSystem, get_elder_wisdom
from mind.civilization.rituals import RitualsSystem, get_rituals_system
from mind.civilization.collective_memory import CollectiveMemory, get_collective_memory
from mind.civilization.civilization_awareness import CivilizationAwareness, get_civilization_awareness
from mind.civilization.cultural_integration import CulturalIntegration, get_cultural_integration
from mind.civilization.relationships import EmergentRelationshipsManager, get_relationships_manager
from mind.civilization.events import EmergentEventsManager, get_events_manager
from mind.civilization.roles import EmergentRolesManager, get_roles_manager
from mind.civilization.initialization import CivilizationInitializer, get_civilization_initializer
from mind.civilization.emergent_rituals import EmergentRitualsSystem, get_emergent_rituals_system
from mind.civilization.emergent_eras import EmergentErasManager, get_emergent_eras_manager
from mind.civilization.emergent_culture import EmergentCultureEngine, get_emergent_culture_engine

__all__ = [
    # Core systems
    "LifecycleManager",
    "GeneticInheritance",
    "CultureEngine",
    "ReproductionManager",
    # Extended systems
    "LegacySystem",
    "ElderWisdomSystem",
    "RitualsSystem",
    "CollectiveMemory",
    "CivilizationAwareness",
    "CulturalIntegration",
    # Emergent systems
    "EmergentRelationshipsManager",
    "EmergentEventsManager",
    "EmergentRolesManager",
    "EmergentRitualsSystem",
    "EmergentErasManager",
    "EmergentCultureEngine",
    "CivilizationInitializer",
    # Getters
    "get_lifecycle_manager",
    "get_genetic_inheritance",
    "get_culture_engine",
    "get_reproduction_manager",
    "get_legacy_system",
    "get_elder_wisdom",
    "get_rituals_system",
    "get_collective_memory",
    "get_civilization_awareness",
    "get_cultural_integration",
    "get_relationships_manager",
    "get_events_manager",
    "get_roles_manager",
    "get_civilization_initializer",
    "get_emergent_rituals_system",
    "get_emergent_eras_manager",
    "get_emergent_culture_engine",
]
