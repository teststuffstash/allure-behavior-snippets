FROM python:3.13-alpine AS base

ENV PYTHONFAULTHANDLER=1 \
    PYTHONHASHSEED=random \
    PYTHONUNBUFFERED=1

WORKDIR /app

FROM base AS builder

ENV PIP_DEFAULT_TIMEOUT=100 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# Runtime deps are pure python (svgwrite only) — no toolchain, no poetry needed;
# pip builds the wheel via the poetry-core backend.
RUN python -m venv /venv

COPY . .
RUN /venv/bin/pip install .

FROM base AS final

COPY --from=builder /venv /venv
COPY docker-entrypoint.sh ./
RUN chmod +x docker-entrypoint.sh
ENTRYPOINT ["./docker-entrypoint.sh"]
