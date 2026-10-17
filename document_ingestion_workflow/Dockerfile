# syntax=docker/dockerfile:1

FROM node:22-bookworm-slim AS ui-builder

WORKDIR /build/ui
COPY document_ingestion_workflow/ui/package.json document_ingestion_workflow/ui/package-lock.json ./
RUN npm ci
COPY document_ingestion_workflow/ui/ ./
RUN npm run build


FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    HOST=0.0.0.0 \
    PORT=8510

WORKDIR /app

COPY document_ingestion_workflow/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir \
        --index-url https://download.pytorch.org/whl/cpu \
        "torch==2.14.1+cpu" \
        "torchvision==0.29.1+cpu" \
    && pip install --no-cache-dir -r /tmp/requirements.txt \
    && python -m playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/*

COPY document_ingestion_workflow /app/document_ingestion_workflow
COPY --from=ui-builder /build/ui/dist /app/document_ingestion_workflow/ui/dist
COPY crawl_dir/src /app/crawl_dir/src
COPY crawl_dir/raw/coverage-policies /app/crawl_dir/raw/coverage-policies
COPY crawl_dir/raw/forms /app/crawl_dir/raw/forms
COPY crawl_dir/raw/research/ey-limra-workforce-benefits-study-final-2025.pdf /app/crawl_dir/raw/research/ey-limra-workforce-benefits-study-final-2025.pdf
COPY crawl_dir/annotations/research/ey-limra-workforce-benefits-study-final-2025/figure-specs /app/crawl_dir/annotations/research/ey-limra-workforce-benefits-study-final-2025/figure-specs
COPY PDF_processing/bill_lading /app/PDF_processing/bill_lading

RUN mkdir -p /app/crawl_dir/runs \
    && useradd --create-home --uid 10001 ingestion \
    && chown -R ingestion:ingestion /app /ms-playwright

USER ingestion

EXPOSE 8510

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8510') + '/api/health', timeout=3)" || exit 1

CMD ["python", "-m", "document_ingestion_workflow.backend"]
