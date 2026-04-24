"""
Admin API module

Contains admin endpoints for:
- User management
- Training records management
- System logs
"""
from .admin import router as admin_router
from .business_rules import router as business_rules_router
from .knowledge_answer_config import router as knowledge_answer_config_router
from .system_logs import router as system_logs_router
from .training_records import router as training_records_router
from .users import router as users_router

__all__ = [
    "admin_router",
    "business_rules_router",
    "users_router",
    "training_records_router",
    "system_logs_router",
    "knowledge_answer_config_router",
]
