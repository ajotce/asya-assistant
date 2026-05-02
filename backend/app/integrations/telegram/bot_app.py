from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from app.core.config import Settings
from app.db.session import create_session
from app.integrations.telegram.link_service import TelegramLinkError, TelegramLinkService
from app.repositories.chat_repository import ChatRepository
from app.services.chat_service_v2 import ChatServiceV2
from app.services.user_service import UserService
from app.services.user_voice_settings_service import UserVoiceSettingsService
from app.voice.service import VoiceService

logger = logging.getLogger(__name__)


class TelegramBotApp:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._bot: Bot | None = None
        self._dispatcher: Dispatcher | None = None
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        token = self._settings.telegram_bot_token.strip()
        if not token:
            logger.info("telegram_bot_disabled reason=no_token")
            return
        self._bot = Bot(token=token)
        self._dispatcher = Dispatcher()
        self._register_handlers(self._dispatcher)
        self._task = asyncio.create_task(self._dispatcher.start_polling(self._bot))
        logger.info("telegram_bot_started")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._bot is not None:
            await self._bot.session.close()
        logger.info("telegram_bot_stopped")

    def _register_handlers(self, dispatcher: Dispatcher) -> None:
        @dispatcher.message(Command("start"))
        async def handle_start(message: Message, command: CommandObject) -> None:
            token = (command.args or "").strip()
            if not token:
                await message.answer("Привет! Чтобы привязать аккаунт Asya, откройте ссылку привязки в веб-приложении.")
                return

            from_user = message.from_user
            if from_user is None:
                await message.answer("Не удалось определить Telegram-пользователя.")
                return

            db = create_session()
            try:
                service = TelegramLinkService(db, self._settings)
                service.consume_start_token(
                    token=token,
                    telegram_user_id=str(from_user.id),
                    telegram_chat_id=str(message.chat.id),
                    telegram_username=from_user.username,
                )
                db.commit()
                await message.answer("Готово! Аккаунт Asya успешно привязан к Telegram.")
            except TelegramLinkError:
                db.rollback()
                await message.answer("Токен недействителен или истек. Сгенерируйте новый токен в настройках Asya.")
            except Exception:
                db.rollback()
                logger.exception("telegram_start_handler_failed")
                await message.answer("Ошибка привязки. Попробуйте позже.")
            finally:
                db.close()

        @dispatcher.message(F.voice)
        async def handle_voice_message(message: Message) -> None:
            from_user = message.from_user
            if from_user is None or message.voice is None or self._bot is None:
                return

            db = create_session()
            try:
                from app.repositories.telegram_account_link_repository import TelegramAccountLinkRepository

                link = TelegramAccountLinkRepository(db).get_active_by_telegram_user_id(str(from_user.id))
                if link is None:
                    await message.answer("Сначала привяжите аккаунт Asya через /start <token>.")
                    return

                file = await self._bot.get_file(message.voice.file_id)
                file_url = f"https://api.telegram.org/file/bot{self._settings.telegram_bot_token}/{file.file_path}"
                import httpx

                raw_audio = httpx.get(file_url, timeout=httpx.Timeout(timeout=20.0, connect=5.0)).content

                user = UserService(db).get_user(link.user_id)
                if user is None:
                    await message.answer("Пользователь не найден.")
                    return

                voice_settings = UserVoiceSettingsService(db, self._settings)
                voice_service = VoiceService(self._settings, voice_settings)
                stt = voice_service.transcribe(user=user, audio_bytes=raw_audio, mime_type="audio/ogg")

                chat_service = ChatServiceV2(db, chat_repository=ChatRepository(db))
                chat = chat_service.get_preferred_chat(user.id)
                await message.answer(f"Транскрипт: {stt.text}")

                from app.api.routes_chat import get_chat_service

                stream_service = get_chat_service(current_user=user, db_session=db)
                full_answer = ""
                for chunk in stream_service.stream_chat(chat.id, stt.text):
                    decoded = chunk.decode("utf-8", errors="ignore")
                    if "event: token" in decoded and '"text":' in decoded:
                        try:
                            import json

                            data_line = next((line for line in decoded.split("\n") if line.startswith("data:")), "")
                            data = json.loads(data_line.replace("data:", "", 1).strip())
                            token_text = data.get("text")
                            if isinstance(token_text, str):
                                full_answer += token_text
                        except Exception:
                            continue

                answer_text = full_answer.strip() or "Не удалось сформировать ответ"
                await message.answer(answer_text[:4000])

                user_voice = voice_settings.get_or_create(user=user)
                if user_voice.tts_enabled:
                    tts = voice_service.synthesize(user=user, text=answer_text)
                    await message.answer_voice(voice=tts.audio_bytes)
                db.commit()
            except Exception:
                db.rollback()
                logger.exception("telegram_voice_handler_failed")
                await message.answer("Ошибка обработки voice-сообщения.")
            finally:
                db.close()

        @dispatcher.message(Command("menu"))
        async def handle_menu(message: Message) -> None:
            from_user = message.from_user
            if from_user is None:
                return
            db = create_session()
            try:
                from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

                from app.repositories.telegram_account_link_repository import TelegramAccountLinkRepository
                from app.repositories.space_repository import SpaceRepository
                from app.services.user_service import UserService

                link = TelegramAccountLinkRepository(db).get_active_by_telegram_user_id(str(from_user.id))
                if link is None:
                    await message.answer("Сначала привяжите аккаунт Asya через /start <token>.")
                    return
                user = UserService(db).get_user(link.user_id)
                if user is None:
                    await message.answer("Пользователь не найден.")
                    return

                spaces = SpaceRepository(db).list_for_user(user.id)
                visible_spaces = [s for s in spaces if (user.role == "admin" or not s.is_admin_only) and not s.is_archived]
                rows = [
                    [InlineKeyboardButton(text="Задачи", callback_data="menu:tasks")],
                    [InlineKeyboardButton(text="Календарь", callback_data="menu:calendar")],
                    [InlineKeyboardButton(text="Дневник", callback_data="menu:diary")],
                ]
                for space in visible_spaces[:8]:
                    rows.append([InlineKeyboardButton(text=f"Пространство: {space.name}", callback_data=f"space:{space.id}")])
                keyboard = InlineKeyboardMarkup(inline_keyboard=rows)
                await message.answer("Меню Asya", reply_markup=keyboard)
            finally:
                db.close()
