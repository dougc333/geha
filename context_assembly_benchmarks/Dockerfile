# syntax=docker/dockerfile:1

FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/opt/huggingface \
    HF_HUB_DISABLE_TELEMETRY=1 \
    PORT=8507

WORKDIR /app

RUN apt-get update \
    && apt-get install --no-install-recommends -y libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Keep dependency and model downloads in reusable image layers.
COPY context_assembly_benchmarks/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir \
        --index-url https://download.pytorch.org/whl/cpu \
        torch torchvision \
    && pip install --no-cache-dir -r /tmp/requirements.txt
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-en-v1.5')"

COPY context_assembly_benchmarks /app/context_assembly_benchmarks
COPY crawl_dir/verified/coverage-policies /app/crawl_dir/verified/coverage-policies

RUN useradd --create-home --uid 10001 contextbench \
    && chown -R contextbench:contextbench /app /opt/huggingface
USER contextbench

EXPOSE 8507

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8507') + '/_stcore/health', timeout=3)" || exit 1

CMD ["sh", "-c", "exec python -m streamlit run context_assembly_benchmarks/comparison_chat_app.py --server.address=0.0.0.0 --server.port=${PORT}"]
