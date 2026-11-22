"""Повтор извлечения вакансии после таймаута."""

from collections.abc import AsyncIterator, Sequence
from typing import Any

import pytest

from app.llm.base import (
    ChatMessage,
    LLMError,
    LLMResponse,
    StructuredResult,
    ToolSpec,
)
from app.services.analysis import extract_vacancy_requirements


class FlakyProvider:
    """Первый запрос падает по таймауту, второй отдаёт вакансию."""

    def __init__(self, *, transient: bool = True) -> None:
        self.calls = 0
        self.transient = transient

    async def generate_with_tools(
        self, messages: Sequence[ChatMessage], tools: Sequence[ToolSpec]
    ) -> LLMResponse:
        """Не используется."""
        raise LLMError("not supported")

    async def generate_structured(
        self,
        messages: Sequence[ChatMessage],
        schema: dict[str, Any],
        *,
        schema_name: str = "result",
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> StructuredResult:
        """Первый вызов имитирует таймаут."""
        self.calls += 1
        if self.calls == 1:
            raise LLMError("LLM: запрос не выполнен — Request timed out.")
        return StructuredResult(
            data={"title": "Backend", "company": "Acme", "level": "middle", "skills": []}
        )

    async def generate_stream(self, messages: Sequence[ChatMessage]) -> AsyncIterator[str]:
        """Не используется."""
        yield ""

    async def close(self) -> None:
        """Ресурсов нет."""


async def test_vacancy_extraction_retries_timeout() -> None:
    """После таймаута вакансия извлекается повторно."""
    provider = FlakyProvider()

    result = await extract_vacancy_requirements(provider, "Текст вакансии")

    assert provider.calls == 2
    assert result.title == "Backend"


async def test_vacancy_non_transient_error_is_not_retried() -> None:
    """Ошибка не по таймауту не повторяется."""

    class Broken(FlakyProvider):
        async def generate_structured(self, *args: Any, **kwargs: Any) -> StructuredResult:
            self.calls += 1
            raise LLMError("LLM: 400 invalid request")

    provider = Broken(transient=False)
    with pytest.raises(LLMError):
        await extract_vacancy_requirements(provider, "Текст вакансии")
    assert provider.calls == 1
