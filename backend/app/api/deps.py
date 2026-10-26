"""Общие зависимости FastAPI."""

from collections.abc import AsyncGenerator
from functools import lru_cache
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import decode_token
from app.db.session import get_db
from app.embeddings import create_embedding_provider
from app.embeddings.base import EmbeddingProvider
from app.llm.base import LLMProvider
from app.llm.factory import create_llm_provider
from app.models import User

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Возвращает пользователя по access-токену из заголовка Authorization."""
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized

    try:
        user_id = decode_token(credentials.credentials, expected_type="access")
    except jwt.InvalidTokenError as exc:
        raise unauthorized from exc

    user = await db.get(User, user_id)
    if user is None:
        raise unauthorized
    return user


async def get_llm_provider() -> AsyncGenerator[LLMProvider]:
    """Отдаёт LLM-провайдер на время запроса и закрывает его после."""
    provider = create_llm_provider(get_settings())
    try:
        yield provider
    finally:
        await provider.close()


@lru_cache
def get_embedder() -> EmbeddingProvider:
    """Единый провайдер эмбеддингов (модель загружается лениво, один раз)."""
    return create_embedding_provider(get_settings())


CurrentUser = Annotated[User, Depends(get_current_user)]
DbSession = Annotated[AsyncSession, Depends(get_db)]
LlmProvider = Annotated[LLMProvider, Depends(get_llm_provider)]
Embedder = Annotated[EmbeddingProvider, Depends(get_embedder)]
