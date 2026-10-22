"""Нормализация навыков к онтологии.

Порядок сопоставления (от точного к приблизительному):

1. `exact` — нормализованное имя совпало с ключом или названием темы;
2. `alias` — совпало с одним из алиасов темы;
3. `fuzzy` — нечёткое совпадение с названием или алиасом темы;
4. `embedding` — косинусная близость к описанию темы (если эмбеддер доступен).

Если тема не найдена, навык не отбрасывается: он сохраняется как есть
(`raw_name`) и попадает в кандидаты на новые темы.
"""

import re
import unicodedata
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from app.embeddings.base import EmbeddingProvider, cosine_similarity

# Порог нечёткого совпадения по названию/алиасу
DEFAULT_FUZZY_THRESHOLD = 0.85
# Порог косинусной близости для сопоставления по смыслу
DEFAULT_EMBEDDING_THRESHOLD = 0.35

_NORMALIZE_RE = re.compile(r"[^\w\s]", re.UNICODE)
_SPACES_RE = re.compile(r"\s+", re.UNICODE)

# Кириллические омоглифы латиницы: «ООП» и «OOP» должны совпадать,
# «С++» с кириллической «С» — с «C++».
_HOMOGLYPHS_UPPER = str.maketrans(
    {
        "А": "A",
        "В": "B",
        "Е": "E",
        "Ѕ": "S",
        "І": "I",
        "Ј": "J",
        "К": "K",
        "М": "M",
        "Н": "H",
        "О": "O",
        "П": "P",
        "Р": "P",
        "С": "C",
        "Т": "T",
        "У": "Y",
        "Х": "X",
    }
)
_HOMOGLYPHS_LOWER = str.maketrans(
    {
        "а": "a",
        "в": "b",
        "е": "e",
        "ё": "e",
        "і": "i",
        "ј": "j",
        "к": "k",
        "м": "m",
        "н": "h",
        "о": "o",
        "п": "p",
        "р": "p",
        "с": "c",
        "ѕ": "s",
        "т": "t",
        "у": "y",
        "х": "x",
    }
)


def normalize_name(raw: str) -> str:
    """Нормализует название навыка: регистр, омоглифы, «ё», пунктуация, пробелы."""
    text = unicodedata.normalize("NFKC", raw or "").strip()
    text = text.translate(_HOMOGLYPHS_UPPER)
    text = text.lower()
    text = text.translate(_HOMOGLYPHS_LOWER)
    text = _NORMALIZE_RE.sub(" ", text)
    text = _SPACES_RE.sub(" ", text)
    return text.strip()


@dataclass(frozen=True)
class TopicRecord:
    """Тема онтологии в виде, удобном для сопоставления."""

    id: uuid.UUID
    key: str
    name: str
    description: str = ""
    aliases: tuple[str, ...] = field(default_factory=tuple)

    def embedding_text(self) -> str:
        """Текст, который кодируется эмбеддером (название + описание)."""
        parts = [self.name, self.description]
        parts.extend(self.aliases)
        return ". ".join(part for part in parts if part)


@dataclass(frozen=True)
class TopicMatch:
    """Результат сопоставления навыка с темой."""

    topic_id: uuid.UUID | None
    method: str
    score: float
    topic_key: str | None = None

    @property
    def matched(self) -> bool:
        """Найдена ли тема."""
        return self.topic_id is not None


class TopicIndex:
    """Индекс тем онтологии: точные имена, алиасы и fuzzy-поиск."""

    def __init__(self, topics: Sequence[TopicRecord]) -> None:
        self._topics = tuple(topics)
        self._exact: dict[str, TopicRecord] = {}
        self._alias: dict[str, TopicRecord] = {}
        for topic in self._topics:
            self._exact.setdefault(normalize_name(topic.key), topic)
            self._exact.setdefault(normalize_name(topic.name), topic)
            for alias in topic.aliases:
                self._alias.setdefault(normalize_name(alias), topic)

    @property
    def topics(self) -> tuple[TopicRecord, ...]:
        """Все темы индекса."""
        return self._topics

    def __len__(self) -> int:
        return len(self._topics)

    def find_exact(self, name: str) -> TopicRecord | None:
        """Тема по нормализованному ключу или названию."""
        return self._exact.get(normalize_name(name))

    def find_alias(self, name: str) -> TopicRecord | None:
        """Тема по нормализованному алиасу."""
        return self._alias.get(normalize_name(name))

    def find_fuzzy(
        self, name: str, threshold: float = DEFAULT_FUZZY_THRESHOLD
    ) -> tuple[TopicRecord | None, float]:
        """Ближайшая тема по нечёткому совпадению названия или алиаса."""
        normalized = normalize_name(name)
        if not normalized:
            return None, 0.0
        best: TopicRecord | None = None
        best_score = 0.0
        for topic in self._topics:
            candidates = (topic.key, topic.name, *topic.aliases)
            for candidate in candidates:
                score = SequenceMatcher(None, normalized, normalize_name(candidate)).ratio()
                if score > best_score:
                    best, best_score = topic, score
        if best_score < threshold:
            return None, best_score
        return best, best_score


class SkillMatcher:
    """Сопоставляет навыки темам онтологии.

    Эмбеддер опционален: без него работают exact/alias/fuzzy-этапы.
    """

    def __init__(
        self,
        index: TopicIndex,
        embedder: EmbeddingProvider | None = None,
        *,
        fuzzy_threshold: float = DEFAULT_FUZZY_THRESHOLD,
        embedding_threshold: float = DEFAULT_EMBEDDING_THRESHOLD,
    ) -> None:
        self._index = index
        self._embedder = embedder
        self._fuzzy_threshold = fuzzy_threshold
        self._embedding_threshold = embedding_threshold
        self._topic_vectors: list[list[float]] | None = None

    @property
    def index(self) -> TopicIndex:
        """Индекс тем, по которому идёт сопоставление."""
        return self._index

    async def match(self, raw_name: str) -> TopicMatch:
        """Сопоставляет один навык с темой онтологии."""
        results = await self.match_many([raw_name])
        return results[0]

    async def match_many(self, raw_names: Sequence[str]) -> list[TopicMatch]:
        """Сопоставляет несколько навыков; эмбеддинги считаются одним батчем."""
        names = list(raw_names)
        matches: list[TopicMatch | None] = [None] * len(names)
        pending: list[int] = []

        for index, raw_name in enumerate(names):
            exact = self._index.find_exact(raw_name)
            if exact is not None:
                matches[index] = TopicMatch(exact.id, "exact", 1.0, exact.key)
                continue
            alias = self._index.find_alias(raw_name)
            if alias is not None:
                matches[index] = TopicMatch(alias.id, "alias", 1.0, alias.key)
                continue
            fuzzy, score = self._index.find_fuzzy(raw_name, self._fuzzy_threshold)
            if fuzzy is not None:
                matches[index] = TopicMatch(fuzzy.id, "fuzzy", score, fuzzy.key)
                continue
            pending.append(index)

        if pending and self._embedder is not None and self._embedder.available:
            await self._match_by_embedding(names, pending, matches)

        return [
            match if match is not None else TopicMatch(None, "none", 0.0, None) for match in matches
        ]

    async def _match_by_embedding(
        self,
        names: Sequence[str],
        pending: Sequence[int],
        matches: list[TopicMatch | None],
    ) -> None:
        """Сопоставляет оставшиеся навыки по косинусной близости к темам."""
        if not self._index.topics:
            return
        vectors = await self._embedder.embed([names[index] for index in pending])
        topic_vectors = await self._topic_vectors_cached()
        if not topic_vectors or len(vectors) != len(pending):
            return
        for position, index in enumerate(pending):
            vector = vectors[position]
            best_key = ""
            best_topic = None
            best_score = 0.0
            for topic, topic_vector in zip(self._index.topics, topic_vectors):
                score = cosine_similarity(vector, topic_vector)
                if score > best_score:
                    best_topic, best_score, best_key = topic, score, topic.key
            if best_topic is not None and best_score >= self._embedding_threshold:
                matches[index] = TopicMatch(best_topic.id, "embedding", best_score, best_key)

    async def _topic_vectors_cached(self) -> list[list[float]]:
        """Векторы тем считаются один раз и переиспользуются."""
        if self._topic_vectors is None:
            texts = [topic.embedding_text() for topic in self._index.topics]
            self._topic_vectors = await self._embedder.embed(texts)
        return self._topic_vectors
