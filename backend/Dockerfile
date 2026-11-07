FROM dhi.io/python:3.12-alpine3.24-dev@sha256:e019a291b90b9cb0572f6f6a0d2e7ee0e3fd9a3dfbd0da8246c9c9f6c6800af5

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1

ENV PYTHONUNBUFFERED=1

COPY backend/requirements.lock ./
RUN python -m pip install --no-cache-dir --upgrade "pip==26.2.2" \
    && python -m pip install --no-cache-dir -r requirements.lock

COPY backend/ .
COPY docs/contracts/examples/gold-publication-v1.json /docs/contracts/examples/gold-publication-v1.json
COPY docs/contracts/examples/genai-plan-fingerprints-v1.json /docs/contracts/examples/genai-plan-fingerprints-v1.json
COPY docs/contracts/examples/genai-internal-contract-v1.json /docs/contracts/examples/genai-internal-contract-v1.json
COPY docs/contracts/examples/text-to-sql-f1-v1.json /docs/contracts/examples/text-to-sql-f1-v1.json
<<<<<<< HEAD
COPY docs/contracts/examples/text-to-sql-f1-http-v1.json /docs/contracts/examples/text-to-sql-f1-http-v1.json
=======
>>>>>>> ce78c544 (feat(genai): instrumenta operação e alertas da F1)
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
