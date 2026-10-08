FROM mcr.microsoft.com/playwright/python:v1.55.0-noble

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app
COPY requirements.txt constraints.txt ./
# Docling depends on PyTorch. Install the CPU wheel explicitly so pip does not
# pull several gigabytes of CUDA libraries into this CPU-only Fargate image.
RUN pip install --no-cache-dir \
      --extra-index-url https://download.pytorch.org/whl/cpu \
      --constraint constraints.txt \
      -r requirements.txt
COPY pdf_worker.py build_validated_sidecar.py cloud_main.py ./

USER pwuser
ENTRYPOINT ["python", "/app/cloud_main.py"]
