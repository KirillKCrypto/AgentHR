"""Agent Harness: цикл «модель → инструменты → модель» на графе LangGraph."""

import asyncio
import operator
import time
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Annotated, Any, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from app.agent.audit import AgentActionRecord, AuditLogger
from app.agent.executor import ToolExecutor
from app.agent.tools import ToolRegistry
from app.core.config import get_settings
from app.llm.base import ChatMessage, LLMError, LLMProvider, LLMUsage, ToolSpec


class AgentState(TypedDict):
    """Состояние агентского цикла (сохраняется checkpointer'ом по `thread_id`)."""

    messages: Annotated[list[ChatMessage], operator.add]
    step: int
    input_tokens: int
    output_tokens: int
    finished: bool
    error: str | None


@dataclass(frozen=True)
class AgentRunResult:
    """Результат прогона агента."""

    status: str
    messages: list[ChatMessage]
    final_text: str | None
    steps: int
    input_tokens: int
    output_tokens: int
    error: str | None = None


class AgentHarness:
    """Оркестратор агента: граф с лимитами (шаги, токены, таймаут) и аудит-логом."""

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
    ) -> None:
        settings = get_settings()
        self._provider = provider
        self._tool_specs: list[ToolSpec] = registry.specs()
        self._audit_logger = audit_logger
        self._max_steps = settings.agent_max_steps if max_steps is None else max_steps
        self._token_budget = (
            settings.agent_token_budget if token_budget is None else token_budget
        )
        self._timeout_seconds = (
            settings.agent_timeout_seconds if timeout_seconds is None else timeout_seconds
        )
        self._executor = ToolExecutor(
            registry,
            audit_logger=audit_logger,
            timeout_seconds=(
                settings.agent_tool_timeout_seconds
                if tool_timeout_seconds is None
                else tool_timeout_seconds
            ),
        )
        self._checkpointer = InMemorySaver()
        self._graph = self._build_graph()

    async def run(
        self,
        messages: Sequence[ChatMessage],
        *,
        session_id: uuid.UUID | None = None,
        thread_id: str | None = None,
    ) -> AgentRunResult:
        """Запускает агентский цикл.

        `thread_id` группирует checkpoint'ы: повторный запуск с тем же thread_id
        продолжает накопленное состояние сессии.
        """
        thread = thread_id or str(uuid.uuid4())
        config: RunnableConfig = {
            "configurable": {
                "thread_id": thread,
                "session_id": str(session_id) if session_id is not None else None,
            }
        }
        initial: AgentState = {
            "messages": list(messages),
            "step": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "finished": False,
            "error": None,
        }

        error: str | None = None
        try:
            async with asyncio.timeout(self._timeout_seconds):
                state: AgentState = await self._graph.ainvoke(initial, config)
        except TimeoutError:
            error = f"Превышен таймаут агента ({self._timeout_seconds} с)"
            state = await self._snapshot_state(config, fallback=initial)

        messages_out = list(state.get("messages", []))
        status = "timeout" if error else (state.get("error") or "completed")
        if error:
            error_message: str | None = error
        elif state.get("error"):
            # для лимитов/ошибок LLM понятное сообщение лежит в последнем ответе ассистента
            error_message = _final_text(messages_out) or state["error"]
        else:
            error_message = None

        return AgentRunResult(
            status=status,
            messages=messages_out,
            final_text=_final_text(messages_out),
            steps=state.get("step", 0),
            input_tokens=state.get("input_tokens", 0),
            output_tokens=state.get("output_tokens", 0),
            error=error_message,
        )

    def _build_graph(self) -> Any:
        builder = StateGraph(AgentState)
        builder.add_node("call_model", self._call_model)
        builder.add_node("execute_tools", self._execute_tools)
        builder.add_edge(START, "call_model")
        builder.add_conditional_edges(
            "call_model",
            _route_after_model,
            {"tools": "execute_tools", "end": END},
        )
        builder.add_edge("execute_tools", "call_model")
        return builder.compile(checkpointer=self._checkpointer)

    async def _call_model(self, state: AgentState, config: RunnableConfig) -> dict[str, Any]:
        step = state["step"]
        limit = self._limit_reason(state)
        if limit is not None:
            status, message = limit
            return {
                "messages": [ChatMessage(role="assistant", content=message)],
                "finished": True,
                "error": status,
            }

        started = time.perf_counter()
        try:
            response = await self._provider.generate_with_tools(
                state["messages"], self._tool_specs
            )
        except LLMError as exc:
            duration_ms = int((time.perf_counter() - started) * 1000)
            await self._log_llm_action(config, step, "error", duration_ms)
            return {
                "messages": [ChatMessage(role="assistant", content=f"Ошибка LLM: {exc}")],
                "finished": True,
                "error": "llm_error",
            }

        duration_ms = int((time.perf_counter() - started) * 1000)
        usage = response.usage or LLMUsage()
        await self._log_llm_action(config, step, "success", duration_ms, usage)

        return {
            "messages": [
                ChatMessage(
                    role="assistant",
                    content=response.content,
                    tool_calls=response.tool_calls,
                )
            ],
            "step": step + 1,
            "input_tokens": state["input_tokens"] + (usage.input_tokens or 0),
            "output_tokens": state["output_tokens"] + (usage.output_tokens or 0),
            "finished": not response.tool_calls,
            "error": None,
        }

    async def _execute_tools(
        self, state: AgentState, config: RunnableConfig
    ) -> dict[str, Any]:
        last_message = state["messages"][-1]
        session_id = _session_id_from(config)
        tool_messages: list[ChatMessage] = []
        for call in last_message.tool_calls:
            result = await self._executor.execute(
                call, session_id=session_id, step=state["step"]
            )
            tool_messages.append(
                ChatMessage(
                    role="tool",
                    content=result.content,
                    tool_call_id=result.tool_call_id,
                )
            )
        return {"messages": tool_messages}

    def _limit_reason(self, state: AgentState) -> tuple[str, str] | None:
        if state["step"] >= self._max_steps:
            return "max_steps", f"Достигнут лимит шагов агента ({self._max_steps})."
        total_tokens = state["input_tokens"] + state["output_tokens"]
        if total_tokens >= self._token_budget:
            return "token_budget", f"Исчерпан бюджет токенов агента ({self._token_budget})."
        return None

    async def _log_llm_action(
        self,
        config: RunnableConfig,
        step: int,
        status: str,
        duration_ms: int,
        usage: LLMUsage | None = None,
    ) -> None:
        if self._audit_logger is None:
            return
        await self._audit_logger.log(
            AgentActionRecord(
                session_id=_session_id_from(config),
                step=step,
                status=status,
                duration_ms=duration_ms,
                input_tokens=usage.input_tokens if usage else None,
                output_tokens=usage.output_tokens if usage else None,
            )
        )

    async def _snapshot_state(
        self, config: RunnableConfig, *, fallback: AgentState
    ) -> AgentState:
        try:
            snapshot = await self._graph.aget_state(config)
            return snapshot.values or fallback
        except Exception:  # noqa: BLE001 — снапшот нужен только для отчёта о таймауте
            return fallback


def _route_after_model(state: AgentState) -> str:
    return "end" if state["finished"] else "tools"


def _session_id_from(config: RunnableConfig) -> uuid.UUID | None:
    raw = (config.get("configurable") or {}).get("session_id")
    if isinstance(raw, str):
        try:
            return uuid.UUID(raw)
        except ValueError:
            return None
    return None


def _final_text(messages: Sequence[ChatMessage]) -> str | None:
    for message in reversed(messages):
        if message.role == "assistant" and message.content:
            return message.content
    return None
