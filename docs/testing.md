# Testing

## Доступные проверки на текущем этапе

### Backend
```bash
make test
```

### Frontend
```bash
make lint
make build-frontend
docker run --rm -v "$PWD/frontend:/work" -w /work node:20-alpine sh -lc "npm test"
```

## Что проверяем
- Базовая структура проекта присутствует.
- Конфигурационные файлы заполнены без секретов.
- Frontend lint проходит (`ESLint` для TypeScript + React).
- Сборка frontend выполняется.
- Frontend unit-тест `StatusPage` проходит.
- Backend-тесты проходят (если окружение готово).
- Usage endpoints возвращают ожидаемый формат и корректно обрабатывают отсутствие данных.
- Health endpoint содержит uptime и статусы embeddings/storage для страницы `Состояние Asya`.

## Проверки health endpoint'а
Автотесты backend покрывают:
- наличие новых health-полей (`uptime_seconds`, `embeddings`, `storage`);
- корректное поведение при отсутствии API-ключа;
- базовый happy path c достижимым VseLLM.

Ручной smoke:
1. `docker compose up -d backend`
2. `curl http://localhost:${ASYA_PORT}/api/health`
3. `docker compose down`

## Проверки файлового пайплайна
Автотесты backend покрывают:
- валидацию количества/типа/размера файлов;
- извлечение текста из PDF, DOCX, XLSX на простых примерах;
- ошибки для повреждённых и пустых файлов;
- очистку временных файлов после удаления сессии;
- chunking текста документов;
- mock-поиск релевантных чанков и добавление retrieval-контекста в chat payload;
- ошибку при недоступном embeddings API.

## Ручная проверка извлечения текста
Минимальный сценарий:
1. Создать временную сессию `POST /api/session`.
2. Загрузить тестовые `PDF`, `DOCX`, `XLSX` через `POST /api/session/{session_id}/files`.
3. Убедиться, что backend принял файлы (`201`) и сохранил их в рамках текущей сессии.
4. Задать вопрос через `POST /api/chat/stream` и убедиться, что ответ строится с retrieval-контекстом по документу.
5. Проверить, что для документов текст извлечён и чанки индексированы (по runtime-store/отладочному сценарию).
6. Удалить сессию `DELETE /api/session/{session_id}` и убедиться, что временные файлы и индекс очищены.

## Проверки usage endpoint'ов
Автотесты backend покрывают:
- успешный ответ `GET /api/usage`;
- формат и поля ответов `GET /api/usage` и `GET /api/usage/session/{session_id}`;
- поведение при недоступных usage-данных (явные `null` + `status=unavailable`);
- отражение собранных usage-данных в `GET /api/usage` (`status=available` при наличии токенов);
- `404` для несуществующей сессии в `GET /api/usage/session/{session_id}`.

Ручной smoke:
1. `docker compose up -d backend`
2. `curl http://localhost:${ASYA_PORT}/api/usage`
3. `docker compose down`

Дополнительно для фактического usage:
1. создать сессию `POST /api/session`;
2. загрузить документ `POST /api/session/{session_id}/files` (собирается embeddings usage);
3. отправить сообщение в `POST /api/chat/stream` (если провайдер возвращает usage для stream, соберется chat usage);
4. проверить `GET /api/usage` и `GET /api/usage/session/{session_id}`.
