# Asya MVP: аудит и пошаговый план до 100% (промты для Codex)

## 1) Краткий аудит текущего состояния

Текущее состояние репозитория `ajotce/asya-assistant`:
- Backend тесты проходят: `31 passed`.
- Frontend TypeScript/Vite build проходит.
- Backend запускается в Docker и отвечает `GET /api/health`.
- Базовые страницы frontend есть: чат, настройки, состояние.
- Реализованы backend-сессии, streaming chat, загрузка файлов, embeddings/retrieval, проверка vision-моделей.

Ключевые незакрытые пункты до 100% MVP по `AGENTS.md` + ТЗ:
- Нет отдельной группы endpoint'ов `/usage`.
- Frontend чат не завершён по файловому UX (загрузка/список прикреплений/передача `file_ids` в `chat/stream`).
- Страница `Состояние Asya` не показывает часть требуемых статусов (например uptime backend, явный статус embeddings/временного хранилища).
- Не настроен frontend lint.
- Не реализованы минимальные frontend тесты из AGENTS.
- Нужен финальный прогон приёмки по критериям готовности MVP с обновлением документации.

---

## 2) Как использовать этот план

- Запускай промты строго по порядку: от Prompt 1 к Prompt 10.
- После каждого шага: изменения в коде + проверки + обновление `docs/development-log.md` + commit.
- Ничего вне MVP не добавляй.
- Не менять архитектуру MVP без явного запроса.

---

## Prompt 1: Базовая точка и защита от регрессий

```text
Проверь репозиторий ajotce/asya-assistant и прочитай AGENTS.md, asya-mvp-tech-spec.md, asya-mvp-development-plan.md.

Сделай только подготовку:
1) Проверь, что текущая ветка актуальна и рабочее дерево чистое.
2) Прогони текущие проверки: make test, make build-frontend, docker compose build, docker compose up -d backend + curl /api/health + docker compose down.
3) Зафиксируй результат в docs/development-log.md как baseline для финального этапа.

Ничего функционально не меняй.
После этого сделай commit с осмысленным сообщением.
```

## Prompt 2: Заверши frontend-файлы в чате (MVP UX)

```text
Доработай frontend чат под требования MVP по файлам, не меняя backend API-контракт:
1) Добавь в ChatPage возможность выбрать файлы (до 10), показать список выбранных файлов и удалить файл из списка до отправки.
2) При отправке сообщения:
   - если есть файлы, сначала загружай их через POST /api/session/{session_id}/files,
   - полученные file_ids передавай в POST /api/chat/stream.
3) Добавь понятные сообщения ошибок пользователю (тип/размер/лимит/vision errors).
4) После успешной отправки очищай локальный список выбранных файлов.
5) Не добавляй историю чатов и долгосрочное хранение.

Проверки:
- make build-frontend
- make test
- ручной smoke: сообщение без файла, сообщение с файлом, сообщение с изображением

Обнови docs/api.md, docs/development.md, docs/development-log.md и сделай commit.
```

## Prompt 3: Добавь backend группу /usage

```text
Реализуй минимальную группу endpoint'ов /usage в backend в рамках MVP:
1) Добавь routes_usage.py и подключи роутер в main.py с префиксом /api.
2) Реализуй GET /api/usage (и при необходимости GET /api/usage/session/{session_id})
   с понятной структурой ответа: хотя бы текущие доступные данные usage (chat/embeddings),
   даже если часть полей временно null.
3) Не хардкодь стоимость моделей. Если данных нет — возвращай явно, что недоступно.
4) Добавь схемы в models/schemas.py.

Покрой тестами backend/tests:
- успешный ответ usage endpoint,
- формат ответа,
- обработка пустых/отсутствующих данных.

Проверки:
- make test
- docker compose up -d backend + curl /api/usage + docker compose down

Обнови docs/api.md, docs/architecture.md, docs/testing.md, docs/development-log.md и сделай commit.
```

## Prompt 4: Расширь /api/health до требований страницы состояния

```text
Доработай backend health-ответ под требования MVP страницы «Состояние Asya»:
1) Добавь uptime backend.
2) Добавь явный статус embeddings (готов/ошибка/не настроен и т.п.).
3) Добавь явный статус временного хранилища сессий/файлов.
4) Сохрани существующие поля, не ломай обратную совместимость без необходимости.

Покрой тестами health-роут:
- наличие новых полей,
- корректные значения при отсутствии API ключа,
- базовый happy path.

Проверки:
- make test
- docker compose up -d backend + curl /api/health + docker compose down

Обнови docs/api.md, docs/testing.md, docs/development-log.md и сделай commit.
```

## Prompt 5: Доработай страницу «Состояние Asya»

```text
Обнови frontend страницу StatusPage под фактический расширенный /api/health:
1) Покажи backend online/offline, выбранную модель, статус API key.
2) Добавь отображение uptime backend.
3) Добавь статус embeddings.
4) Добавь статус временного хранилища.
5) Оставь UX простым и понятным на русском.

Проверки:
- make build-frontend
- ручная проверка страницы состояния

Обнови docs/development.md и docs/development-log.md, затем commit.
```

## Prompt 6: Настрой frontend lint (без лишних зависимостей)

```text
Добавь минимальный рабочий lint для frontend:
1) Подключи ESLint для TypeScript + React (минимальная конфигурация, без избыточных плагинов).
2) Добавь npm script lint в frontend/package.json.
3) Обнови Makefile, чтобы make lint реально запускал frontend lint.
4) Исправь найденные lint-проблемы в коде.

Проверки:
- make lint
- make build-frontend
- make test

Обнови docs/testing.md, README.md, docs/development-log.md и сделай commit.
```

## Prompt 7: Добавь минимальные frontend тесты из AGENTS

```text
Добавь минимальный набор frontend тестов (в рамках AGENTS):
1) рендер главного экрана,
2) отправка сообщения,
3) отображение streaming-состояния,
4) настройки модели,
5) редактирование системного промта,
6) страница состояния,
7) отображение ошибок.

Выбери лёгкий стек тестирования для Vite+React (без усложнения архитектуры).
Добавь script test в frontend/package.json (реальный, не заглушка).

Проверки:
- frontend test script
- make test
- make build-frontend

Обнови docs/testing.md и docs/development-log.md, затем commit.
```

## Prompt 8: Приёмка документации и runbook запуска

```text
Приведи документацию к финальному MVP-состоянию:
1) README.md — один понятный сценарий запуска с нуля.
2) docs/api.md — актуальные endpoint'ы (/health,/models,/settings,/chat,/session,/files,/usage).
3) docs/architecture.md — фактическая архитектура без расхождений с кодом.
4) docs/testing.md — точные команды и ожидаемые результаты.
5) docs/development-log.md — запись по этапу.

Проверь, что инструкции соответствуют реальным командам и окружению.
После проверки сделай commit.
```

## Prompt 9: Финальный security-pass для MVP

```text
Сделай финальный security-pass без расширения scope:
1) Проверь, что .env не отслеживается git.
2) Убедись, что реальные ключи/токены не попали в tracked файлы.
3) Проверь, что API ключ не возвращается во frontend и не логируется.
4) Проверь .gitignore на временные файлы, sqlite, логи, кеши.
5) Убедись, что backend не требует публичного внешнего открытия.

Добавь только необходимые правки и обнови docs/development-log.md.
Сделай commit.
```

## Prompt 10: Финальная приёмка 100% MVP по AGENTS.md

```text
Проведи финальную приёмку MVP по критериям разделов 17 и 18 AGENTS.md:
1) Запуск проекта локально по README.
2) Backend в Docker.
3) Frontend работает через backend (same-origin).
4) Выбор модели, чат, streaming.
5) Системный промт.
6) Загрузка поддерживаемых файлов.
7) Ответ с учётом файлов (retrieval).
8) Очистка сессии.
9) /health и страница состояния.
10) Тесты проходят.
11) Документация актуальна.
12) Секретов в репозитории нет.

Сформируй отчёт:
- что прошло,
- что не прошло,
- блокеры,
- финальный статус: «MVP завершён» или «MVP не завершён» с конкретным списком остатков.

Если всё прошло — обнови docs/development-log.md и сделай финальный commit с пометкой финальной приёмки MVP.
```

---

## 3) Целевой результат после Prompt 10

Ожидаемый итог:
- Все обязательные MVP-функции из AGENTS/ТЗ реализованы.
- Проект воспроизводимо запускается по README.
- Проверки и тесты стабильны.
- Документация синхронизирована с фактическим кодом.
- Можно честно зафиксировать статус «MVP завершён».
