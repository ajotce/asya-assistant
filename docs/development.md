# Development

## Цель текущего этапа
Поддерживать и проверять текущее ядро Asya Local:
- backend API + локальный Docker запуск;
- frontend PWA (чат/настройки/состояние);
- сессионный контекст, загрузку файлов и retrieval через embeddings;
- актуальность документации и проверок.

## Базовые команды запуска
```bash
cp .env.example .env
docker run --rm -v "$PWD/frontend:/work" -w /work node:20-alpine sh -lc "npm ci && npm run build"
docker compose up --build
```

## Инфраструктура БД Asya 0.2 (без подключения endpoint-ов)
- Добавлен отдельный SQLAlchemy/Alembic контур в `backend/app/db` и `backend/alembic`.
- Путь новой БД задаётся через `ASYA_DB_PATH`.
- Кодовый default: `./data/asya-0.2.sqlite3` (безопасно для локального запуска тестов/CLI).
- В `.env.example` задано `ASYA_DB_PATH=/app/data/asya-0.2.sqlite3`, чтобы Docker backend писал в volume `/app/data`.
- Текущие endpoint-ы (`/api/session*`, `/api/chat/stream`, `/api/usage*`) пока не переключены на новый DB-слой и продолжают работать как раньше.

Проверка, что Alembic-конфиг поднимается:
```bash
cd backend && python3 -m alembic -c alembic.ini current
```

Применение первой миграции на чистой БД:
```bash
cd backend && ASYA_DB_PATH=./data/asya-0.2.sqlite3 python3 -m alembic -c alembic.ini upgrade head
```

Важно:
- на этом этапе таблицы созданы, но действующие `/api/session*`, `/api/chat/stream`, `/api/usage*` всё ещё работают через текущие runtime/store-слои;
- переключение API на SQLAlchemy-модели делается отдельными шагами.

## Инфраструктура шифрования секретов (этап 0.2)
- Добавлена env-переменная `MASTER_ENCRYPTION_KEY` (в `.env.example` только имя, без значения).
- Добавлен `SecretCryptoService` (Fernet) для backend-шифрования секретов.
- Добавлен `EncryptedSecretService`, который сохраняет секреты в `encrypted_secrets` только в зашифрованном виде.
- Если `MASTER_ENCRYPTION_KEY` не задан или невалиден, сервис шифрования выдаёт явную безопасную ошибку конфигурации.
- Текущий этап не подключает внешние интеграции и не добавляет публичные endpoint-ы управления секретами.

## Repository/Service шаг для users/chats (без подключения endpoint-ов)
- Добавлен backend слой `repositories + services` для:
  - пользователей (`UserService`, `UserRepository`);
  - чатов (`ChatServiceV2`, `ChatRepository`).
- При создании пользователя автоматически создаётся `Base-chat`.
- Сервис гарантирует один активный (`is_archived=false`, `is_deleted=false`) `Base-chat` на пользователя.
- Базовые операции чатов реализованы в сервисе:
  - список;
  - создание;
  - переименование;
  - архивирование;
  - безопасное удаление (soft-delete);
  - чтение по `chat_id` только в рамках владельца (`user_id`).

## Переходный слой session/chat -> БД (совместимость API)
- Текущий legacy контракт `/api/session*` сохранён, но теперь:
  - `session_id` фактически является `chat_id` в БД;
  - сообщения `user/assistant` пишутся и читаются из таблицы `messages`.
- `/api/chat/stream` работает только в рамках `current user`:
  - чат должен принадлежать текущему пользователю;
  - история восстанавливается из БД после перезапуска backend.
- SSE-streaming и контракт событий не менялись.
- `reasoning/thinking` не сохраняется как обычное сообщение.
- Что ещё временно in-memory:
  - `SessionVectorStore` (retrieval-векторы/chunks).

## Перенос FileMeta и UsageRecord в БД
- Upload файлов теперь записывает metadata в таблицу `file_meta` (user-scoped).
- Chat/embeddings usage теперь записывается в `usage_records` (user-scoped, chat-scoped).
- `routes_usage` использует DB-агрегацию вместо runtime `UsageStore`.
- При `DELETE /api/session/{session_id}`:
  - удаляются runtime-файлы и runtime-векторы по сессии;
  - удаляются DB-записи `FileMeta` и `UsageRecord` текущего пользователя для этого чата.

Временное ограничение 0.2:
- retrieval-vector chunks всё ещё runtime-only (в памяти процесса), поэтому после рестарта backend retrieval-индекс требует повторной загрузки файлов.

## Локальный Docker запуск backend
```bash
docker compose up -d --build
docker compose ps
curl http://localhost:${ASYA_PORT}/api/health
curl -I http://localhost:${ASYA_PORT}/
curl -I http://localhost:${ASYA_PORT}/manifest.webmanifest
```

Если нужно посмотреть логи:
```bash
docker compose logs -f backend
```

Остановка:
```bash
docker compose down
```

## Локальные команды проверки
```bash
make test
make build-frontend
docker run --rm -v "$PWD/frontend:/work" -w /work node:20-alpine sh -lc "npm test"
```

`make build-frontend` работает в двух режимах:
- если локально доступен `npm`, используется локальная сборка;
- если `npm` не установлен, автоматически используется `node:20-alpine` контейнер.

Frontend unit-тесты запускаются через `vitest` (`frontend/src/pages/StatusPage.test.tsx` проверяет ключевые карточки страницы состояния).

## Frontend Chat + Files
- В `ChatPage` поддержан выбор до 10 файлов перед отправкой сообщения.
- Файлы проходят клиентскую проверку (тип/размер/лимит) до отправки.
- Если файлы выбраны, frontend сначала загружает их в `POST /api/session/{session_id}/files`, затем отправляет чат-запрос в `POST /api/chat/stream` с `file_ids`.
- При успешной отправке локальный список выбранных файлов очищается.
- При переключении вкладок `Чат`/`Настройки`/`Состояние` страницы не размонтируются повторно: уже открытые вкладки скрываются, поэтому runtime-состояние чата (текущая backend-сессия и видимая история) сохраняется до перезагрузки страницы.
- История чатов и долгосрочное хранение на frontend не добавляются.

## Frontend Auth UI (минимальный слой 0.2)
- Добавлен `AuthPage` (вход / регистрация / заявка на доступ) без отдельного UI framework.
- `App` при старте вызывает `/api/auth/me`:
  - если пользователь не авторизован, приватные вкладки `Чат` и `Настройки` не рендерятся;
  - показывается экран авторизации;
  - session token не хранится в `localStorage` (используется только backend `HttpOnly` cookie).
- В шапке приложения показывается `current user` и кнопка logout (`POST /api/auth/logout`).
- После входа frontend использует `preferred_chat_id` из auth-response и открывает Base-chat или последний доступный чат без создания лишней сессии.

## Minimal Admin Flow (заявки на доступ)
- Backend admin endpoint-ы `/api/admin/access-requests*` защищены `role=admin` через `get_current_admin_user`.
- Во frontend добавлен минимальный admin-раздел в `Настройки`:
  - виден только пользователям с `role=admin`;
  - показывает pending заявки;
  - даёт approve/reject действия.
- UI честно показывает dev-mode ограничение: реальная отправка email/magic-link не реализована в этом шаге.

## Как назначить первого admin локально (безопасный dev-командный вариант)
1. Сначала создайте обычного пользователя через UI/API (`/api/auth/register`) и убедитесь, что он есть в БД.
2. Выполните локально команду (из корня репозитория), подставив email:

```bash
cd backend && python3 -c "from sqlalchemy.orm import Session; from app.core.config import get_settings; from app.db.session import get_engine; from app.db.models.user import User; from app.db.models.common import UserRole; s=get_settings(); e=get_engine(s.asya_db_url); session=Session(bind=e); u=session.query(User).filter(User.email=='admin@example.com').one(); u.role=UserRole.ADMIN; session.commit(); session.close()"
```

3. Перелогиньтесь этим пользователем. В `Настройки` появится admin-раздел заявок.

Важно:
- это только локальная dev-процедура;
- не храните реальные секреты в Git;
- не используйте миграции для временного повышения роли конкретного пользователя в dev.

## Frontend multiple chats (этап 0.2)
- В `ChatPage` добавлен минимальный список чатов:
  - выбор активного чата;
  - создание нового;
  - переименование/архивирование/удаление обычного чата.
- `Base-chat` показывается в списке по умолчанию и выбирается стартовым чатом, если `preferred_chat_id` недоступен.
- История выбранного чата загружается из БД через `/api/chats/{chat_id}/messages`.
- Streaming-ответы продолжают идти через текущий `/api/chat/stream` и не меняют формат SSE.

## Streaming размышления
- Если выбранная модель присылает reasoning (`reasoning_content`/`reasoning`/`thinking`), backend пробрасывает его в отдельный SSE `event: thinking` без дублирования в `event: token`.
- Reasoning не сохраняется в истории сессии и не отправляется обратно провайдеру в последующих запросах.
- Во frontend в `ChatPage` появляется блок «Размышления модели» (`<details>`) только для тех ответов, где reasoning действительно пришёл; блок раскрыт во время генерации и сворачивается после `done`.
- Для обычных моделей блок не показывается.

Минимальный smoke:
```bash
docker compose up -d --build backend
# в Настройках выбрать reasoning-модель и отправить сообщение в Чате
# увидеть блок «Размышления модели» в ответе (если provider реально шлёт reasoning)
# выбрать обычную модель -> блок не появляется
docker compose down
```

Подтверждённые на текущий момент модели VseLLM, которые реально стримят `reasoning_content`:
- `qwen/qwen3-vl-235b-a22b-thinking`
- `qwen/qwen3-vl-30b-a3b-thinking`
- `qwen/qwen3-vl-8b-thinking`

Модели с «thinking» / «r1» в имени, которые не пробрасывают reasoning через текущую VseLLM-проксю (отдают только `content`): `qwen/qwen3-max-thinking`, `deepseek-r1-distill-llama-70b`, `claude-*` (даже с `thinking`-параметром), `gpt-5` с `reasoning_effort`.

В Настройках сделана пометка `🧠` по эвристике на ID и кнопка «Проверить reasoning у моделей», которая через `POST /api/models/probe-reasoning` живьём проверяет провайдера и подтверждает значком `✅` те модели, у которых reasoning реально стримится. Кэш — 24 часа, кнопка «Проверить заново» сбрасывает запись и переспрашивает провайдера.

## Проверка совместимости моделей
- На `Настройки` обновите список моделей (`GET /api/models`).
- Если у модели в metadata явно `supports_chat=false`, она показывается как неподходящая для chat/completions и недоступна для выбора.
- Если metadata неполная (например, есть только `id`), модель остается доступной для выбора и проверяется фактическим запросом чата.
- Для проблемных моделей backend возвращает понятную причину ошибки с ID модели и рекомендацией выбрать другую chat-модель или проверить provider settings.
- Если провайдер явно сообщает, что `stream=true` не поддерживается конкретной моделью, backend автоматически пробует non-stream fallback и отдает результат в текущий SSE-контракт.

## Страница «Состояние Asya»
На `StatusPage` отображаются:
- backend online/offline;
- доступность VseLLM API и base URL без API-ключа;
- выбранная модель;
- статус VseLLM API-ключа;
- uptime backend;
- статус файлового контура;
- статус embeddings (статус + модель + последняя ошибка, если есть);
- активные runtime-сессии;
- usage по chat/embeddings/cost из `/api/usage` (если провайдер прислал usage);
- статус временного хранилища (session/files + writable) и `tmp` путь.

UX страницы:
- статусы вынесены в интерактивные карточки с severity (`ok`, `warning`, `error`, `unknown`);
- в карточке показывается короткий понятный итог;
- по клику/тапу раскрываются технические детали;
- есть `Последнее обновление`, кнопка `Обновить` и toggle `Автообновление (15 сек)`.

Минимальная ручная проверка:
```bash
docker compose up -d --build backend
curl http://localhost:${ASYA_PORT}/api/health
# открыть в браузере: http://localhost:${ASYA_PORT}/status
docker compose down
```

Проверить в UI:
- карточки показывают корректные severity и короткий итог;
- раскрытие деталей по нажатию;
- при падении `/api/usage` health-карточки продолжают отображаться;
- автообновление отключается при уходе со страницы.

Прямые URL `/`, `/settings` и `/status` должны открывать соответствующие вкладки frontend через backend SPA fallback.

## Ручной smoke для chat/files
```bash
docker compose up -d backend
curl http://localhost:${ASYA_PORT}/api/health
```

Далее в UI проверить три сценария:
- сообщение без файла;
- сообщение с документом (PDF/DOCX/XLSX);
- сообщение с изображением (и понятная ошибка, если модель без vision).

## Минимальная PWA-проверка
```bash
# после сборки frontend
ls -la frontend/dist
ls -la frontend/dist/icons
cat frontend/dist/manifest.webmanifest
```

Критерии:
- в `dist` присутствуют `manifest.webmanifest` и иконки;
- приложение открывается через backend URL того же origin, что и `/api/*`;
- интерфейс корректно адаптируется для iPhone Safari и Mac;
- offline-режим и долгосрочное хранение чатов в браузере не добавляются.

## Правила этапа
- Не менять архитектуру без отдельного запроса.
- Не коммитить `.env` и реальные ключи.
- Для локального запуска frontend должен открываться через backend URL (same-origin с `/api`).
