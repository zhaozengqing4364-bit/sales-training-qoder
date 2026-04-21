"""
Shared fixtures for contract test modules.
"""

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.service import create_access_token
from common.db.models import User


@pytest_asyncio.fixture
async def contract_auth_headers(
    test_user: User,
    test_db: AsyncSession,
) -> dict[str, str]:
    """Always provide a valid JWT header bound to an existing test user."""
    test_user.role = "admin"
    await test_db.commit()
    await test_db.refresh(test_user)
    token = create_access_token(data={"sub": str(test_user.user_id)})
    return {"Authorization": f"Bearer {token}"}
