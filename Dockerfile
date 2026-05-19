# ── builder ──────────────────────────────────────────────────────────────────
FROM python:3.10-alpine AS builder

RUN apk add --no-cache gcc musl-dev libffi-dev openssl-dev postgresql-dev

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── runtime ───────────────────────────────────────────────────────────────────
FROM python:3.10-alpine

RUN apk add --no-cache libpq libffi openssl

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
COPY --from=builder /install /usr/local
COPY . .

CMD ["python", "bot.py"]
