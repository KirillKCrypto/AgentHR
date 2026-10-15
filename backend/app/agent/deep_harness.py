"""Agent Harness на Deep Agents: готовый harness поверх LangGraph-рантайма.

Заменяет ручную сборку графа «модель → инструменты → модель» на
`create_deep_agent`, сохраняя контракт проекта: тот же результат прогона
(`AgentRunResult`), те же лимиты, аудит каждого шага и checkpoint по `thread_id`.

Решение зафиксировано в `AGENTS.md` (decision log): основным harness проекта
становится Deep Agents; доступ LLM к данным — только через инструменты реестра.
"""

import asyncio
import uuid
from collections.abc import Sequence
from typing import Any

from deepagents import create_deep_agent
from langchain.agents.middleware import ToolErrorMiddleware
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.errors import GraphRecursionError
from langgraph.graph.state import CompiledStateGraph

from app.agent.audit import AuditLogger
from app.agent.langchain_model import ProviderChatModel, to_chat_messages
from app.agent.langchain_tools import build_registry_tools
from app.agent.middleware import (
    LIMIT_MESSAGES,
    MAX_STEPS_STATUS,
    AuditMiddleware,
    LimitsMiddleware,
    tool_error_text,
)
from app.agent.result import AgentRunResult
from app.agent.tools import ToolRegistry
from app.core.config import get_settings
from app.llm.base import ChatMessage, LLMError, LLMProvider

DEFAULT_SYSTEM_PROMPT = (
    "Ты — агент системы AgentHR: она готовит кандидатов к техническим "
    "собеседованиям под конкретную вакансию. Все данные о пользователе, "
    "вакансиях, резюме и графе тем доступны только через инструменты — "
    "используй их, ничего не выдумывай. Отвечай на русском языке, кратко и по делу."
)

# Отношение лимита рекурсии графа к лимиту шагов агента: middleware обязана
# успеть остановить цикл раньше, чем сработает аварийный лимит LangGraph.
_RECURSION_LIMIT_FACTOR = 5


class DeepAgentHarness:
    """Оркестратор агента на Deep Agents с лимитами, аудитом и checkpoint'ами."""

    def __init__(
        self,
        provider: LLMProvider,
        registry: ToolRegistry,
        *,
        audit_logger: AuditLogger | None = None,
        max_steps: int | None = None,
        token_budget: int | None = None,
        timeout_seconds: float | None = None,
        tool_timeout_seconds: float | None = None,
        system_prompt: str | None = None,
        checkpointer: Any | None = None,
    ) -> None:
        """Собирает deep agent из провайдера LLM и реестра инструментов."""
        settings = get_settings()
        self._max_steps = settings.agent_max_steps if max_steps is None else max_steps
        self._token_budget = settings.agent_token_budget if token_budget is None else token_budget
        self._timeout_seconds = (
            settings.agent_timeout_seconds if timeout_seconds is None else timeout_seconds
        )
        self._checkpointer = checkpointer or InMemorySaver()
        self._agent: CompiledStateGraph[Any, Any, Any, Any] = create_deep_agent(
            model=ProviderChatModel(provider=provider),
            tools=build_registry_tools(
                registry,
                timeout_seconds=(
                    settings.agent_tool_timeout_seconds
                    if tool_timeout_seconds is None
                    else tool_timeout_seconds
                ),
            ),
            system_prompt=system_prompt or DEFAULT_SYSTEM_PROMPT,
            middleware=[
                LimitsMiddleware(max_steps=self._max_steps, token_budget=self._token_budget),
                AuditMiddleware(audit_logger),
                # Ошибка инструмента возвращается модели, а не прерывает цикл.
                ToolErrorMiddleware(on_error=tool_error_text),
            ],
            checkpointer=self._checkpointer,
        )

    async def run(
        self,
        messages: Sequence[ChatMessage],
        *,
        session_id: uuid.UUID | None = None,
        thread_id: str | None = None,
    ) -> AgentRunResult:
        """Запускает агентский цикл и возвращает результат прогона.

        `thread_id` группирует checkpoint'ы: повторный запуск с тем же thread_id
        продолжает накопленное состояние сессии.
        """
        thread = thread_id or str(uuid.uuid4())
        config: dict[str, Any] = {
            "configurable": {
                "thread_id": thread,
                "session_id": str(session_id) if session_id is not None else None,
            },
            "recursion_limit": self._max_steps * _RECURSION_LIMIT_FACTOR + 10,
        }
        payload = {
            "messages": [_to_langchain(message) for message in messages],
            "files": {},
        }

        error: str | None = None
        state: dict[str, Any] = {}
        try:
            async with asyncio.timeout(self._timeout_seconds):
                state = await self._agent.ainvoke(payload, config)
        except TimeoutError:
            error = f"Превышен таймаут агента ({self._timeout_seconds} с)"
            state = await self._snapshot_state(config, fallback=payload)
        except GraphRecursionError:
            error = LIMIT_MESSAGES[MAX_STEPS_STATUS].format(limit=self._max_steps)
            state = await self._snapshot_state(config, fallback=payload)
        except LLMError as exc:
            error = f"Ошибка LLM: {exc}"
            state = await self._snapshot_state(config, fallback=payload)

        langchain_messages: list[BaseMessage] = list(state.get("messages") or [])
        out_messages = to_chat_messages(langchain_messages)
        status = self._status(state, out_messages, error)

        return AgentRunResult(
            status=status,
            messages=out_messages,
            final_text=_final_text(out_messages),
            steps=_steps(out_messages),
            input_tokens=_tokens(langchain_messages, "input_tokens"),
            output_tokens=_tokens(langchain_messages, "output_tokens"),
            error=error if error is not None else _limit_error(status),
        )

    def _status(
        self,
        state: dict[str, Any],
        messages: Sequence[ChatMessage],
        error: str | None,
    ) -> str:
        """Определяет статус прогона: ошибка, лимит или успешное завершение."""
        if error is not None:
            if "таймаут" in error.lower():
                return "timeout"
            if error.startswith("Ошибка LLM"):
                return "llm_error"
            return MAX_STEPS_STATUS
        run_status = state.get("run_status")
        if isinstance(run_status, str) and run_status:
            return run_status
        if messages:
            last = messages[-1]
            if last.role == "assistant" and last.content:
                for status, template in LIMIT_MESSAGES.items():
                    prefix = template.split("(")[0].strip()
                    if last.content.startswith(prefix):
                        return status
        return "completed"

    async def _snapshot_state(
        self, config: dict[str, Any], *, fallback: dict[str, Any]
    ) -> dict[str, Any]:
        """Читает состояние из checkpointer'а (для отчёта о прерывании)."""
        try:
            snapshot = await self._agent.aget_state(config)
            return dict(snapshot.values or fallback)
        except Exception:  # noqa: BLE001 — снапшот нужен только для отчёта
            return fallback


def _to_langchain(message: ChatMessage) -> BaseMessage:
    """Конвертирует сообщение AgentHR в сообщение LangChain."""
    if message.role == "system":
        return SystemMessage(content=message.content or "")
    if message.role == "tool":
        return ToolMessage(
            content=message.content or "",
            tool_call_id=message.tool_call_id or "",
        )
    if message.role == "assistant":
        return AIMessage(
            content=message.content or "",
            tool_calls=[
                {"name": call.name, "args": call.arguments, "id": call.id, "type": "tool_call"}
                for call in message.tool_calls
            ],
        )
    return HumanMessage(content=message.content or "")


def _steps(messages: Sequence[ChatMessage]) -> int:
    """Считает шаги прогона: каждый ответ модели — один шаг цикла."""
    return sum(
        1
        for message in messages
        if message.role == "assistant" and not _is_limit_message(message.content)
    )


def _tokens(messages: Sequence[BaseMessage], key: str) -> int:
    """Суммарный расход токенов по всем ответам модели."""
    total = 0
    for message in messages:
        usage = getattr(message, "usage_metadata", None) or {}
        total += int(usage.get(key, 0) or 0)
    return total


def _is_limit_message(content: str | None) -> bool:
    """Проверяет, что сообщение — маркер остановки по лимиту."""
    if not content:
        return False
    return any(
        content.startswith(template.split("(")[0].strip()) for template in LIMIT_MESSAGES.values()
    )


def _limit_error(status: str) -> str | None:
    """Возвращает понятное сообщение для статусов-лимитов."""
    if status in LIMIT_MESSAGES:
        return LIMIT_MESSAGES[status].split("(")[0].strip()
    return None


def _final_text(messages: Sequence[ChatMessage]) -> str | None:
    """Текст последнего ответа ассистента."""
    for message in reversed(messages):
        if message.role == "assistant" and message.content:
            return message.content
    return None
