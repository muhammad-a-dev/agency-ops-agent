# Lightweight image for the agency-ops-agent FastAPI demo.
# Default mode is offline-safe (no LLM keys required).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AGENCY_OPS_AGENT_LLM_ENABLED=false \
    AGENCY_OPS_WORKSPACE_DIR=/app/workspace \
    AGENCY_OPS_LOG_LEVEL=INFO

WORKDIR /app

# Install package first for better layer caching.
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/workspace \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"

CMD ["uvicorn", "agency_ops_agent.api:app", "--host", "0.0.0.0", "--port", "8000"]
