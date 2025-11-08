FROM python:3.11-slim
LABEL maintainer="subchak.maksym@gmail.com"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=off \
    POETRY_VIRTUALENVS_CREATE=false

RUN apt update && apt install -y gcc curl && rm -rf /var/lib/apt/lists/*

RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="/root/.local/bin:$PATH"

WORKDIR /usr/app
COPY pyproject.toml poetry.lock ./
RUN poetry install --no-root
RUN poetry run pip install pytest flake8

COPY . .

EXPOSE 8000

RUN mkdir -p /usr/app/database/source

CMD ["bash", "-c", "poetry run alembic upgrade head && poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000"]
