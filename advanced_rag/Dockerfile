FROM node:22-bookworm-slim AS web-build

WORKDIR /build/web
COPY advanced_rag/web/package.json advanced_rag/web/package-lock.json ./
RUN npm ci
COPY advanced_rag/web/ ./
RUN npm run build


FROM python:3.12-slim-bookworm AS app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app:/app/src \
    AWS_WORKFLOW_DATA_DIR=/app/runtime

RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        libgl1 \
        libglib2.0-0 \
        libgomp1 \
        poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY advanced_rag/requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY geha_processing/ ./geha_processing/
COPY advanced_rag/src/ ./src/
COPY advanced_rag/evals/ ./evals/
COPY advanced_rag/state_machines/ ./state_machines/
COPY --from=web-build /build/web/dist ./web/dist

RUN mkdir -p /app/runtime

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/documents', timeout=3)" || exit 1

CMD ["python", "-m", "aws_data_workflow.server"]
