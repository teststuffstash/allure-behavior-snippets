#playwright is not supported on alpine
FROM python:3.11.5-alpine3.18 as base

ENV PYTHONFAULTHANDLER=1 \
    PYTHONHASHSEED=random \
    PYTHONUNBUFFERED=1

WORKDIR /app

FROM base as builder

ENV PIP_DEFAULT_TIMEOUT=100 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VERSION=1.6.1

RUN pip install "poetry==$POETRY_VERSION"
RUN python -m venv /venv

COPY pyproject.toml poetry.lock ./
RUN poetry export -f requirements.txt --with=dev > requirements.txt


FROM mcr.microsoft.com/playwright/python:v1.38.0-jammy

ENV TZ=UTC
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

RUN apt update && \
    apt install -y software-properties-common gpg-agent && \
    add-apt-repository --yes ppa:deadsnakes/ppa && \
    apt install -y python3.11 python3.11-venv && \
    python3.11 -m ensurepip

WORKDIR /app
COPY --from=builder /app/requirements.txt ./
RUN python3.11 -m pip install -r requirements.txt

COPY allure_behavior_snippets ./allure_behavior_snippets
COPY tests ./tests
RUN chmod +x tests/docker-entrypoint.sh

WORKDIR /app/tests
ENTRYPOINT ["./docker-entrypoint.sh"]
