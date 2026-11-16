# AgentHR STT (GigaAM)

Отдельный сервис распознавания русской речи для голосового ввода ответов.

## Запуск

```powershell
cd infra
# один раз: включить адрес STT в .env
# STT_BASE_URL=http://stt:9000
docker compose --profile voice up -d --build
```

Первый запуск долгий: скачиваются torch и модель GigaAM. Аудио не сохраняется.

## API

- `GET /health`
- `POST /transcribe` — `multipart/form-data`, поле `file`

Ответ:

```json
{"text": "...", "duration_ms": 12000, "confidence": null}
```

## Ограничения

- Модель работает на CPU; распознавание длинного ответа может занимать время.
- Входное аудио режется на сегменты по 20 секунд, потому что `GigaAM.transcribe()`
  рассчитан на короткие фрагменты.
- `ffmpeg` и `ffprobe` обязательны.
- `GIGAAM_MODEL` по умолчанию `v3_e2e_ctc`.
- Для локальной проверки без модели: `GIGAAM_MOCK=1`.
