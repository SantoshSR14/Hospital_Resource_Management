FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY environment.py .
COPY graders.py .
COPY server.py .
COPY inference.py .
COPY openenv.yaml .

RUN mkdir -p /app/logs

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

ENV PYTHONUNBUFFERED=1
ENV API_BASE_URL=http://localhost:8000
ENV MODEL_NAME=gpt-4
# HF_TOKEN and LOCAL_IMAGE_NAME have NO defaults — set them as HF Secrets

CMD ["python", "-m", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
