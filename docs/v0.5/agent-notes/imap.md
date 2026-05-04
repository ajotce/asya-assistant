# Agent D — IMAP (v0.5)

Ветка: `0.5/imap-mail`

Сделано:
- добавлен provider `imap` в enum + alembic migration `20260503_02_imap_provider.py`;
- реализован `backend/app/integrations/imap.py` (test/connect/list/read/search/mark-read/disconnect);
- API для IMAP добавлен в `routes_integrations.py`;
- observer detector `UnansweredImportantEmail` учитывает `imap` как источник;
- добавлена UI-форма подключения IMAP в `SettingsPage` (presets + custom + status/errors);
- добавлены backend/frontend тесты для базового IMAP flow.

Риски/долги:
- SMTP draft/send вынесен в отдельный sub-step;
- для некоторых IMAP серверов может понадобиться тонкая настройка folder names/delimiter;
- parsing тела письма сейчас ориентирован на text/plain fallback.
