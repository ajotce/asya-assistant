# iCloud Drive integration (v0.5)

Статус: deferred.

## Decision

В web-Asya (v0.5) iCloud Drive не реализуется как файловый провайдер.

## Why

- Для Asya нужен надёжный API уровня пользовательского файлового диска (`list/metadata/download/upload/delete`).
- Официальные web-интерфейсы Apple для серверной интеграции относятся к CloudKit контейнерам приложения, а не к общему iCloud Drive пользователя.
- Ненадёжные обходы (reverse-engineering/private endpoints/browser automation) не соответствуют требованиям безопасности и поддержки.

## What is implemented now

- В UI отображается карточка статуса iCloud Drive.
- Статус по умолчанию: не подключен.
- Нет runtime-операций с файлами iCloud Drive в web backend.

## Revisit

- Пересмотр в фазе 2.0+ для нативного приложения с корректными Apple capabilities/entitlements.
