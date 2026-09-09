FROM python:3.12-slim AS runtime
RUN apt-get update && apt-get dist-upgrade -y && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir "."
RUN python -m pip install --no-cache-dir --upgrade "setuptools>=78.1.1" "msgpack>=1.2.1"

COPY alembic.ini ./
COPY alembic ./alembic
RUN chown -R app:app /app

USER app
EXPOSE 8000

CMD ["uvicorn", "mail_control.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
