"""Адаптер инструментов AgentHR к интерфейсу LangChain (`BaseTool`).

Инструмент остаётся описанным нашей JSON Schema (`ToolRegistry`): схема
передаётся модели дословно, а аргументы валидируются реестром — правила
проекта (JSON Schema + валидация на каждый вызов) сохраняются.
"""

import asyncio
from typing import Any

from langchain_core.tools import BaseTool
from pydantic import ConfigDict

from app.agent.tools import ToolRegistry


def _to_text(result: Any) -> str:
    """Приводит результат инструмента к тексту для сообщения LLM."""
    if isinstance(result, str):
        return result
    import json

    return json.dumps(result, ensure_ascii=False, default=str)


class RegistryTool(BaseTool):
    """Инструмент из `ToolRegistry`, вызываемый агентом LangChain."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    """Имя инструмента."""

    description: str
    """Описание инструмента для модели."""

    parameters: dict[str, Any]
    """JSON Schema аргументов (передаётся модели дословно)."""

    registry: Any
    """Реестр инструментов (`ToolRegistry`)."""

    timeout_seconds: float = 30.0
    """Таймаут одного вызова инструмента."""

    @property
    def tool_call_schema(self) -> dict[str, Any]:  # type: ignore[override]
        """Схема вызова для модели — наша JSON Schema без пересборки в pydantic."""
        return self.parameters

    async def _arun(self, **kwargs: Any) -> str:
        """Валидирует аргументы и вызывает обработчик с таймаутом."""
        registry: ToolRegistry = self.registry
        try:
            registry.validate_arguments(self.name, kwargs)
            tool = registry.get(self.name)
            result = await asyncio.wait_for(tool.handler(**kwargs), timeout=self.timeout_seconds)
        except TimeoutError as exc:
            message = f"Таймаут инструмента {self.name!r} ({self.timeout_seconds} с)"
            raise TimeoutError(message) from exc
        return _to_text(result)

    def _run(self, **kwargs: Any) -> str:
        """Синхронный вызов не поддерживается: обработчики инструментов async."""
        message = f"Инструмент {self.name!r} вызывается только асинхронно (_arun)"
        raise NotImplementedError(message)


def build_registry_tools(registry: ToolRegistry, *, timeout_seconds: float) -> list[RegistryTool]:
    """Собирает инструменты LangChain из реестра AgentHR."""
    return [
        RegistryTool(
            name=spec.name,
            description=spec.description,
            parameters=spec.parameters,
            registry=registry,
            timeout_seconds=timeout_seconds,
        )
        for spec in registry.specs()
    ]
