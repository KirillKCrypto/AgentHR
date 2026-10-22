"""Локальный ONNX-эмбеддер (fastembed) — бесплатно, без внешних сервисов.

Модель скачивается при первом использовании и кэшируется в каталоге
`EMBEDDING_CACHE_DIR`. Если пакет `fastembed` не установлен или модель
недоступна, провайдер сообщает `available = False`, и нормализация
продолжает работать по алиасам и нечёткому совпадению.
"""

import asyncio

from app.embeddings.base import EmbeddingError


class LocalEmbeddingProvider:
    """Эмбеддер на локальной ONNX-модели (multilingual-модели HuggingFace)."""

    def __init__(self, model_name: str, cache_dir: str | None = None) -> None:
        self._model_name = model_name
        self._cache_dir = cache_dir
        self._model: object | None = None
        self._error: str | None = None

    @property
    def model_name(self) -> str:
        """Имя используемой модели."""
        return self._model_name

    @property
    def error(self) -> str | None:
        """Причина недоступности провайдера (если он недоступен)."""
        return self._error

    @property
    def available(self) -> bool:
        return self._load() is not None

    def _load(self) -> object | None:
        """Лениво загружает модель; при ошибке запоминает причину."""
        if self._model is not None or self._error is not None:
            return self._model
        try:
            from fastembed import TextEmbedding
        except ImportError as exc:
            self._error = "fastembed не установлен — поставьте пакет: uv sync --extra embeddings"
            self._error = f"{self._error} ({exc})"
            return None
        try:
            kwargs: dict[str, str] = {}
            if self._cache_dir:
                kwargs["cache_dir"] = self._cache_dir
            self._model = TextEmbedding(model_name=self._model_name, **kwargs)
        except Exception as exc:  # noqa: BLE001 — причина недоступности фиксируется в error
            self._error = f"не удалось загрузить модель {self._model_name!r}: {exc}"
            return None
        return self._model

    async def embed(self, texts: list[str] | tuple[str, ...]) -> list[list[float]]:
        """Считает векторы; считает в отдельном потоке (CPU-bound работа)."""
        model = self._load()
        if model is None:
            raise EmbeddingError(self._error or "локальный эмбеддер недоступен")
        items = list(texts)
        vectors = await asyncio.to_thread(lambda: list(model.embed(items)))
        return [[float(value) for value in vector] for vector in vectors]
