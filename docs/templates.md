# Document Templates (H1–H5)

Статус: реализовано в фазе 1.0 (backend ядро + API + frontend базовый UI).

## 1. Цель и scope

Поддержка end-to-end pipeline шаблонов документов:
- H1: карточки шаблонов пользователя.
- H2: заполнение полей и генерация DOCX.
- H3: Vision для VIN/паспорта с валидацией.
- H4: конвертация DOCX -> PDF через внешний converter endpoint.
- H5: возврат двух файлов (DOCX + PDF) в ответе заполнения.

## 2. Модель данных

Таблица: `document_templates`
- `id`, `user_id`, `name`, `description`, `provider`, `file_id`, `fields`, `output_settings`, `created_at`.

`provider`:
- `google_drive`
- `yandex_disk`
- `onedrive`

`fields` (JSON array):
- `key`, `label`, `type`, `required`, `validation`.

Поддерживаемые `type`:
- `text`, `vin`, `passport_number`, `date`, `phone`, `email`.

`output_settings`:
- `format`: `docx` | `pdf` | `both`
- `filename`: базовое имя выходного файла.

## 3. Backend services

### 3.1 DocumentFillService

`fill_template(template_bytes, values) -> docx_bytes`

Поддерживаемые области подстановки `{{FieldKey}}`:
- paragraphs,
- tables,
- headers,
- footers.

### 3.2 VisionService

Методы:
- `extract_vin(image_bytes)`
- `extract_passport_number(image_bytes)`

Валидация:
- VIN: 17 символов, без `I/O/Q`, проверка check digit.
- Паспорт РФ: `NNNN NNNNNN`.

Для low-confidence:
- если `confidence < 0.85`, результат помечается `needs_confirmation=true`.

### 3.3 DocxToPdfConverter

`convert_to_pdf(docx_bytes) -> pdf_bytes`

Backend вызывает HTTP endpoint converter-сервиса `POST /convert`.
Конфиг через env:
- `DOCUMENTS_CONVERTER_ENABLED`
- `DOCUMENTS_CONVERTER_URL` (по умолчанию `http://libreoffice:3000` внутри docker-сети)
- `DOCUMENTS_CONVERTER_TIMEOUT_SECONDS`

## 4. API

### CRUD шаблонов
- `GET /api/document-templates`
- `POST /api/document-templates`
- `PATCH /api/document-templates/{id}`
- `DELETE /api/document-templates/{id}`

### Заполнение
- `POST /api/document-templates/{id}/fill`

Request:
- `values: { [key: string]: string }`

Response:
- `files: [{ filename, content_type, content_base64 }]`
- В зависимости от `output_settings.format` возвращается один или два файла.

## 5. Frontend

Добавлена вкладка `Шаблоны`:
- список шаблонов,
- создание карточки,
- удаление,
- запуск fill,
- скачивание сгенерированных DOCX/PDF.

В чате добавено отображение file attachments (download buttons) для ответов с generated files.

Команда для быстрого шаблонного fill в чате:
- `/template-fill <template_id> {"field":"value"}`

## 5.1 Chat flow (NLU + slot filling)

Backend `ChatService` поддерживает flow:
- интент вида «заполни шаблон ...»;
- извлечение начальных значений полей через LLM;
- запрос недостающих required полей по одному;
- для `vin`/`passport_number` можно прислать фото;
- при `confidence < 0.85` обязательный шаг подтверждения (`Верно?`) перед записью в шаблон;
- после заполнения в ответ ассистента возвращаются attachment markers с DOCX/PDF, которые frontend рендерит как кнопки скачивания.

## 6. Ограничения и безопасность

- В коде нет hardcoded machine-specific путей для шаблонов.
- `file_id` трактуется как внешний идентификатор/ключ шаблона в storage provider.
- Никакие секреты не логируются.
- Для VIN/паспорта используется обязательная валидация результата перед использованием.

## 7. Тесты

Покрытие добавлено для:
- `DocumentFillService` (подстановка в body/table/header/footer),
- `VisionService` (валидация VIN/паспорт + low-confidence),
- `DocxToPdfConverter` (HTTP converter mock),
- API E2E (`create -> fill -> 2 files`).
