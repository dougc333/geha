FROM node:22-bookworm-slim AS ui
WORKDIR /build
COPY ui/package*.json ./
RUN npm ci
COPY ui/ ./
RUN npm run build

FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOST=0.0.0.0 PORT=8520
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir 'aiohttp>=3.13,<4' 'pymupdf>=1.28,<2' 'requests>=2.32,<3' 'beautifulsoup4>=4.14,<5'
COPY batch_app /app/batch_app
COPY catalog.json /app/catalog.json
COPY document_ingestion_workflow /app/document_ingestion_workflow
COPY crawl_dir/src /app/crawl_dir/src
COPY geha_processing /app/geha_processing
COPY bounding_box /app/bounding_box
COPY PDF_processing /app/PDF_processing
COPY --from=ui /build/dist /app/ui/dist
RUN mkdir -p /app/crawl_dir/raw /app/runs
EXPOSE 8520
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8520/api/health',timeout=3)" || exit 1
CMD ["python", "-m", "batch_app.backend"]
