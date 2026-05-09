# Briefings and Workflows (I2, I3)

Статус: реализовано в ветке `1.0/briefings`.

## Цель и scope

Утренние и вечерние briefings формируются автоматически по расписанию и вручную по trigger.
Источники: активные интеграции пользователя (`google_calendar`, `linear`, `todoist`, `gmail`, `imap`) + safe metadata.
Доставка: `in_app` (через Notification Center activity + deeplink) и `telegram` (если канал включен и Telegram привязан).

## Backend

- Модель `briefings`:
  - `id`, `user_id`, `kind`, `created_at`, `updated_at`, `content`, `delivered_via`.
- Модель `briefing_settings`:
  - `user_id`, `timezone`, `morning_enabled`, `evening_enabled`, `morning_time`, `evening_time`, `channel_in_app`, `channel_telegram`.
- Сервис `BriefingService`:
  - `generate(user_id, kind)` — собирает контекст интеграций, вызывает LLM prompt, сохраняет briefing, отправляет доставку.
  - `run_scheduled()` — ежеминутная проверка расписаний по user timezone.
  - `cleanup_old(days=30)` — удаление briefings старше retention.

## API

- `GET /api/briefings?days=30&limit=100` — список briefings.
- `GET /api/briefings/{id}` — получить briefing.
- `POST /api/briefings/generate?kind=morning|evening` — ручная генерация.
- `GET /api/briefings/settings` — получить настройки расписания/каналов.
- `PATCH /api/briefings/settings` — обновить настройки.

## Scheduler

В `scheduler_service` добавлены задачи:

- `briefings` — interval 1 minute, вызывает `run_scheduled()`.
- `briefings_cleanup` — daily 00:30 UTC, удаляет записи старше 30 дней.

## Frontend

- Вкладка `Брифинги`:
  - список за 30 дней;
  - просмотр выбранного briefing;
  - ручной trigger morning/evening;
  - быстрые настройки времени/каналов/таймзоны.
- `Settings`:
  - отдельный блок `Брифинги` для включения/выключения morning/evening;
  - время morning/evening;
  - выбор каналов доставки (`in_app`, `telegram`) и timezone.

## Security

- В briefing не пишутся токены и integration secrets.
- Контекст строится только из safe metadata.
- Telegram отправка ограничена markdown text и активной привязкой пользователя.

## Тесты

- Генерация morning/evening briefing.
- Доставка только в включенные каналы.
- Retention cleanup: старше 30 дней удаляется.
