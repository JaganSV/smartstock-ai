FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN useradd --create-home --uid 10001 appuser

WORKDIR /app

# Dependency layer first (cached unless requirements.lock changes).
COPY requirements.lock ./
RUN pip install -r requirements.lock

# Application code (.env is excluded via .dockerignore).
COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY data ./data
RUN chown -R appuser:appuser /app

USER appuser
EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
