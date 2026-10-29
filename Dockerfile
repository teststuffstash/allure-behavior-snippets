FROM python:3.15-alpine AS base

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

# The process artifact — a `FROM scratch` image whose root filesystem is exactly the pinned
# process text: /process/{RULES.md,CONVENTIONS.md,briefs/*.md} + /process/VERSION. Built for a
# Kubernetes image volume (pod.spec.volumes[].image, mounted read-only), so a worker pod reads the
# pinned process as files instead of digging it out of the venv. Published by docker-publish.yml
# (job `process`) as ghcr.io/teststuffstash/allure-behavior-snippets-process:<tag>, which also
# diffs the rootfs listing against allure_behavior_snippets/process/ so no file is left out.
FROM base AS process-src

COPY pyproject.toml ./
COPY allure_behavior_snippets/process/ /out/process/
# VERSION is derived from the one pyproject version (== __version__ by tests/test_process_docs.py,
# == the pushed tag by the workflow's check) — never a second hand-maintained copy.
RUN python -c 'import tomllib; print(tomllib.load(open("pyproject.toml", "rb"))["tool"]["poetry"]["version"])' \
    > /out/process/VERSION

FROM scratch AS process

COPY --from=process-src /out/process/ /process/

# `final` stays the LAST stage: it is the default target of `docker build .` and compose `build: .`.
FROM base AS final

COPY --from=builder /venv /venv
COPY docker-entrypoint.sh ./
RUN chmod +x docker-entrypoint.sh
ENTRYPOINT ["./docker-entrypoint.sh"]
