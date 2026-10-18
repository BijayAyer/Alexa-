FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
COPY src ./src

RUN pip install --no-cache-dir uv \
    && uv sync --frozen --no-dev

ENV CRAM_DB_PATH=/data/cram.db
RUN mkdir -p /data
VOLUME ["/data"]

EXPOSE 8000
CMD ["uv", "run", "--frozen", "--no-dev", "cram-server"]