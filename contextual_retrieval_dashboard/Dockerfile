# syntax=docker/dockerfile:1

FROM node:22-bookworm-slim AS ui-builder

WORKDIR /build/ui
COPY contextual_retrieval_dashboard/ui/package.json contextual_retrieval_dashboard/ui/package-lock.json ./
RUN npm ci
COPY contextual_retrieval_dashboard/ui/ ./
RUN npm run build


FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HOST=0.0.0.0 \
    PORT=8511 \
    HF_HOME=/home/dashboard/.cache/huggingface

WORKDIR /app

COPY contextual_retrieval_dashboard/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir \
        --index-url https://download.pytorch.org/whl/cpu \
        "torch==2.14.1+cpu" \
        "torchvision==0.29.1+cpu" \
    && pip install --no-cache-dir -r /tmp/requirements.txt

COPY contextual_retrieval_dashboard /app/contextual_retrieval_dashboard
COPY --from=ui-builder /build/ui/dist /app/contextual_retrieval_dashboard/ui/dist
COPY crawl_dir/src /app/crawl_dir/src

RUN mkdir -p /app/crawl_dir/raw/coverage-policies \
        /app/crawl_dir/runs \
        /app/crawl_dir/cache \
        /home/dashboard/.cache/huggingface \
    && useradd --create-home --uid 10001 dashboard \
    && chown -R dashboard:dashboard /app /home/dashboard

USER dashboard

# Cache the chunker's tokenizer/model in the image so a normal container start
# does not pause for a first-use Hugging Face download.
RUN python -c "from docling_core.transforms.chunker.tokenizer.huggingface import HuggingFaceTokenizer; HuggingFaceTokenizer.from_pretrained(model_name='BAAI/bge-small-en-v1.5', max_tokens=380)"

EXPOSE 8511

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8511') + '/api/health', timeout=3)" || exit 1

CMD ["python", "-m", "contextual_retrieval_dashboard.backend"]
