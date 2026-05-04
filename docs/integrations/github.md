# GitHub integration (v0.5, read-only)

Статус: реализовано в read-only scope.

## Scope

Интеграция GitHub в этом шаге поддерживает только чтение данных через API GitHub.
Write-операции намеренно не реализованы.

Поддержанные сценарии:
- список репозиториев пользователя;
- чтение данных репозитория;
- список issues;
- список pull requests;
- список commits;
- чтение файла по `path` + optional `ref`;
- поиск кода (`/search/code`).

## Безопасность

- Доступ user-scoped: каждый запрос выполняется только от имени текущего пользователя.
- Access token берётся только из `encrypted_secrets` через существующий OAuth/integration слой.
- Токены и секреты не возвращаются в API и не логируются.
- Для собственного репозитория Asya (`ajotce/asya-assistant`) действует ограничение: доступ только для admin-пользователя.

## Endpoint-ы (read-only)

- `GET /api/integrations/github/status`
- `GET /api/integrations/github/repos`
- `GET /api/integrations/github/repos/{owner}/{repo}`
- `GET /api/integrations/github/repos/{owner}/{repo}/issues`
- `GET /api/integrations/github/repos/{owner}/{repo}/pulls`
- `GET /api/integrations/github/repos/{owner}/{repo}/commits`
- `GET /api/integrations/github/repos/{owner}/{repo}/files?path=...&ref=...`
- `GET /api/integrations/github/search?query=...`

## Что не реализовано в этом шаге

- любые write-action в GitHub (issues/comments/PR/review/merge и т.д.);
- GitHub App и webhooks;
- фоновая синхронизация write-state.

## Chat/Observer

Добавлены read-only сценарии в chat tools:
- «что в моих PR?»;
- «покажи открытые issues в репозитории owner/repo»;
- «прочитай файл X в репозитории owner/repo».

Добавлены detector-ы observer:
- `GitHubPRStaleWithoutReview`;
- `GitHubMentionedInIssueOrPR`.
