# IMAP интеграция (v0.5)

Статус: реализовано в read-only scope + безопасное `mark as read`.

Что поддерживается:
- ручное подключение IMAP (email/username/password + host/port/security);
- presets: Yandex Mail, Mail.ru, Outlook, ProtonMail Bridge, Custom;
- тест подключения;
- список папок;
- список писем;
- чтение письма;
- поиск писем;
- пометка письма как прочитанного;
- отключение интеграции.

Безопасность:
- credentials хранятся только как encrypted secrets (`encrypted_secrets`);
- plaintext password/app password не возвращается через API;
- содержимое писем не пишется в логи;
- все endpoint-ы и данные строго user-scoped.

Ограничения текущего шага:
- SMTP draft/send не включён в этот scope;
- observer использует безопасную эвристику источника (`gmail`/`imap`) без хранения тела письма.

Backend endpoint-ы:
- `POST /api/integrations/imap/test`
- `POST /api/integrations/imap/connect`
- `GET /api/integrations/imap/folders`
- `GET /api/integrations/imap/messages`
- `GET /api/integrations/imap/messages/{uid}`
- `GET /api/integrations/imap/search`
- `POST /api/integrations/imap/messages/{uid}/read`
- `DELETE /api/integrations/imap`
