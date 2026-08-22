FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AUDITOR_HOST=0.0.0.0 \
    AUDITOR_ALLOW_TRANSIENT_PROVIDER_CONFIG=false

WORKDIR /app
COPY pyproject.toml README.md ./
COPY auditor ./auditor

RUN pip install --no-cache-dir .

EXPOSE 8000
CMD ["auditor-web"]
