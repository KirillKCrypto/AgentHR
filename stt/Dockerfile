FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 HF_HOME=/models TORCH_HOME=/models/torch

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

# Только CPU-сборка torch: CUDA-колёса весят десятки гигабайт и не нужны.
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch torchaudio

# GigaAM ставится из официального репозитория; torch уже установлен CPU-версией.
RUN git clone --depth 1 https://github.com/salute-developers/GigaAM.git /opt/GigaAM \
    && cd /opt/GigaAM \
    && pip install -e ".[torch]"

COPY app.py .

EXPOSE 9000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "9000"]
