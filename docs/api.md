# API

Текущий документ фиксирует минимальную API-базу для MVP и служит оглавлением до полной OpenAPI-документации.

## Базовые принципы
- Префикс backend endpoint-ов: `/api/*`.
- Секреты и API-ключи не возвращаются во frontend.
- Полная схема API доступна через OpenAPI/Swagger backend.
- В локальном MVP backend может отдавать собранный frontend (`frontend/dist`) с того же origin.

## Базовые группы endpoint-ов MVP
- `/health`
- `/models`
- `/settings`
- `/chat`
- `/files`
- `/session`
- `/usage`

## Локальная раздача frontend через backend
- `GET /` -> `index.html` из собранного frontend.
- `GET /manifest.webmanifest` -> PWA manifest из сборки frontend.
- `GET /assets/*`, `GET /icons/*` -> статические файлы сборки.
- Для SPA-путей backend отдает `index.html` fallback.
- API продолжает работать через `/api/*`.

## Health (MVP)

### `GET /api/health`
Возвращает расширенный статус для страницы `Состояние Asya`:
- базовые поля: `status`, `version`, `environment`, `last_error`;
- `uptime_seconds` — uptime backend с момента старта процесса;
- `vsellm` — статус ключа, base URL и доступности API;
- `model` — выбранная chat-модель;
- `files` — базовый статус файлового модуля;
- `embeddings` — явный статус embeddings (`готов` / `ошибка` / `не настроен`);
- `storage` — явный статус временного хранилища (`session_store`, `file_store`, `tmp_dir`, `writable`);
- `session` — состояние runtime-сессий (включая `active_sessions`).

Пример:
```json
{
  "status": "ok",
  "version": "0.1.0",
  "environment": "local",
  "uptime_seconds": 7,
  "vsellm": {
    "api_key_configured": true,
    "base_url": "https://api.vsellm.ru/v1",
    "reachable": true
  },
  "model": {
    "selected": "gpt-4o"
  },
  "files": {
    "enabled": true,
    "status": "готов"
  },
  "embeddings": {
    "enabled": true,
    "model": "text-embedding-3-small",
    "status": "готов",
    "last_error": null
  },
  "storage": {
    "session_store": "готов",
    "file_store": "готов",
    "tmp_dir": "/app/tmp",
    "writable": true
  },
  "session": {
    "enabled": true,
    "active_sessions": 0
  },
  "last_error": null
}
```

## Загрузка файлов в сессию (MVP)

### `POST /api/session/{session_id}/files`
Загрузка файлов в текущую временную backend-сессию.

Формат запроса: `multipart/form-data`  
Поле: `files` (можно передать несколько файлов)

Ограничения:
- поддерживаемые типы: PDF, DOCX, XLSX, изображения;
- максимум 10 файлов за одно сообщение;
- максимум 256 МБ на один файл (настраивается через `MAX_FILE_SIZE_MB`);
- файлы хранятся только в рамках текущей сессии.

Что делает backend для документов (`PDF`, `DOCX`, `XLSX`):
- извлекает текст;
- режет текст на чанки;
- создает embeddings для чанков через VseLLM `/embeddings`;
- сохраняет локальный временный векторный индекс только для текущей сессии.

Что делает backend для изображений:
- валидирует файл через `Pillow` (формат/целостность);
- сохраняет изображение только во временной директории текущей сессии;
- не использует OCR как основной механизм.

Пример успешного ответа (`201`):
```json
{
  "session_id": "b5075c99-3572-4f58-b4bc-d8a52f34fc7f",
  "files": [
    {
      "file_id": "f8f4740a-4471-4439-ab39-7513ad4c958a",
      "filename": "contract.pdf",
      "content_type": "application/pdf",
      "size_bytes": 12456
    }
  ],
  "file_ids": [
    "f8f4740a-4471-4439-ab39-7513ad4c958a"
  ]
}
```

Примеры ошибок:
- `404`: `Сессия не найдена.`
- `400`: `Можно загрузить не более 10 файлов за одно сообщение.`
- `400`: `Файл 'example.txt' не поддерживается. Разрешены типы: PDF, DOCX, XLSX и изображения.`
- `400`: `Файл 'big.pdf' превышает лимит 256 МБ.`
- `400`: `DOCX/PDF/XLSX ... может быть повреждён.`
- `400`: `Изображение '...' повреждено или имеет некорректный формат.`
- `502/504`: понятная ошибка недоступности embeddings API.

### Использование во frontend (ChatPage)
- Перед отправкой сообщения с файлами frontend делает `POST /api/session/{session_id}/files`.
- В `POST /api/chat/stream` frontend передает `file_ids` только для изображений из текущей загрузки.
- Для документов (`PDF/DOCX/XLSX`) frontend не передает `file_ids`: backend использует их через retrieval по данным сессии.
- Если файлов нет, frontend отправляет `POST /api/chat/stream` без `file_ids`.
- После успешной отправки сообщения frontend очищает локальный список выбранных файлов.

### Очистка файлов
`DELETE /api/session/{session_id}` удаляет:
- временный контекст сообщений;
- привязки файлов;
- реальные временные файлы этой сессии на диске;
- временный векторный индекс сессии.

## Поиск релевантных чанков при чате
`POST /api/chat/stream` теперь использует retrieval по загруженным документам:
- строится embedding вопроса;
- выполняется локальный поиск по векторному индексу текущей сессии;
- найденные чанки добавляются в контекст запроса к модели.

Если embeddings API недоступен, поток возвращает `event: error` с понятным текстом ошибки.

## Поддержка изображений в чате
`POST /api/chat/stream` принимает:
- `session_id`
- `message`
- `file_ids` (опционально) — список `file_id` изображений, прикрепленных к текущему сообщению.

Если `file_ids` содержит изображения:
- backend проверяет, что эти `file_id` принадлежат текущей сессии;
- backend блокирует запрос заранее только если модель явно помечена как `supports_vision=false`;
- если `supports_vision` неизвестен (`null`) или модель отсутствует в metadata, backend пробует отправить запрос в провайдер и возвращает его ошибку при отказе;
- изображения передаются в VseLLM в составе user-message как image input.

Если модель не поддерживает vision, поток возвращает понятную ошибку:
- `event: error` с текстом: выбранная модель не поддерживает анализ изображений.

Frontend должен показать это как пользовательскую ошибку и предложить выбрать vision-модель в настройках.

## Usage (MVP)

### `GET /api/usage`
Возвращает минимальный общий usage-срез по текущему runtime:
- `chat` — usage чата из `chat/stream` (если провайдер возвращает `usage`, статус `available`, иначе `unavailable`);
- `embeddings` — usage embeddings из upload/retrieval pipeline (`available` при наличии данных);
- `cost` — расчет стоимости (в MVP `status=unavailable`, стоимость `null`, цены моделей не хардкодятся);
- `runtime` — текущие доступные runtime-данные (`active_sessions`, `selected_model`, `embedding_model`).

Пример:
```json
{
  "chat": {
    "prompt_tokens": null,
    "completion_tokens": null,
    "total_tokens": null,
    "status": "unavailable",
    "note": "Данные usage по chat не сохраняются в текущем MVP."
  },
  "embeddings": {
    "input_tokens": null,
    "total_tokens": null,
    "status": "unavailable",
    "note": "Данные usage по embeddings не сохраняются в текущем MVP."
  },
  "cost": {
    "currency": null,
    "total_cost": null,
    "status": "unavailable",
    "note": "Стоимость не рассчитывается: цены моделей не хардкодятся в MVP."
  },
  "runtime": {
    "active_sessions": 0,
    "selected_model": "gpt-4o",
    "embedding_model": "text-embedding-3-small"
  }
}
```

### `GET /api/usage/session/{session_id}`
Возвращает usage-срез для конкретной сессии:
- `chat` / `embeddings` возвращают фактически собранные токены для данной сессии, если данные доступны;
- если провайдер не вернул usage, статус соответствующего блока будет `unavailable`;
- `cost` в MVP возвращается как `unavailable` (`null`, без хардкода цен моделей);
- `runtime` содержит доступные данные сессии:
  - `session_id`, `created_at`;
  - `message_count`, `user_messages`, `assistant_messages`;
  - `file_count`, `chunks_indexed`.

Ошибки:
- `404`: `Сессия не найдена.`

## Документация backend
- OpenAPI schema: `GET /openapi.json`
- Swagger UI: `GET /docs`
