FROM python:3.12-slim@sha256:f77ac9e44ae96ef2c90b8053ea08c31f8be030f824196b0ae4db6d462c84e51f

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY ai-agent/pyproject.toml ./pyproject.toml
COPY ai-agent/requirements.lock ./requirements.lock
COPY ai-agent/app ./app

RUN python -m pip install --no-cache-dir --upgrade "pip==26.3" \
    && python -m pip install --no-cache-dir -r requirements.lock \
    && python -m pip install --no-cache-dir --no-deps --no-build-isolation .

EXPOSE 8001

CMD ["uvicorn", "app.gold_runtime:create_gold_app", "--factory", "--host", "0.0.0.0", "--port", "8001"]
