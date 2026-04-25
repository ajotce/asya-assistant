# Testing

Документ фиксирует фактические команды проверки в текущем MVP.

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
- покрыты минимальные MVP-сценарии:
  - `App` (прямое открытие `/status`, сохранение runtime-состояния чата при `Чат -> Настройки -> Чат`, отсутствие повторного создания сессии при возврате на вкладку чата)
  - `ChatPage` (рендер, отправка, streaming, отображение блока «Размышления модели» при наличии reasoning, отсутствие блока для обычных моделей, ошибки)
  - `SettingsPage` (модель, системный промт, предупреждение и disabled option для моделей с явным `supports_chat=false`)
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
- текущий baseline: `48 passed` (возможны предупреждения, не блокирующие запуск)
- для совместимости моделей покрыты сценарии:
  - нормализация `supports_chat`/`supports_stream` из provider metadata (`supports_*`, `capabilities`, `endpoints`);
  - понятная маппинга provider body ошибок в chat;
  - fallback non-stream при явной provider-ошибке streaming;
- для streaming размышлений покрыты сценарии:
  - `event: thinking` эмитится при `delta.reasoning_content` от провайдера, reasoning не попадает в историю сессии;
  - non-stream fallback с `message.reasoning_content` отдаёт `event: thinking` до `event: token`.

## 4) Frontend сборка
Команда:
```bash
make build-frontend
```

Ожидаемый результат:
- выполняется `tsc --noEmit && vite build`
- в `frontend/dist` появляются актуальные артефакты сборки
- команда завершается с кодом `0`

## 5) Smoke локального запуска (рекомендуется перед релизным коммитом)
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
