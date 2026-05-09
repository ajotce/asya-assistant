# Changelog

## v1.0.0 (2026-05-09)

### 1.0.6 Monitoring
- Добавлены runtime health/readiness endpoint-ы.
- Подготовлена интеграция мониторинга (Prometheus/Grafana/Sentry-ready конфиги).
- Улучшена структуризация operational логирования.

### 1.0.7 Backups
- Реализованы backup/restore процедуры для данных.
- Добавлены документы и runbook для восстановления.

### 1.0.8 User Export & Account Deletion (K8)
- Добавлен JSON export пользовательских данных.
- Реализован безопасный one-time download token с TTL.
- Добавлен двухшаговый процесс удаления аккаунта с подтверждением.
- Обеспечено исключение integration tokens из export.

### 1.0.9 OAuth (Google/Yandex)
- Добавлен OAuth foundation с PKCE/state.
- Реализованы provider-specific OAuth подключения в рамках фазы.
- Добавлены state ownership/expiry/reuse проверки.

### 1.0.10 Voice (Wake-word & Listening)
- Реализована поддержка wake-word.
- Добавлен режим «Слушаю» для обработки голосовых команд.

### 1.0.11 Open Registration & Onboarding
- Обновлён auth flow для публичного onboarding сценария.
- Добавлено завершение onboarding в auth lifecycle.

### 1.0.12 Public Site
- Подготовлен public-facing контур и юр. документация в рамках проектного scope.

### 1.0.13 Stabilization
- Выполнен security audit (OWASP checklist + RBAC + logging + token lifecycle audit).
- Исправлены security findings:
  - `[security-fix-1]` SHA256 для diary audio hash.
  - `[security-fix-2]` SHA256 для observer dedup key.
- Выполнен load test (50 concurrent users, 5 minutes).

### 1.0.14 Release Readiness
- Актуализированы acceptance критерии v1.0.
- Подготовлены user docs (`user-guide`, `faq`).
- Подготовлен release announcement draft (без публикации).
- Подготовка ветки и артефактов к выпуску `v1.0.0`.
