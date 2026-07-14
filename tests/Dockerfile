#playwright is not supported on alpine, so tests run on the playwright ubuntu image
FROM python:3.13-alpine AS exporter

ENV POETRY_VERSION=2.2.1

WORKDIR /app

RUN pip install "poetry==$POETRY_VERSION" poetry-plugin-export

COPY pyproject.toml poetry.lock ./
RUN poetry export -f requirements.txt --with=dev > requirements.txt

# Tag must match the exact playwright pin in pyproject.toml — the browsers
# baked into this image only work with the same playwright package version.
FROM mcr.microsoft.com/playwright/python:v1.61.0-noble

ENV TZ=UTC
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

WORKDIR /app
COPY --from=exporter /app/requirements.txt ./
RUN python3 -m venv /venv && /venv/bin/pip install -r requirements.txt

COPY allure_behavior_snippets ./allure_behavior_snippets
COPY tests ./tests
RUN chmod +x tests/docker-entrypoint.sh

WORKDIR /app/tests
ENTRYPOINT ["./docker-entrypoint.sh"]
