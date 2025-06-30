FROM python:3.11-bookworm AS test
WORKDIR /home/vcap/app
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        redis \
    && rm -rf /var/lib/apt/lists/*
COPY . .
RUN make bootstrap
