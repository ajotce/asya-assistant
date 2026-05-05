# Bitrix24 integration audit (v0.5, read-only)

Дата аудита: 2026-05-03.
Контур: только облачный Bitrix24 (cloud), только read-only.

## 1) Cloud Bitrix24

- Для cloud-версии REST API доступен в актуальной версии.
- В проекте Asya интеграция ограничена только чтением CRM/Tasks/Telephony данных.
- On-premise особенности в этот scope не входят.

## 2) Авторизация

Поддерживаемые варианты для cloud:

- Incoming webhook (локальный вебхук, постоянный секрет).
- OAuth 2.0 (access token + refresh token).

В Asya:

- Данные подключения (`base_url`, `auth_mode`, `auth_secret`) хранятся только в `encrypted_secrets`.
- Секреты не возвращаются через API.
- Ошибки подключения должны возвращаться безопасно, без утечки credential-данных.

## 3) Read-only методы в scope

CRM:

- `crm.lead.list`, `crm.lead.get` (лиды).
- `crm.deal.list`, `crm.deal.get` (сделки).
- `crm.contact.list`, `crm.contact.get` (контакты).
- `crm.category.list` (воронки/категории сделок).
- `crm.status.list` (стадии и источники, через `ENTITY_ID`).

Tasks:

- `tasks.task.list`.

Telephony / communications:

- `voximplant.statistic.get` (история звонков/коммуникаций при наличии прав).

## 4) Ограничения и rate limits

- REST может вернуть `QUERY_LIMIT_EXCEEDED` при высокой интенсивности запросов.
- Возможна блокировка `OVERLOAD_LIMIT` на стороне Bitrix24 при перегрузке.
- API может быть недоступен на некоммерческих тарифах (`ACCESS_DENIED`).
- Нужен HTTPS для вызовов API.
- Доступ к части данных зависит от прав пользователя Bitrix24 (например, telephony stats).

## 5) Почему write запрещён

В текущей фазе v0.5 Bitrix24 используется только как источник данных для аналитики и обзора.
Пользователь явно запретил любые изменения внешних сущностей из Asya.
Поэтому:

- в backend отсутствуют create/update/delete методы для Bitrix24;
- добавлены только `GET` endpoint-ы;
- отсутствуют POST/PATCH/DELETE endpoint-ы для Bitrix24 в Asya API;
- тесты отдельно проверяют запрет write методов и HTTP-ограничения.

## 6) Безопасность и приватность

- Credentials хранятся только encrypted.
- В логах и activity нельзя сохранять полные персональные данные клиентов.
- В ответах инструментов использовать агрегаты (counts/sums) и минимально нужные поля.
