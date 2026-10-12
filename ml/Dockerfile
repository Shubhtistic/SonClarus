FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app/src \
    HOME=/home/mlworker

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    ffmpeg \
    git \
    libgomp1 \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 10001 mlworker && \
    useradd --uid 10001 --gid mlworker --create-home --shell /usr/sbin/nologin mlworker

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN python -m pip install --no-cache-dir -r requirements.txt
RUN python -m pip check && python -c "import aioboto3, aiokafka, df.enhance, faster_whisper, speechbrain, torch, torchaudio; from google import genai; print('ML dependency imports passed')"

COPY src ./src
COPY start_consumers.py ./start_consumers.py

RUN mkdir -p /models && chown mlworker:mlworker /models

USER mlworker

CMD ["python", "start_consumers.py"]
