"""Import all models so Alembic can discover them."""
from app.models.base import Base
from app.models.user import User
from app.models.settings import Setting
from app.models.mapping import PersonalMapping, MappingTarget
from app.models.routine import Routine, RoutineStep
from app.models.reminder import Reminder, ShoppingItem, Errand
from app.models.interaction import InteractionEvent, CorrectionLog
from app.models.alias import LearnedAlias, FileReference
from app.models.proactive import (
    ProactiveLog, ModelVersion, BrowserProfile,
    SyncMetadata, MemoryNode, MemoryEdge,
)

__all__ = [
    "Base", "User", "Setting",
    "PersonalMapping", "MappingTarget",
    "Routine", "RoutineStep",
    "Reminder", "ShoppingItem", "Errand",
    "InteractionEvent", "CorrectionLog",
    "LearnedAlias", "FileReference",
    "ProactiveLog", "ModelVersion", "BrowserProfile",
    "SyncMetadata", "MemoryNode", "MemoryEdge",
]
