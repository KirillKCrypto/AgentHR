"""Middleware агентского цикла: аудит действий и лимиты (шаги, токены).

Deep Agents строится на LangChain-middleware, поэтому и аудит, и лимиты
встроены сюда — правила проекта сохраняются: каждый вызов инструмента и
каждый вызов модели попадают в audit-лог, а цикл ограничен по шагам и токенам.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated, Any, NotRequired

from langchain.agents.middleware.types import (
    AgentMiddleware,
    AgentState,
    PrivateStateAttr,
    ToolCallRequest,
    hook_config,
)
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.channels.untracked_value import UntrackedValue
from langgraph.config import get_config
from langgraph.runtime import Runtime

from app.agent.audit import AgentActionRecord, AuditLogger
from app.agent.tools import ToolArgumentsError, ToolNotFoundError

MAX_STEPS_STATUS = "max_steps"
TOKEN_BUDGET_STATUS = "token_budget"

# Тексты-маркеры лимитов: по ним harness определяет причину остановки,
# если поле состояния недоступно.
LIMIT_MESSAGES = {
    MAX_STEPS_STATUS: "Достигнут лимит шагов агента ({limit}).",
    TOKEN_BUDGET_STATUS: "Исчерпан бюджет токенов агента ({limit}).",
}


class AgentRunState(AgentState[Any]):
    """Состояние прогона: номер шага, расход токенов и причина остановки."""

    # Номер текущего вызова модели: им нумеруются записи аудита (шаг 1, 2, ...).
    audit_step: NotRequired[Annotated[int, UntrackedValue, PrivateStateAttr]]
    # Число вызовов модели в текущем прогоне — для контроля лимита шагов.
    run_model_calls: NotRequired[Annotated[int, UntrackedValue, PrivateStateAttr]]
    # Расход токенов текущего прогона — для контроля бюджета.
    run_input_tokens: NotRequired[Annotated[int, UntrackedValue, PrivateStateAttr]]
    run_output_tokens: NotRequired[Annotated[int, UntrackedValue, PrivateStateAttr]]
    # Причина остановки прогона: сохраняется в checkpoint'е, чтобы harness её прочитал.
    run_status: NotRequired[Annotated[str | None, PrivateStateAttr]]


def _session_id_from_config() -> uuid.UUID | None:
    """Достаёт `session_id` из конфигурации запуска графа."""
    raw = (get_config().get("configurable") or {}).get("session_id")
    if isinstance(raw, str):
        try:
            return uuid.UUID(raw)
        except ValueError:
            return None
    return None


def _usage_of(message: Any) -> tuple[int, int]:
    """Возвращает (input_tokens, output_tokens) из `usage_metadata` сообщения."""
    usage = getattr(message, "usage_metadata", None) or {}
    return int(usage.get("input_tokens", 0)), int(usage.get("output_tokens", 0))


def _reset_run_counters() -> dict[str, Any]:
    """Сбрасывает счётчики прогона в начале каждого запуска агента."""
    return {
        "audit_step": 0,
        "run_model_calls": 0,
        "run_input_tokens": 0,
        "run_output_tokens": 0,
        "run_status": None,
    }


def tool_error_text(exc: Exception, request: ToolCallRequest) -> str:
    """Формирует текст ошибки инструмента, возвращаемый модели.

    Ошибка не прерывает цикл: модель получает её как `ToolMessage(status="error")`
    и может исправить аргументы или выбрать другой инструмент.
    """
    tool_name = str((request.tool_call or {}).get("name") or "")
    if isinstance(exc, ToolArgumentsError):
        return str(exc)
    if isinstance(exc, ToolNotFoundError):
        return str(exc)
    if isinstance(exc, TimeoutError):
        return str(exc)
    return f"Ошибка инструмента {tool_name!r}: {exc}"


class AuditMiddleware(AgentMiddleware[AgentRunState, Any, Any]):
    """Пишет в audit-лог каждый вызов модели и каждый вызов инструмента."""

    state_schema = AgentRunState

    def __init__(self, audit_logger: AuditLogger | None) -> None:
        """Создаёт middleware; без логгера все методы ничего не делают."""
        super().__init__()
        self._audit_logger = audit_logger

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Any]],
    ) -> Any:
        """Логирует вызов инструмента: имя, аргументы, результат, время, статус."""
        if self._audit_logger is None:
            return await handler(request)

        tool_call = request.tool_call
        tool_name = str(tool_call.get("name") or "")
        arguments = dict(tool_call.get("args") or {})
        step = int((request.state or {}).get("audit_step", 0))
        started = time.perf_counter()

        try:
            message = await handler(request)
        except Exception as exc:  # сначала аудит, потом пробрасываем исключение
            await self._write(
                step=step,
                status="error",
                duration_ms=int((time.perf_counter() - started) * 1000),
                tool_name=tool_name,
                arguments=arguments,
                result={"error": str(exc)},
            )
            raise

        status = "error" if getattr(message, "status", None) == "error" else "success"
        await self._write(
            step=step,
            status=status,
            duration_ms=int((time.perf_counter() - started) * 1000),
            tool_name=tool_name,
            arguments=arguments,
            result=getattr(message, "content", None),
        )
        return message

    async def aafter_model(
        self, state: AgentRunState, runtime: Runtime[Any]
    ) -> dict[str, Any] | None:
        """Логирует вызов модели: номер шага, расход токенов.

        Номер шага ведёт сам аудит: вызовы инструментов, инициированные моделью,
        попадают в тот же шаг, что и породивший их вызов модели.
        """
        messages = state.get("messages") or []
        if not messages:
            return None
        step = int(state.get("audit_step", 0)) + 1
        if self._audit_logger is not None:
            input_tokens, output_tokens = _usage_of(messages[-1])
            await self._write(
                step=step,
                status="success",
                duration_ms=0,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
        return {"audit_step": step}

    async def _write(
        self,
        *,
        step: int,
        status: str,
        duration_ms: int,
        tool_name: str | None = None,
        arguments: dict[str, Any] | None = None,
        result: Any = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
    ) -> None:
        """Записывает строку аудит-лога."""
        if self._audit_logger is None:  # pragma: no cover — защита от гонок
            return
        await self._audit_logger.log(
            AgentActionRecord(
                session_id=_session_id_from_config(),
                step=step,
                status=status,
                duration_ms=duration_ms,
                tool_name=tool_name,
                arguments=arguments,
                result=result,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
        )


class LimitsMiddleware(AgentMiddleware[AgentRunState, Any, Any]):
    """Останавливает цикл при превышении лимитов шагов и токенов."""

    state_schema = AgentRunState

    def __init__(self, *, max_steps: int, token_budget: int) -> None:
        """Создаёт middleware с лимитами прогона."""
        super().__init__()
        self.max_steps = max_steps
        self.token_budget = token_budget

    @hook_config(can_jump_to=["end"])
    def before_model(self, state: AgentRunState, runtime: Runtime[Any]) -> dict[str, Any] | None:
        """Проверяет лимиты перед очередным вызовом модели."""
        return self._check(state)

    @hook_config(can_jump_to=["end"])
    async def abefore_model(
        self, state: AgentRunState, runtime: Runtime[Any]
    ) -> dict[str, Any] | None:
        """Асинхронная проверка лимитов перед вызовом модели."""
        return self._check(state)

    def before_agent(self, state: AgentRunState, runtime: Runtime[Any]) -> dict[str, Any]:
        """Обнуляет счётчики прогона в начале каждого запуска."""
        return _reset_run_counters()

    async def abefore_agent(self, state: AgentRunState, runtime: Runtime[Any]) -> dict[str, Any]:
        """Асинхронно обнуляет счётчики прогона."""
        return _reset_run_counters()

    def after_model(self, state: AgentRunState, runtime: Runtime[Any]) -> dict[str, Any] | None:
        """Накапливает шаги и токены после вызова модели."""
        return self._accumulate(state)

    async def aafter_model(
        self, state: AgentRunState, runtime: Runtime[Any]
    ) -> dict[str, Any] | None:
        """Асинхронное накопление шагов и токенов."""
        return self._accumulate(state)

    def _check(self, state: AgentRunState) -> dict[str, Any] | None:
        """Возвращает команду остановки, если лимит исчерпан."""
        calls = int(state.get("run_model_calls", 0))
        if calls >= self.max_steps:
            return self._stop(MAX_STEPS_STATUS, self.max_steps)
        total = int(state.get("run_input_tokens", 0)) + int(state.get("run_output_tokens", 0))
        if total >= self.token_budget:
            return self._stop(TOKEN_BUDGET_STATUS, self.token_budget)
        return None

    def _accumulate(self, state: AgentRunState) -> dict[str, Any]:
        """Возвращает обновление счётчиков шагов и токенов прогона."""
        messages = state.get("messages") or []
        input_tokens, output_tokens = _usage_of(messages[-1]) if messages else (0, 0)
        return {
            "run_model_calls": int(state.get("run_model_calls", 0)) + 1,
            "run_input_tokens": int(state.get("run_input_tokens", 0)) + input_tokens,
            "run_output_tokens": int(state.get("run_output_tokens", 0)) + output_tokens,
        }

    def _stop(self, status: str, limit: int) -> dict[str, Any]:
        """Формирует остановку цикла с понятным сообщением."""
        text = LIMIT_MESSAGES[status].format(limit=limit)
        return {
            "jump_to": "end",
            "messages": [AIMessage(content=text)],
            "run_status": status,
        }
