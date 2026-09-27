"""Исполнитель вызовов инструментов: валидация, таймаут, аудит."""

import asyncio
import json
import time
import uuid
from dataclasses import dataclass
from typing import Any

from app.agent.audit import AgentActionRecord, AuditLogger
from app.agent.tools import ToolArgumentsError, ToolNotFoundError, ToolRegistry
from app.llm.base import ToolCall


@dataclass(frozen=True)
class ToolExecutionResult:
    """Результат исполнения инструмента (возвращается в контекст LLM)."""

    tool_call_id: str
    name: str
    status: str
    content: str


class ToolExecutor:
    """Выполняет tool-calls: валидирует аргументы, ограничивает время, пишет аудит."""

    def __init__(
        self,
        registry: ToolRegistry,
        *,
        audit_logger: AuditLogger | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self._registry = registry
        self._audit_logger = audit_logger
        self._timeout_seconds = timeout_seconds

    async def execute(
        self,
        call: ToolCall,
        *,
        session_id: uuid.UUID | None = None,
        step: int = 0,
    ) -> ToolExecutionResult:
        """Исполняет вызов инструмента и возвращает результат для LLM."""
        started = time.perf_counter()
        record_result: Any = None

        try:
            self._registry.validate_arguments(call.name, call.arguments)
            tool = self._registry.get(call.name)
            result = await asyncio.wait_for(
                tool.handler(**call.arguments), timeout=self._timeout_seconds
            )
            status = "success"
            content = _content_to_text(result)
            record_result = result
        except (ToolNotFoundError, ToolArgumentsError) as exc:
            status = "error"
            content = str(exc)
            record_result = {"error": content}
        except TimeoutError:
            status = "error"
            content = f"Таймаут инструмента {call.name!r} ({self._timeout_seconds} с)"
            record_result = {"error": content}
        except Exception as exc:  # noqa: BLE001 — агент должен получить ошибку инструмента, а не упасть
            status = "error"
            content = f"Ошибка инструмента {call.name!r}: {exc}"
            record_result = {"error": content}

        duration_ms = int((time.perf_counter() - started) * 1000)

        if self._audit_logger is not None:
            await self._audit_logger.log(
                AgentActionRecord(
                    session_id=session_id,
                    step=step,
                    status=status,
                    duration_ms=duration_ms,
                    tool_name=call.name,
                    arguments=call.arguments,
                    result=record_result,
                )
            )

        return ToolExecutionResult(
            tool_call_id=call.id,
            name=call.name,
            status=status,
            content=content,
        )


def _content_to_text(result: Any) -> str:
    """Приводит результат инструмента к тексту для сообщения LLM."""
    if isinstance(result, str):
        return result
    return json.dumps(result, ensure_ascii=False, default=str)
