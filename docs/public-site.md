# Public Site (1.0.12)

## Назначение

Публичный сайт Asya размещён в том же frontend-приложении и отдаётся backend-ом как SPA-статика.

Публичные страницы:
- `/` — лендинг
- `/request-access` — форма запроса инвайта
- `/privacy` — шаблон privacy policy
- `/terms` — шаблон terms of service
- `/data-policy` — шаблон политики обработки ПДн (с акцентом на 152-ФЗ)

Внутреннее приложение (авторизованная зона):
- `/chat`, `/settings`, `/memory`, `/activity`, `/observer`, `/diary`, `/status`

Авторизованный пользователь при заходе на публичный URL автоматически перенаправляется на `/chat`.

## Где редактировать контент

Основные файлы:
- `frontend/src/pages/public/LandingPage.tsx`
- `frontend/src/pages/public/RequestAccessPage.tsx`
- `frontend/src/pages/public/LegalPage.tsx`
- `frontend/src/components/PublicFooter.tsx`

SEO и мета:
- `frontend/src/seo.ts` — динамический `<title>`, `meta description`, Open Graph
- `frontend/index.html` — базовые fallback-meta для первого рендера
- `frontend/public/robots.txt`
- `frontend/public/sitemap.xml`

## Форма инвайта

Страница `/request-access` отправляет данные в:
- `POST /api/access-requests`

Поля формы:
- `email`
- `display_name`
- `reason`

Отправка разрешена только при отмеченном обязательном checkbox-согласии:
- «Я принимаю условия использования и политику конфиденциальности»

Ссылки в тексте согласия:
- `/terms`
- `/privacy`

## Юридические шаблоны

`/privacy`, `/terms`, `/data-policy` содержат только базовую структуру + TODO-блоки для владельца проекта.
Финальное юридическое содержание заполняется владельцем проекта отдельно.
