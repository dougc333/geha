# syntax=docker/dockerfile:1

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/opt/huggingface \
    HF_HUB_DISABLE_TELEMETRY=1 \
    PORT=8506 \
    DENTAL_WARM_RETRIEVER=1

RUN apt-get update \
    && apt-get install --no-install-recommends -y libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies and download BGE while these slow layers can still be
# reused after ordinary application-code edits.
COPY dspy_dental_chatbot/requirements.txt /tmp/dental-requirements.txt
RUN pip install --no-cache-dir \
        --index-url https://download.pytorch.org/whl/cpu \
        "torch==2.14.1+cpu" \
        "torchvision==0.29.1+cpu" \
    && pip install --no-cache-dir -r /tmp/dental-requirements.txt
RUN python -c "import dspy, torch, torchvision; from transformers import AutoModel"
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-large-en-v1.5')"

# The chatbot intentionally reuses the repository's canonical corpus search,
# ingestion paths, dental PDFs, and visually validated page Markdown.
COPY dspy_dental_chatbot /app/dspy_dental_chatbot
COPY agentic_search_corpus/src /app/agentic_search_corpus/src
COPY crawl_dir/src /app/crawl_dir/src
COPY crawl_dir/raw/dental /app/crawl_dir/raw/dental
COPY crawl_dir/runs/dental /app/crawl_dir/runs/dental

ENV PYTHONPATH=/app/dspy_dental_chatbot/src

# Build both vector caches into the image. Runtime uses local_files_only=True,
# so a deployed container never needs Hugging Face network access.
RUN mkdir -p /app/agentic_search_corpus/indexes \
    && python -c "from corpus_retriever import ExistingDentalCorpusRetriever; [ExistingDentalCorpusRetriever(include_plan_brochure=include).warm_vectors() for include in (False, True)]"

RUN useradd --create-home --uid 10001 dental \
    && chown -R dental:dental /app /opt/huggingface
USER dental

EXPOSE 8506

HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8506') + '/_stcore/health', timeout=3)" || exit 1

CMD ["sh", "-c", "exec python -m streamlit run dspy_dental_chatbot/src/app.py --server.address=0.0.0.0 --server.port=${PORT}"]
