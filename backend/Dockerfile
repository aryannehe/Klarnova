FROM python:3.13-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    KUBE_IN_CLUSTER=true \
    CHROMA_PERSIST_DIR=/data/chroma

# Set to true to pull in the RAG embedding stack (torch / sentence-transformers /
# chromadb) -- adds several GB and minutes to the build.
ARG INSTALL_ML=false

COPY backend/requirements.txt /app/requirements.txt
COPY backend/requirements-ml.txt /app/requirements-ml.txt
RUN pip install --no-cache-dir -r /app/requirements.txt \
    && if [ "$INSTALL_ML" = "true" ]; then pip install --no-cache-dir -r /app/requirements-ml.txt; fi

COPY backend/app /app/app
COPY knowledge-base /app/knowledge-base

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
