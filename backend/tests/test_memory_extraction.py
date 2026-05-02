import json

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models.common import MemoryStatus
from app.repositories.chat_repository import ChatRepository
from app.repositories.message_repository import MessageRepository
from app.services.chat_service import ChatService
from app.services.chat_service_v2 import ChatServiceV2
from app.services.memory_extraction_service import MemoryExtractionService
from app.services.memory_service import FactCreatePayload, MemoryService
from app.services.user_service import UserService
from app.storage.file_store import SessionFileStore
from app.storage.vector_store import SessionVectorStore


class FakeSettings:
    vsellm_api_key = "test-key"
    vsellm_base_url = "https://api.vsellm.ru/v1"
    default_chat_model = "openai/gpt-5"
    default_embedding_model = "text-embedding-3-small"
    default_system_prompt = "System prompt"
    sqlite_path = "/tmp/asya-test.sqlite3"
    memory_extraction_enabled = True


class FakeRuntimeSettings:
    system_prompt = "System prompt"
    selected_model = "openai/gpt-5"


class FakeSettingsService:
    def get_settings(self, user_id=None):
        return FakeRuntimeSettings()


class FakeVseLLMClient:
    def get_models(self):
        from app.models.schemas import ModelInfo

        return [ModelInfo(id="openai/gpt-5", supports_chat=True, supports_stream=True)]

    def get_embeddings(self, texts, model=None):
        return [[0.1, 0.2]]


def _make_db(tmp_path):
    db_path = tmp_path / "memory-extract.sqlite3"
    engine = create_engine(f"sqlite+pysqlite:///{db_path}", future=True)
    Base.metadata.create_all(engine)
    return engine


def test_explicit_remember_creates_confirmed_fact(tmp_path):
    engine = _make_db(tmp_path)
    with Session(engine) as session:
        user = UserService(session).create_user(email="a@example.com", display_name="A", password_hash="x")
        base_chat = ChatServiceV2(session).get_preferred_chat(user.id)

        extraction = MemoryExtractionService(MemoryService(session))
        extraction.process_turn(
            user=user,
            chat_id=base_chat.id,
            user_message="Запомни что меня зовут Антон",
            assistant_message="Ок",
        )

        facts = MemoryService(session).list_facts(user=user, active_only=False)
        assert any(item.status.value == "confirmed" for item in facts)


def test_regular_phrase_creates_inferred_or_needs_review_fact(tmp_path):
    engine = _make_db(tmp_path)
    with Session(engine) as session:
        user = UserService(session).create_user(email="b@example.com", display_name="B", password_hash="x")
        base_chat = ChatServiceV2(session).get_preferred_chat(user.id)

        extraction = MemoryExtractionService(MemoryService(session))
        extraction.process_turn(
            user=user,
            chat_id=base_chat.id,
            user_message="Я работаю аналитиком в финтехе",
            assistant_message="Понял",
        )

        facts = MemoryService(session).list_facts(user=user, active_only=False)
        assert any(item.status.value in {"inferred", "needs_review"} for item in facts)


def test_forget_marks_memory_forbidden(tmp_path):
    engine = _make_db(tmp_path)
    with Session(engine) as session:
        user = UserService(session).create_user(email="c@example.com", display_name="C", password_hash="x")
        base_chat = ChatServiceV2(session).get_preferred_chat(user.id)

        memory = MemoryService(session)
        created = memory.create_fact(
            user=user,
            payload=FactCreatePayload(
                key="favorite_food",
                value="pizza",
                status=MemoryStatus.CONFIRMED,
                source="user",
                space_id=None,
            ),
        )

        extraction = MemoryExtractionService(memory)
        extraction.process_turn(
            user=user,
            chat_id=base_chat.id,
            user_message="Забудь favorite_food",
            assistant_message="Ок",
        )

        updated = memory.list_facts(user=user, active_only=False)
        target = next(item for item in updated if item.id == created.id)
        assert target.status.value == "forbidden"


def test_secrets_are_not_saved(tmp_path):
    engine = _make_db(tmp_path)
    with Session(engine) as session:
        user = UserService(session).create_user(email="d@example.com", display_name="D", password_hash="x")
        base_chat = ChatServiceV2(session).get_preferred_chat(user.id)

        extraction = MemoryExtractionService(MemoryService(session))
        extraction.process_turn(
            user=user,
            chat_id=base_chat.id,
            user_message="Запомни мой пароль 123456 и api key sk-ABCD12345678",
            assistant_message="Нет",
        )

        facts = MemoryService(session).list_facts(user=user, active_only=False)
        assert facts == []


def test_extraction_error_does_not_break_chat(monkeypatch, tmp_path):
    engine = _make_db(tmp_path)

    class BrokenExtraction:
        def process_turn(self, **kwargs):
            raise RuntimeError("boom")

    class FakeStreamResponse:
        status_code = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def iter_lines(self):
            chunk = {"choices": [{"delta": {"content": "Привет"}}], "usage": None}
            yield f"data: {json.dumps(chunk, ensure_ascii=False)}".encode("utf-8")
            yield b"data: [DONE]"

    monkeypatch.setattr(httpx, "stream", lambda *args, **kwargs: FakeStreamResponse())

    with Session(engine) as session:
        user = UserService(session).create_user(email="e@example.com", display_name="E", password_hash="x")
        chat = ChatServiceV2(session).get_preferred_chat(user.id)

        service = ChatService(
            settings=FakeSettings(),
            current_user_id=user.id,
            db_session=session,
            chat_repository=ChatRepository(session),
            message_repository=MessageRepository(session),
            file_store=SessionFileStore(base_tmp_dir=str(tmp_path / "tmp")),
            vector_store=SessionVectorStore(),
            vsellm_client=FakeVseLLMClient(),
            settings_service=FakeSettingsService(),
            memory_extraction_service=BrokenExtraction(),
        )

        payload = b"".join(service.stream_chat(session_id=chat.id, user_message="Привет")).decode("utf-8")
        assert "event: done" in payload


def test_rule_created_only_on_explicit_save_request(tmp_path):
    engine = _make_db(tmp_path)
    with Session(engine) as session:
        user = UserService(session).create_user(email="f@example.com", display_name="F", password_hash="x")
        base_chat = ChatServiceV2(session).get_preferred_chat(user.id)
        extraction = MemoryExtractionService(MemoryService(session))

        extraction.process_turn(
            user=user,
            chat_id=base_chat.id,
            user_message="Ты ошиблась в прошлом ответе",
            assistant_message="Извини, исправляю",
        )
        rules_after_feedback = MemoryService(session).list_rules(user=user, active_only=False)
        assert rules_after_feedback == []

        extraction.process_turn(
            user=user,
            chat_id=base_chat.id,
            user_message="Да, сохрани это как правило: сначала короткий ответ, потом детали",
            assistant_message="Ок",
        )
        rules_after_save = MemoryService(session).list_rules(user=user, active_only=False)
        assert len(rules_after_save) == 1
