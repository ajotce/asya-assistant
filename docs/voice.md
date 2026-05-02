# Voice

Документ описывает голосовой слой Asya v0.4: push-to-talk в вебе и голосовые сообщения в Telegram.

## 1. Архитектура

```
Frontend (web)                          Telegram Bot
  MediaRecorder --> POST /api/voice/stt    voice msg --> download --> POST /api/voice/stt
  транскрипт --> ChatPage.sendMessage()    транскрипт --> ChatService.stream_chat()
  ответ Asya --> TTS (если включено)       ответ Asya --> voice reply (если включено)
```

Backend слой:

```
app/voice/
  providers.py   — абстракции (SpeechToTextProvider, TextToSpeechProvider) + реализации
  service.py     — VoiceService (transcribe, synthesize) + валидация лимитов

app/api/routes_voice.py  — HTTP API: /api/voice/stt, /api/voice/tts, /api/voice/settings
app/services/user_voice_settings_service.py  — per-user настройки голоса
app/db/models/user_voice_settings.py         — модель UserVoiceSettings

app/integrations/telegram/bot_app.py  — voice message handler в Telegram-боте
```

## 2. Поддерживаемые провайдеры

| Провайдер         | STT | TTS | Требует                                    |
|-------------------|-----|-----|--------------------------------------------|
| mock              | ✓   | ✓   | Ничего (для тестов и dev)                  |
| yandex_speechkit  | ✓   | ✓   | `YANDEX_SPEECHKIT_API_KEY`, `FOLDER_ID`    |
| gigachat          | ✓   | ✓   | `GIGACHAT_API_KEY`                        |

Mock-провайдер возвращает `[mock transcript]` для STT и синтетический WAV для TTS.

## 3. Настройки голоса пользователя

`UserVoiceSettings` (per user_id):

| Поле            | Тип          | По умолчанию         |
|------------------|--------------|----------------------|
| assistant_name   | str(120)     | имя пользователя     |
| voice_gender     | enum         | female               |
| stt_provider     | enum         | mock                 |
| tts_provider     | enum         | mock                 |
| tts_enabled      | bool         | false                |

API:

- `GET  /api/voice/settings` — получить текущие настройки
- `PUT  /api/voice/settings` — обновить настройки

### 3.1. Обновление настроек

```json
{
  "assistant_name": "Asya",
  "voice_gender": "female",
  "stt_provider": "yandex_speechkit",
  "tts_provider": "yandex_speechkit",
  "tts_enabled": true
}
```

## 4. Speech-to-Text

`POST /api/voice/stt`

- Content-Type: `audio/webm` (или другой поддерживаемый mime-тип)
- Body: сырые аудио-байты
- Лимит: 15 MB (`VOICE_MAX_AUDIO_BYTES`, настраивается в `.env`)
- Авторизация: требуется (cookie)

Ответ (200):

```json
{
  "text": "распознанный текст",
  "provider": "yandex_speechkit"
}
```

Ошибки:
- 400 — аудио пустое или превышает лимит
- 400 — ошибка провайдера (детали в detail)
- 401 — требуется авторизация

### 4.1. Ограничения безопасности

- Аудио не пишется в логи (ни содержимое, ни размер выше порога)
- Транскрипт не логируется в production
- Лимит размера проверяется до передачи провайдеру

## 5. Text-to-Speech

`POST /api/voice/tts`

```json
{
  "text": "текст для озвучивания (до 12000 символов)"
}
```

Ответ (200): аудио-файл (Content-Type зависит от провайдера: `audio/mpeg`, `audio/wav`)

## 6. Push-to-talk в веб-интерфейсе

### 6.1. Компонент

`frontend/src/hooks/useVoiceRecorder.ts` — React-хук:

- `isSupported` — доступен ли MediaRecorder API
- `isRecording` — идёт ли запись
- `start()` / `stop()` → Blob | null
- MIME: audio/webm

### 6.2. Поток

1. Пользователь нажимает кнопку «Микрофон» в ChatPage
2. Начинается запись (браузер запрашивает доступ к микрофону)
3. Пользователь нажимает «Стоп» (кнопка пульсирует красным во время записи)
4. Аудио отправляется на `POST /api/voice/stt`
5. Транскрипт вставляется в чат как сообщение пользователя
6. Asya генерирует ответ через стандартный поток streamChat
7. Если `tts_enabled = true` — ответ озвучивается через `/api/voice/tts` и проигрывается в браузере

### 6.3. Не ломает текстовый чат

- Текстовый ввод и отправка работают как раньше
- Voice-транскрипт не виден на UI до отправки
- TTS проигрывается только при включённой настройке, best-effort (ошибки не прерывают чат)

## 7. Голос в Telegram

### 7.1. Обработка voice-сообщений

`handle_voice_message` в `bot_app.py`:

1. Получает voice message от пользователя
2. Проверяет привязку аккаунта через `TelegramAccountLinkRepository`
3. Скачивает аудио-файл с серверов Telegram
4. Отправляет на `VoiceService.transcribe()`
5. Результат отправляет в `ChatService.stream_chat()` 
6. Если `tts_enabled` — синтезирует и отправляет voice-ответ

### 7.2. Меню (/menu)

Inline-клавиатура с кнопками:
- Задачи, Календарь, Дневник
- Список пространств пользователя
- `Asya-dev` не показывается обычным пользователям (фильтрация по `is_admin_only`)
