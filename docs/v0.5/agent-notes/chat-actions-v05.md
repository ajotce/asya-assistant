# Agent J — chat actions (v0.5)

Ветка: `0.5/chat-actions-v05`
База: `0.5-extended`

## Что добавлено

- Расширен `ActionRouter` для v0.5 действий:
  - `github repos/issues/prs/file` (read-only)
  - `bitrix leads/deals/funnel_sum` (read-only)
  - `storage search/read/save by provider`
  - `imap search/read`
  - `document template_fill`
  - `briefing generate`
  - `rollback preview/execute`
- Добавлен intent extraction для русских команд:
  - «что нового в моих PR?»
  - «сколько денег в воронке X на стадии Y?»
  - «найди файл в Яндекс.Диске»
  - «сделай гарантийный талон…»
  - «сгенерируй вечерний итог»
  - «откати последнее действие»
- Обновлена confirmation policy:
  - read actions — без подтверждения;
  - document generation (`document.template_fill`) — без подтверждения по умолчанию;
  - write (`storage.save`) — только через pending + `/confirm`;
  - rollback execute — только через pending + `/confirm`.

## Безопасность и ограничения

- Hidden write запрещён: actions с записью не выполняются до explicit confirm.
- GitHub остаётся read-only на уровне routing.
- Bitrix24 остаётся read-only на уровне routing.
- Центральный `docs/api.md` в этой ветке не менялся (сведение делает координатор).
