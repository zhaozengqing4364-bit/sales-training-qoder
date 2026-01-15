"""
Admin API module

Contains admin endpoints for:
- User management
- Training records management
- System logs
"""
from .admin import router as admin_router
from .users import router as users_router
from .training_records import router as training_records_router
from .system_logs import router as system_logs_router

__all__ = [
    "admin_router",
    "users_router",
    "training_records_router",
    "system_logs_router",
]
