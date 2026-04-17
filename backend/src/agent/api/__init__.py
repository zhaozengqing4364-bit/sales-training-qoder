"""
Agent Platform API Routes

API endpoints for Agent, Persona, and AgentPersona management.
"""
from .agent_personas import admin_router as agent_persona_admin_router
from .agents import admin_router as agent_admin_router
from .agents import user_router as agent_user_router
from .personas import admin_router as persona_admin_router

__all__ = [
    "agent_admin_router",
    "agent_user_router",
    "persona_admin_router",
    "agent_persona_admin_router",
]
