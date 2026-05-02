# Testing

Документ фиксирует фактические команды проверки текущей версии Asya Local.

## Предусловия
- Для frontend-команд используется Docker (`node:20-alpine`), если локального `npm` нет.
- Для backend тестов нужен `python3`.

## 1) Frontend test script
Команда:
```bash
docker run --rm -v "$PWD/frontend:/work" -w /work node:20-alpine sh -lc "npm ci && npm test"
```

Ожидаемый результат:
- `vitest run` завершается без ошибок
- `Test Files ... passed`
- покрыты базовые сценарии:
  - `App` (прямое открытие `/status`, сохранение runtime-состояния чата при `Чат -> Настройки -> Чат`, отсутствие повторного создания сессии при возврате на вкладку чата)
  - `ChatPage` (рендер, отправка, streaming, отображение блока «Размышления модели» при наличии reasoning, отсутствие блока для обычных моделей, ошибки)
  - `SettingsPage` (модель, системный промт, предупреждение и disabled option для моделей с явным `supports_chat=false`, бейджи `🧠`/`✅` и probe-секция reasoning)
  - `StatusPage` (интерактивные статус-карточки, раскрытие деталей, понятная ошибка `/api/health`, graceful-деградация при ошибке `/api/usage`, наличие toggle автообновления)

## 2) Lint
Команда:
```bash
make lint
```

Ожидаемый результат:
- запускается `eslint "src/**/*.{ts,tsx}"`
- команда завершается с кодом `0`

## 3) Backend тесты
Команда:
```bash
make test
```

Ожидаемый результат:
- `pytest` завершается без падений
- текущий baseline: `55 passed` (возможны предупреждения, не блокирующие запуск)
- для совместимости моделей покрыты сценарии:
  - нормализация `supports_chat`/`supports_stream` из provider metadata (`supports_*`, `capabilities`, `endpoints`);
  - понятная маппинга provider body ошибок в chat;
  - fallback non-stream при явной provider-ошибке streaming;
- для streaming размышлений покрыты сценарии:
  - `event: thinking` эмитится при `delta.reasoning_content` от провайдера, reasoning не попадает в историю сессии;
  - non-stream fallback с `message.reasoning_content` отдаёт `event: thinking` до `event: token`;
  - для reasoning-моделей с известными ID (`deepseek-r1-*`, `o1`, `o3`) backend заранее уходит в non-stream и chunk'ает reasoning + ответ в SSE;
- для probe reasoning-моделей покрыты сценарии:
  - эвристика `is_likely_reasoning_model` по ID;
  - `probe_reasoning_streaming` распознаёт `delta.reasoning_content`;
  - `POST /api/models/probe-reasoning` фильтрует кандидатов эвристикой, использует кэш и поддерживает `force=true`;
  - `POST /api/models/probe-reasoning` принимает явный `model_ids[]` и не зовёт `get_models()`.

## 4) Frontend сборка
Команда:
```bash
make build-frontend
```

Ожидаемый результат:
- выполняется `tsc --noEmit && vite build`
- в `frontend/dist` появляются актуальные артефакты сборки
- команда завершается с кодом `0`

## 5) Smoke локального запуска
```bash
cp .env.example .env
make build-frontend
docker compose up -d --build
PORT=$(grep '^ASYA_PORT=' .env | cut -d= -f2)
curl "http://localhost:${PORT}/api/health"
curl "http://localhost:${PORT}/" | head -n 2
docker compose down
```

Ожидаемый результат:
- `/api/health` -> `200`, JSON с `status: "ok"`
- `/` -> HTML (`<!doctype html>`)

## 6) Проверка Alembic-конфига
Команда:
```bash
cd backend && python3 -m alembic -c alembic.ini current
```

Ожидаемый результат:
- команда выполняется без падения Alembic env/config;
- для пустого `backend/alembic/versions` допустим ответ без ревизии (`None`/пусто).

## 7) Проверка Alembic upgrade на чистой БД
Команда:
```bash
cd backend && ASYA_DB_PATH=./data/asya-0.2.sqlite3 python3 -m alembic -c alembic.ini upgrade head
```

Ожидаемый результат:
- миграция `20260502_01` применяется без ошибок;
- в SQLite создаются таблицы: `users`, `auth_sessions`, `chats`, `messages`, `file_meta`, `usage_records`, `access_requests`, `encrypted_secrets`;
- таблица `alembic_version` содержит текущую ревизию `20260502_01`.

## 8) Тесты сервисов users/chats
Покрытие в `backend/tests/test_user_chat_services.py`:
- создание пользователя автоматически создаёт `Base-chat`;
- у пользователя сохраняется один активный `Base-chat`;
- CRUD операций чата (create/rename/archive/soft-delete);
- защита `Base-chat` от archive/delete;
- изоляция данных: пользователь A не видит и не читает чат пользователя B.

## 9) Тесты auth v1
Покрытие в `backend/tests/test_auth.py`:
- регистрация пользователя (`/api/auth/register`) и auto-инициализация сессии после login;
- login/logout/me happy-path;
- неправильный пароль;
- запрет login для `pending`/`disabled`;
- токен после logout больше не даёт доступ к `/api/auth/me`;
- `login/me` возвращают `preferred_chat_id` для перехода в Base-chat/последний доступный чат;
- режим `AUTH_REGISTRATION_MODE=closed` сохраняет `AccessRequest` вместо создания пользователя.

## 10) Тесты access request flow
Покрытие в `backend/tests/test_access_requests.py`:
- публичная подача заявки в `pending`;
- предсказуемая обработка повторной заявки на тот же email (возврат той же pending-записи);
- admin-only доступ к списку и действиям approve/reject;
- без авторизации admin endpoint-ы возвращают `401`, для non-admin — `403`;
- запрет self-approve;
- после approve создаётся/активируется пользователь и создаётся `Base-chat`.

## 11) Тесты migration-layer session/chat в БД
Покрытие:
- `backend/tests/test_session.py`:
  - CRUD сессии через auth-user;
  - изоляция: пользователь B не может читать/удалять сессию пользователя A.
- `backend/tests/test_usage.py`:
  - usage/session endpoint работает с message history из БД;
  - ownership-check для session usage.
- `backend/tests/test_chat.py`:
  - сохранён SSE smoke, контракт streaming не сломан.

## 12) Тесты file metadata и usage records в БД
Покрытие:
- `backend/tests/test_files.py`:
  - upload требует ownership сессии (изоляция между пользователями);
  - прежние лимиты и валидации файлов сохранены.
- `backend/tests/test_usage.py`:
  - usage overview/session читают DB-агрегации `UsageRecord`;
  - usage/session недоступен для чужой сессии (`404`).

## 13) Тесты шифрования секретов
Покрытие:
- `backend/tests/test_secret_crypto_service.py`:
  - encrypt/decrypt roundtrip;
  - разные ciphertext для одинакового plaintext (nonce/IV поведение Fernet);
  - ошибка при неверном ключе;
  - ошибка при отсутствии `MASTER_ENCRYPTION_KEY`.
- `backend/tests/test_encrypted_secret_service.py`:
  - `EncryptedSecretService` сохраняет в БД только ciphertext;
  - значение успешно расшифровывается тем же ключом.

## 14) Frontend auth UI
Покрытие в `frontend/src/App.test.tsx`:
- при неавторизованном `/api/auth/me` показывается экран входа;
- успешный login открывает вкладку `Чат`;
- при авторизованном пользователе `ChatPage` использует `preferred_chat_id` и не создаёт новую сессию автоматически.

## 15) Multiple chats UI/API
Покрытие:
- `backend/tests/test_chats_api.py`:
  - список чатов содержит `Base-chat`;
  - доступно чтение истории чата;
  - CRUD обычного чата (create/rename/archive/delete);
  - `Base-chat` нельзя удалить через обычный delete endpoint.
- `frontend/src/pages/ChatPage.test.tsx`:
  - базовый список чатов рендерится;
  - отправка/streaming по выбранному чату сохраняет текущий UX.

## 16) Frontend admin access requests UI
Покрытие в `frontend/src/App.test.tsx`:
- admin-пользователь видит в `Настройки` раздел `Admin: Заявки на доступ`;
- раздел показывает pending заявку;
- non-admin пользователям этот раздел не отображается.
