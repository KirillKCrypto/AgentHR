"""Реестр инструментов агента: описания (JSON Schema) и обработчики."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from jsonschema import ValidationError, validate

from app.llm.base import ToolSpec


class ToolNotFoundError(Exception):
    """Инструмент с таким именем не зарегистрирован."""


class ToolArgumentsError(Exception):
    """Аргументы вызова не соответствуют JSON Schema инструмента."""


@dataclass(frozen=True)
class ToolDefinition:
    """Инструмент агента: описание для LLM и async-обработчик."""

    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., Awaitable[Any]]

    def to_spec(self) -> ToolSpec:
        """Возвращает описание инструмента для LLM-провайдера."""
        return ToolSpec(name=self.name, description=self.description, parameters=self.parameters)


class ToolRegistry:
    """Реестр инструментов: регистрация, поиск, валидация аргументов."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        """Регистрирует инструмент; повторная регистрация имени запрещена."""
        if tool.name in self._tools:
            raise ValueError(f"Инструмент с именем {tool.name!r} уже зарегистрирован")
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolDefinition:
        """Возвращает инструмент по имени."""
        try:
            return self._tools[name]
        except KeyError as exc:
            raise ToolNotFoundError(f"Инструмент {name!r} не зарегистрирован") from exc

    def specs(self) -> list[ToolSpec]:
        """Описания всех инструментов (для передачи LLM)."""
        return [tool.to_spec() for tool in self._tools.values()]

    def validate_arguments(self, name: str, arguments: dict[str, Any]) -> None:
        """Проверяет аргументы вызова по JSON Schema инструмента."""
        tool = self.get(name)
        try:
            validate(instance=arguments, schema=tool.parameters)
        except ValidationError as exc:
            raise ToolArgumentsError(
                f"Аргументы инструмента {name!r} не соответствуют схеме: {exc.message}"
            ) from exc
