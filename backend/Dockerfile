# ─────────────────────────────────────────────
#  Stage 1 — Builder
# ─────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev libffi-dev libssl-dev poppler-utils tesseract-ocr \
    tesseract-ocr-fra tesseract-ocr-eng libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --prefix=/install --no-cache-dir -r requirements.txt

# ─────────────────────────────────────────────
#  Stage 2 — Production
# ─────────────────────────────────────────────
FROM python:3.12-slim AS production

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 poppler-utils tesseract-ocr tesseract-ocr-fra tesseract-ocr-eng libgomp1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Non-root user
RUN groupadd -r jmj && useradd -r -g jmj -d /app -s /sbin/nologin jmj

WORKDIR /app

COPY --from=builder /install /usr/local
COPY . .

RUN mkdir -p /app/storage/documents /app/storage/signatures \
             /app/storage/stamps /app/storage/scans /app/storage/assets && \
    chmod +x /app/start.sh && \
    chown -R jmj:jmj /app

USER jmj

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["/app/start.sh"]
