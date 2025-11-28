# Stage 1: Build (pip global pour accessibilité non-root)
FROM python:3.12-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt  # Global, pas --user

# Stage 2: Runtime (non-root sécurisé)
FROM python:3.12-slim
# Crée user/group non-root (aligné avec securityContext UID 1000)
RUN groupadd -r -g 1000 appuser && useradd -r -u 1000 -g appuser appuser \
    && mkdir -p /app && chown -R appuser:appuser /app
WORKDIR /app

# Copie bins et libs globales (pas /root/.local)
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY . .
# Chown pour non-root (essentiel pour exécution uvicorn)
RUN chown -R appuser:appuser /app /usr/local

# Switch to non-root avant CMD
USER appuser
ENV PYTHONPATH=/app
EXPOSE ${PORT:-8002}
CMD sh -c "uvicorn main:app --host 0.0.0.0 --port \${PORT:-8002}"