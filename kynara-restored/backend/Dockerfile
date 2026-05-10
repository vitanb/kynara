FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PYTHONPATH=/app
WORKDIR /app

# xmlsec deps for python3-saml
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libxml2-dev libxmlsec1-dev libxmlsec1-openssl pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Copy source first so pip install -e . can see the package
COPY . .
RUN pip install --upgrade pip && pip install -e .

# Non-root runtime
RUN useradd -m kynara && chown -R kynara /app
RUN chmod +x /app/entrypoint.sh
USER kynara

EXPOSE 8000
CMD ["/app/entrypoint.sh"]
