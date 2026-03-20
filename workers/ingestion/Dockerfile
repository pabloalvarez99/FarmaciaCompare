FROM python:3.12-slim AS base
WORKDIR /app

RUN pip install poetry && \
    poetry config virtualenvs.create false

COPY workers/ingestion/pyproject.toml workers/ingestion/poetry.lock* ./
RUN poetry install --no-interaction --no-ansi --no-root

COPY workers/ingestion/src ./src

CMD ["python", "-m", "src.es_indexer"]
