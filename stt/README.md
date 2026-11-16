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

### Диск и загрузка модели

- В образ ставится CPU-сборка torch, без CUDA/NVIDIA.
- Вес модели не входит в образ: при первом старте она скачивается в volume `stt_models`
  (`HF_HOME=/models`).
- Ориентировочно: образ 1.5–2.5 ГБ + модель 1–2 ГБ. Повторный запуск модель не скачивает.
- Удалить модель и освободить место: `docker volume rm agenthr_stt_models`.
- Для меньшего размера можно указать `GIGAAM_MODEL=v2_ctc` в `infra/.env`.
- Вместо локальной модели можно указать внешний STT-сервис в `STT_BASE_URL`; он должен
  принимать `POST /transcribe` с полем `file` и возвращать `{text, duration_ms, confidence}`.

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
