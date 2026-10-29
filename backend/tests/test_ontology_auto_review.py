"""Автоматическое ревью provisional-тем: правила, LLM, аудит и API."""

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import delete, select

from app.core.config import Settings
from app.db.session import async_session_factory
from app.llm.base import (
    ChatMessage,
    LLMError,
    LLMResponse,
    StructuredResult,
    ToolSpec,
)
from app.models import (
    OntologyReviewAction,
    Resume,
    ResumeSkill,
    Topic,
    TopicAlias,
    TopicCandidate,
    User,
    UserSkillState,
    VacancySkill,
)
from app.services.normalization import TopicIndex, TopicRecord, normalize_name
from app.services.ontology_auto_review import (
    _decide,
    _needs_review,
    _parse_llm,
    _SimilarTopic,
    _TopicFacts,
    run_auto_review,
)
from app.services.topics import load_topic_index
from tests.conftest import ApiUser


def _settings(**overrides: Any) -> Settings:
    """Настройки авто-ревью с предсказуемыми порогами."""
    values: dict[str, Any] = {
        "ontology_auto_review_enabled": True,
        "ontology_auto_review_min_confidence": 0.75,
        "ontology_auto_merge_similarity": 0.9,
        "ontology_auto_approve_min_documents": 2,
        "ontology_auto_review_max_topics": 20,
    }
    values.update(overrides)
    return Settings(**values)


def _facts(
    name: str,
    *,
    description: str = "",
    category: str = "auto",
    names: Sequence[str] | None = None,
    document_count: int = 1,
    occurrences: int = 1,
) -> _TopicFacts:
    """Собирает факты темы без записи в БД."""
    topic = Topic(
        key=f"auto-test-{uuid4().hex[:8]}",
        name=name,
        description=description,
        category=category,
        status="provisional",
    )
    return _TopicFacts(
        topic=topic,
        names=tuple(names or (name,)),
        document_count=document_count,
        occurrences=occurrences,
        evidence=(),
    )


def _canonical(key: str, name: str, *, aliases: Sequence[str] = ()) -> TopicRecord:
    """Canonical-тема для индекса сопоставления."""
    return TopicRecord(id=uuid4(), key=key, name=name, aliases=tuple(aliases))


class ReviewStub:
    """LLM-заглушка, которая отвечает только на схему ontology_review."""

    def __init__(self, data: dict[str, Any] | None = None, *, error: bool = False) -> None:
        self.data = data or {}
        self.error = error
        self.calls: list[str] = []

    async def generate_with_tools(
        self, messages: Sequence[ChatMessage], tools: Sequence[ToolSpec]
    ) -> LLMResponse:
        """Не используется в авто-ревью."""
        raise LLMError("ReviewStub: generate_with_tools не поддерживается")

    async def generate_structured(
        self,
        messages: Sequence[ChatMessage],
        schema: dict[str, Any],
        *,
        schema_name: str = "result",
    ) -> StructuredResult:
        """Возвращает заготовленное решение."""
        self.calls.append(schema_name)
        if self.error:
            raise LLMError("ReviewStub: модель недоступна")
        return StructuredResult(data=self.data)

    async def close(self) -> None:
        """Ресурсов нет."""
        return


def test_parse_llm_requires_target_for_merge() -> None:
    """Merge без target_key безопасно превращается в keep."""
    review = _parse_llm(
        {"decision": "merge", "confidence": 0.95, "reason": "синоним"}
    )

    assert review.action == "keep"
    assert "target_key" in review.reason
    assert review.confidence == 0.95


def test_parse_llm_clamps_confidence_and_aliases() -> None:
    """Уверенность ограничивается диапазоном, алиасы обрезаются по лимиту."""
    review = _parse_llm(
        {
            "decision": "approve",
            "confidence": 1.7,
            "reason": "  реальный   навык ",
            "name": "  Новый навык ",
            "aliases": [" Синоним ", "", "Синоним"],
        }
    )

    assert review.action == "approve"
    assert review.confidence == 1.0
    assert review.reason == "реальный навык"
    assert review.name == "Новый навык"
    assert review.aliases == ("Синоним", "Синоним")


def test_needs_review_only_after_new_occurrences() -> None:
    """Повторная проверка kept-темы запускается только при новых упоминаниях."""
    topic = Topic(key="auto-test", name="Test", status="provisional")

    assert _needs_review(topic, 1) is True

    topic.auto_review_decision = "keep"
    topic.auto_reviewed_occurrences = 1
    topic.auto_reviewed_at = datetime.now(UTC)
    assert _needs_review(topic, 1) is False
    assert _needs_review(topic, 2) is True

    topic.auto_review_decision = "approve"
    assert _needs_review(topic, 10) is False


async def test_rule_merges_exact_alias() -> None:
    """Точное совпадение с алиасом canonical-темы даёт merge без LLM."""
    index = TopicIndex([_canonical("postgresql", "PostgreSQL", aliases=("Postgres",))])
    facts = _facts("Postgres", names=("Postgres",))

    decision = await _decide(
        facts,
        index=index,
        similar=[],
        provider=ReviewStub(),
        settings=_settings(),
    )

    assert decision.action == "merge"
    assert decision.target_key == "postgresql"
    assert decision.source == "rule"
    assert decision.confidence == 1.0


async def test_rule_merges_high_similarity() -> None:
    """Очень высокая семантическая близость сливает тему с canonical."""
    record = _canonical("react", "React")
    facts = _facts("React framework")

    decision = await _decide(
        facts,
        index=TopicIndex([record]),
        similar=[_SimilarTopic(record=record, score=0.95)],
        provider=None,
        settings=_settings(),
    )

    assert decision.action == "merge"
    assert decision.target_key == "react"
    assert decision.source == "rule"


async def test_rule_approves_repeated_topic() -> None:
    """Повторяющаяся тема без близкой canonical-темы подтверждается правилом."""
    facts = _facts("Kubernetes operator", document_count=3, occurrences=4)

    decision = await _decide(
        facts,
        index=TopicIndex([]),
        similar=[],
        provider=None,
        settings=_settings(),
    )

    assert decision.action == "approve"
    assert decision.source == "rule"
    assert decision.confidence >= 0.7


async def test_rule_keeps_overflow_topic() -> None:
    """Служебная review-тема переполнения не подтверждается автоматически."""
    facts = _facts("Новые навыки (на ревью)", category="auto_review", document_count=5)

    decision = await _decide(
        facts,
        index=TopicIndex([]),
        similar=[],
        provider=None,
        settings=_settings(),
    )

    assert decision.action == "keep"
    assert decision.source == "rule"


async def test_llm_low_confidence_keeps_topic() -> None:
    """Решение LLM ниже порога уверенности не применяется."""
    provider = ReviewStub(
        {"decision": "approve", "confidence": 0.4, "reason": "возможно, реальный навык"}
    )
    facts = _facts("Сомнительный навык")

    decision = await _decide(
        facts,
        index=TopicIndex([]),
        similar=[],
        provider=provider,
        settings=_settings(),
    )

    assert decision.action == "keep"
    assert decision.source == "llm"
    assert "ниже порога" in decision.reason
    assert provider.calls == ["ontology_review"]


async def test_llm_merge_target_must_be_among_candidates() -> None:
    """LLM не может слить тему в canonical-тему вне top-K кандидатов."""
    provider = ReviewStub(
        {
            "decision": "merge",
            "target_key": "unknown-topic",
            "confidence": 0.95,
            "reason": "похоже",
        }
    )
    record = _canonical("python", "Python")
    facts = _facts("Python tooling")

    decision = await _decide(
        facts,
        index=TopicIndex([record]),
        similar=[_SimilarTopic(record=record, score=0.5)],
        provider=provider,
        settings=_settings(),
    )

    assert decision.action == "keep"
    assert decision.source == "llm"
    assert "неизвестную тему" in decision.reason


async def test_llm_approve_passes_enrichment() -> None:
    """LLM-approve возвращает уточнённые название, описание и алиасы."""
    provider = ReviewStub(
        {
            "decision": "approve",
            "confidence": 0.9,
            "reason": "самостоятельный навык",
            "name": "Brand New Skill",
            "description": "Навык из тестов",
            "category": "testing",
            "aliases": ["BNS"],
        }
    )
    facts = _facts("Brand New Skill 123")

    decision = await _decide(
        facts,
        index=TopicIndex([]),
        similar=[],
        provider=provider,
        settings=_settings(),
    )

    assert decision.action == "approve"
    assert decision.name == "Brand New Skill"
    assert decision.description == "Навык из тестов"
    assert decision.category == "testing"
    assert decision.aliases == ("BNS",)


def _key(prefix: str) -> str:
    """Уникальный ключ тестовой темы."""
    return f"auto-review-test-{prefix}-{uuid4().hex[:8]}"


async def _make_topic(
    session,
    *,
    name: str,
    status: str = "provisional",
    key_prefix: str = "topic",
) -> Topic:
    """Создаёт тему нужного статуса."""
    topic = Topic(
        key=_key(key_prefix),
        name=name,
        description=f"Тестовая тема {name}",
        category="auto" if status == "provisional" else "test",
        aliases=[],
        status=status,
        origin="auto" if status == "provisional" else "manual",
        is_auto_generated=status == "provisional",
    )
    session.add(topic)
    await session.flush()
    return topic


async def _cleanup(keys: Sequence[str], email: str | None = None) -> None:
    """Удаляет данные теста, не оставляя мусора в онтологии."""
    async with async_session_factory() as session:
        if email is not None:
            user = await session.scalar(select(User).where(User.email == email))
            if user is not None:
                await session.delete(user)
        topics = (await session.scalars(select(Topic).where(Topic.key.in_(keys)))).all()
        topic_ids = [topic.id for topic in topics]
        if topic_ids:
            await session.execute(delete(ResumeSkill).where(ResumeSkill.topic_id.in_(topic_ids)))
            await session.execute(delete(VacancySkill).where(VacancySkill.topic_id.in_(topic_ids)))
            await session.execute(
                delete(UserSkillState).where(UserSkillState.topic_id.in_(topic_ids))
            )
            await session.execute(
                delete(OntologyReviewAction).where(
                    OntologyReviewAction.source_topic_id.in_(topic_ids)
                    | OntologyReviewAction.target_topic_id.in_(topic_ids)
                )
            )
            await session.execute(
                delete(TopicCandidate).where(TopicCandidate.topic_id.in_(topic_ids))
            )
            await session.execute(delete(Topic).where(Topic.id.in_(topic_ids)))
        await session.commit()


async def test_topic_index_prefers_canonical_over_provisional(seeded_db: None) -> None:
    """Одинаковое имя не должно вести в provisional-тему вместо canonical."""
    name = f"Shared Review Name {uuid4().hex[:8]}"
    canonical_key = _key("canonical")
    provisional_key = _key("provisional")
    try:
        async with async_session_factory() as session:
            canonical = await _make_topic(
                session, name=name, status="canonical", key_prefix="canonical"
            )
            canonical_key = canonical.key
            provisional = await _make_topic(
                session, name=name, status="provisional", key_prefix="provisional"
            )
            provisional_key = provisional.key
            await session.commit()

            index = await load_topic_index(session)
            found = index.find_exact(name)

        assert found is not None
        assert found.key == canonical_key
        assert found.key != provisional_key
    finally:
        await _cleanup([canonical_key, provisional_key])


async def test_auto_merge_moves_skills_and_writes_audit(seeded_db: None) -> None:
    """Правило merge переносит навыки, меняет match_method и пишет аудит."""
    source_key = _key("merge-source")
    target_key = _key("merge-target")
    alias = f"Review Alias {uuid4().hex[:8]}"
    email = f"auto-merge-{uuid4().hex}@example.com"
    try:
        async with async_session_factory() as session:
            target = await _make_topic(
                session, name="Review Canonical", status="canonical", key_prefix="merge-target"
            )
            target_key = target.key
            session.add(
                TopicAlias(
                    topic_id=target.id,
                    alias=alias,
                    normalized_alias=normalize_name(alias),
                    source="manual",
                    status="active",
                )
            )

            source = await _make_topic(
                session, name=alias, status="provisional", key_prefix="merge-source"
            )
            source_key = source.key

            user = User(email=email, password_hash="test")
            session.add(user)
            await session.flush()
            resume = Resume(user_id=user.id, title=None, raw_text="test")
            session.add(resume)
            await session.flush()
            session.add(
                TopicCandidate(
                    name=alias,
                    normalized_name=normalize_name(alias),
                    topic_id=source.id,
                    status="auto_created",
                    occurrences=1,
                    sources=[{"type": "resume", "id": str(resume.id), "evidence": "из теста"}],
                )
            )
            session.add(
                ResumeSkill(
                    resume_id=resume.id,
                    topic_id=source.id,
                    raw_name=alias,
                    proficiency=40,
                    confidence=0.5,
                    match_method="provisional",
                )
            )
            await session.commit()

            decisions = await run_auto_review(session, [source.id])

        assert len(decisions) == 1
        assert decisions[0].action == "merge"
        assert decisions[0].target_key == target_key

        async with async_session_factory() as session:
            source = await session.scalar(select(Topic).where(Topic.key == source_key))
            target = await session.scalar(select(Topic).where(Topic.key == target_key))
            skill = await session.scalar(select(ResumeSkill).where(ResumeSkill.raw_name == alias))
            action = await session.scalar(
                select(OntologyReviewAction).where(
                    OntologyReviewAction.source_topic_id == source.id,
                    OntologyReviewAction.action == "merge",
                )
            )

        assert source.status == "merged"
        assert source.canonical_topic_id == target.id
        assert source.auto_review_decision == "merge"
        assert skill.topic_id == target.id
        assert skill.match_method == "auto_merge"
        assert action is not None
        assert action.actor == "auto"
        assert action.details["source"] == "rule"
    finally:
        await _cleanup([source_key, target_key], email)


async def test_llm_approve_updates_topic_candidate_and_skill(seeded_db: None) -> None:
    """LLM-approve переводит тему в canonical и обогащает её данными модели."""
    name = f"Brand New Skill {uuid4().hex[:8]}"
    topic_key = _key("approve")
    email = f"auto-approve-{uuid4().hex}@example.com"
    provider = ReviewStub(
        {
            "decision": "approve",
            "confidence": 0.92,
            "reason": "самостоятельный навык",
            "name": name,
            "description": "Навык из теста авто-ревью",
            "category": "testing",
            "aliases": [f"BNS {uuid4().hex[:8]}"],
        }
    )
    try:
        async with async_session_factory() as session:
            topic = await _make_topic(session, name=name, key_prefix="approve")
            topic_key = topic.key

            user = User(email=email, password_hash="test")
            session.add(user)
            await session.flush()
            resume = Resume(user_id=user.id, title=None, raw_text="test")
            session.add(resume)
            await session.flush()
            session.add(
                TopicCandidate(
                    name=name,
                    normalized_name=normalize_name(name),
                    topic_id=topic.id,
                    status="auto_created",
                    occurrences=1,
                    sources=[{"type": "resume", "id": str(resume.id), "evidence": "из теста"}],
                )
            )
            session.add(
                ResumeSkill(
                    resume_id=resume.id,
                    topic_id=topic.id,
                    raw_name=name,
                    proficiency=45,
                    confidence=0.6,
                    match_method="provisional",
                )
            )
            await session.commit()

            decisions = await run_auto_review(session, [topic.id], provider=provider)

        assert decisions[0].action == "approve"
        assert decisions[0].source == "llm"

        async with async_session_factory() as session:
            topic = await session.scalar(select(Topic).where(Topic.key == topic_key))
            candidate = await session.scalar(
                select(TopicCandidate).where(TopicCandidate.topic_id == topic.id)
            )
            skill = await session.scalar(select(ResumeSkill).where(ResumeSkill.raw_name == name))
            action = await session.scalar(
                select(OntologyReviewAction).where(
                    OntologyReviewAction.source_topic_id == topic.id,
                    OntologyReviewAction.action == "approve",
                )
            )
            aliases = (
                await session.scalars(select(TopicAlias).where(TopicAlias.topic_id == topic.id))
            ).all()

        assert topic.status == "canonical"
        assert topic.category == "testing"
        assert topic.description == "Навык из теста авто-ревью"
        assert candidate.status == "approved"
        assert skill.match_method == "auto_approve"
        assert action is not None
        assert action.actor == "auto"
        assert action.details["confidence"] == 0.92
        assert any(alias.alias.startswith("BNS ") for alias in aliases)
    finally:
        await _cleanup([topic_key], email)


async def test_low_confidence_keeps_topic_provisional(seeded_db: None) -> None:
    """Неуверенное решение LLM оставляет тему на ручную проверку."""
    name = f"Uncertain Skill {uuid4().hex[:8]}"
    topic_key = _key("keep")
    provider = ReviewStub(
        {"decision": "approve", "confidence": 0.4, "reason": "недостаточно данных"}
    )
    try:
        async with async_session_factory() as session:
            topic = await _make_topic(session, name=name, key_prefix="keep")
            topic_key = topic.key
            session.add(
                TopicCandidate(
                    name=name,
                    normalized_name=normalize_name(name),
                    topic_id=topic.id,
                    status="auto_created",
                    occurrences=1,
                    sources=[],
                )
            )
            await session.commit()

            decisions = await run_auto_review(session, [topic.id], provider=provider)

        assert decisions[0].action == "keep"

        async with async_session_factory() as session:
            topic = await session.scalar(select(Topic).where(Topic.key == topic_key))
            candidate = await session.scalar(
                select(TopicCandidate).where(TopicCandidate.topic_id == topic.id)
            )
            action = await session.scalar(
                select(OntologyReviewAction).where(
                    OntologyReviewAction.source_topic_id == topic.id,
                    OntologyReviewAction.action == "keep",
                )
            )

        assert topic.status == "provisional"
        assert topic.auto_review_decision == "keep"
        assert topic.auto_review_confidence == 0.4
        assert candidate.status == "auto_created"
        assert action is not None
        assert action.actor == "auto"
    finally:
        await _cleanup([topic_key])


async def test_kept_topic_is_not_rechecked_without_new_occurrences(seeded_db: None) -> None:
    """Повторный прогон без новых упоминаний не вызывает LLM и не пишет аудит."""
    name = f"Stable Uncertain Skill {uuid4().hex[:8]}"
    topic_key = _key("stable")
    provider = ReviewStub(
        {"decision": "approve", "confidence": 0.4, "reason": "недостаточно данных"}
    )
    try:
        async with async_session_factory() as session:
            topic = await _make_topic(session, name=name, key_prefix="stable")
            topic_key = topic.key
            session.add(
                TopicCandidate(
                    name=name,
                    normalized_name=normalize_name(name),
                    topic_id=topic.id,
                    status="auto_created",
                    occurrences=1,
                    sources=[],
                )
            )
            await session.commit()

            first = await run_auto_review(session, [topic.id], provider=provider)
            calls_after_first = len(provider.calls)
            second = await run_auto_review(session, [topic.id], provider=provider)

        assert len(first) == 1
        assert second == []
        assert len(provider.calls) == calls_after_first
    finally:
        await _cleanup([topic_key])


async def test_failed_llm_does_not_break_document_upload(api_user: ApiUser) -> None:
    """Сбой LLM-ревью не мешает сохранить резюме: тема остаётся provisional."""
    name = f"Resilient Skill {uuid4().hex[:8]}"
    api_user.provider.responses["resume_skills"] = {
        "experience_years": 1.0,
        "self_level": "junior",
        "skills": [
            {
                "name": name,
                "proficiency": 40,
                "evidence": "учебный проект",
                "confidence": 0.7,
            }
        ],
    }
    # Ответа для ontology_review нет — провайдер бросит LLMError.
    api_user.provider.responses.pop("ontology_review", None)

    try:
        response = await api_user.client.post(
            "/resumes",
            json={"title": "Резюме", "raw_text": "Резюме с новым навыком"},
            headers=api_user.headers,
        )

        assert response.status_code == 201, response.text
        skill = response.json()["skills"][0]
        assert skill["match_method"] == "provisional"
        assert skill["topic"]["status"] == "provisional"
    finally:
        await _cleanup_topic_by_name(name)


async def test_upload_applies_llm_approve_and_returns_canonical_topic(api_user: ApiUser) -> None:
    """Резюме с новой темой сразу возвращает canonical-тему после LLM-approve."""
    name = f"Auto Approved Skill {uuid4().hex[:8]}"
    api_user.provider.responses["resume_skills"] = {
        "experience_years": 1.0,
        "self_level": "junior",
        "skills": [
            {
                "name": name,
                "proficiency": 40,
                "evidence": "учебный проект",
                "confidence": 0.7,
            }
        ],
    }
    api_user.provider.responses["ontology_review"] = {
        "decision": "approve",
        "confidence": 0.93,
        "reason": "самостоятельный навык",
        "name": name,
        "description": "Навык, подтверждённый авто-ревью",
        "category": "testing",
        "aliases": [],
    }

    try:
        response = await api_user.client.post(
            "/resumes",
            json={"title": "Резюме", "raw_text": "Резюме с новым навыком"},
            headers=api_user.headers,
        )

        assert response.status_code == 201, response.text
        skill = response.json()["skills"][0]
        assert skill["match_method"] == "auto_approve"
        assert skill["topic"]["status"] == "canonical"

        profile = await api_user.client.get("/profile", headers=api_user.headers)
        assert profile.status_code == 200
        topics = {topic["topic_key"]: topic for topic in profile.json()["topics"]}
        assert topics[skill["topic"]["key"]]["status"] == "canonical"
    finally:
        await _cleanup_topic_by_name(name)


async def _cleanup_topic_by_name(name: str) -> None:
    """Удаляет тему, созданную API-сценарием по имени навыка."""
    async with async_session_factory() as session:
        candidate = await session.scalar(
            select(TopicCandidate).where(TopicCandidate.normalized_name == normalize_name(name))
        )
        topic_id = candidate.topic_id if candidate is not None else None
        if candidate is not None:
            await session.delete(candidate)
        if topic_id is not None:
            await session.execute(delete(ResumeSkill).where(ResumeSkill.topic_id == topic_id))
            await session.execute(delete(VacancySkill).where(VacancySkill.topic_id == topic_id))
            await session.execute(
                delete(UserSkillState).where(UserSkillState.topic_id == topic_id)
            )
            await session.execute(
                delete(OntologyReviewAction).where(
                    (OntologyReviewAction.source_topic_id == topic_id)
                    | (OntologyReviewAction.target_topic_id == topic_id)
                )
            )
            await session.execute(delete(Topic).where(Topic.id == topic_id))
        await session.commit()
