FROM python:3.12-slim AS base
WORKDIR /app

RUN pip install poetry && \
    poetry config virtualenvs.create false

COPY workers/scraper/pyproject.toml workers/scraper/poetry.lock* ./
RUN poetry install --no-interaction --no-ansi --no-root

RUN playwright install chromium && \
    playwright install-deps chromium

COPY workers/scraper/src ./src

CMD ["python", "-m", "src.scheduler"]
