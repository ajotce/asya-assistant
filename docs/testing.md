# Testing

## Доступные проверки на текущем этапе

### Backend
```bash
cd backend
python3 -m pytest -q
```

### Frontend
```bash
cd frontend
npm run build
```

## Что проверяем
- Базовая структура проекта присутствует.
- Конфигурационные файлы заполнены без секретов.
- Сборка frontend выполняется.
- Backend-тесты проходят (если окружение готово).
