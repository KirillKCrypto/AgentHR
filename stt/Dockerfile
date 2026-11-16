FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg git build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

# GigaAM ставится из официального репозитория вместе с torch.
RUN git clone --depth 1 https://github.com/salute-developers/GigaAM.git /opt/GigaAM \
    && cd /opt/GigaAM \
    && pip install -e ".[torch]"

COPY app.py .

EXPOSE 9000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "9000"]
