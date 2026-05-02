# Testing

Документ фиксирует обязательные проверки для Asya 0.2/0.3.

## 1. Обязательные команды
```bash
make test
make lint
make build-frontend
```

Frontend unit tests:
```bash
docker run --rm -v "$PWD/frontend:/work" -w /work node:20-alpine sh -lc "npm ci && npm test"
```

Manual smoke (README flow):
```bash
docker compose up --build
curl http://localhost:${ASYA_PORT:-8000}/api/health
```

## 2. Security regression checklist
- user-scoped endpoints недоступны для чужого пользователя (`404`/`403` по контракту).
- auth/session revoke работает (`/api/auth/logout`).
- admin-only endpoint-ы защищены (`401`/`403`).
- нет утечки секретов в API payload/логах.

## 3. Дополнительные проверки для Asya 0.3

### Memory
- записи памяти создаются только для текущего `user_id`;
- `forbidden/deleted` не попадают в retrieval и chat context;
- операции confirm/forbid/edit/rollback отражаются в memory feed.
- frontend: вкладка `Память` показывает факты/правила/эпизоды и статусные действия (confirm/edit/outdated/forbid/hide для фактов);
- frontend: для правил доступны create/edit/disable;
- frontend: отображаются source + статус + created/updated для сущностей памяти;
- frontend: есть `loading/empty/error` состояния и ручное обновление секции памяти;
- frontend: технические ID не отображаются в UI.
- snapshots: manual snapshot создаётся и попадает в список/summary;
- rollback: восстанавливает состояние фактов/правил из snapshot;
- rollback user-scoped: чужой snapshot недоступен;
- rollback пишет activity event `memory_rollback` и memory change kind `rollback`.

### Spaces
- пользователь не видит чужие пространства;
- чат нельзя открыть/изменить в чужом пространстве;
- `Asya-dev` недоступен non-admin пользователю.
- frontend: при выборе пространства отображаются только чаты этого пространства;
- frontend: переключение вкладок не сбрасывает runtime-state чата;
- frontend: loading/error для spaces/settings отрисовываются и не ломают чат.

### Personality/Rules
- изменения профиля личности и правил user-scoped;
- space overlay не «протекает» в другие пространства.
- frontend: доступны редактирование personality параметров (tone/humor/initiative/disagree/name-address) и создание правил вручную.

### Activity log
- события логируются по ключевым действиям;
- события user-scoped;
- в событиях нет секретов.
- доступны фильтры `event_type/entity_type/space/date_from/date_to` в `GET /api/activity-log`;
- события admin-only пространства не видны обычному пользователю (из-за user-scope + space-access check).
- frontend: вкладка `Активность` показывает события понятным языком и не показывает технические ID/prompt.

## 4. Документационные изменения
Если менялась только документация:
- тесты приложения можно не запускать;
- обязательно сделать ручную проверку markdown-файлов (структура, ссылки, логическая непротиворечивость);
- если markdown-линтер в проекте отсутствует, это явно указывается в отчёте.
