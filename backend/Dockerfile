FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY pyproject.toml alembic.ini ./
COPY alembic ./alembic
COPY app ./app

# Editable install so the docker-compose.dev.yml bind mounts of ./app are the
# code that actually runs; in the plain image it behaves like a normal install.
RUN pip install --no-cache-dir -e .

EXPOSE 8000

# §9.1: run migrations, then serve.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
