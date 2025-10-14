FROM python:3.13-bookworm AS test

COPY --from=ghcr.io/astral-sh/uv:0.5.30 /uv /uvx /bin/

ENV UV_CACHE_DIR='/tmp/uv-cache/'
ENV VIRTUAL_ENV="/opt/venv"

WORKDIR /home/vcap/app
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        redis \
    && rm -rf /var/lib/apt/lists/*
COPY . .
RUN make bootstrap
