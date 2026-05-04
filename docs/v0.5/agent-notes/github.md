# Agent A notes: GitHub read-only

Дата: 2026-05-03
Ветка: `0.5/github-readonly`

Сделано:
- provider `github` добавлен в integration layer;
- добавлен OAuth provider для GitHub;
- реализован backend read-only `GitHubService`;
- добавлены API endpoint-ы для GitHub read-only;
- write HTTP methods на GitHub routes отсутствуют (проверка 405 в тестах);
- добавлены chat read-only команды для PR/issues/file;
- добавлены observer detector-ы для stale PR и mentions;
- добавлен минимальный UI-блок в Settings для просмотра repos/issues/PR/file;
- добавлены docs `docs/integrations/github.md`.

Важно для координатора:
- central `docs/api.md` не менялся специально, чтобы не конфликтовать в интеграции фазы;
- `mypy` глобально падает на существующем `app/integrations/imap.py` (не связано с GitHub scope);
- frontend `vitest` сейчас не запускается из-за окружения `@rollup/rollup-darwin-arm64` optional dependency.
