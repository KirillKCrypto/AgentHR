"""Контракт результата прогона агента (общий для harness'ов)."""

from dataclasses import dataclass

from app.llm.base import ChatMessage


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
