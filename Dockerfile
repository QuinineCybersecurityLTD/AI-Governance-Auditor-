FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY aigov ./aigov
COPY examples ./examples

RUN pip install --no-cache-dir ".[api]"

# stateless service: no volumes, no persisted system data
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s \
  CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/health')"

CMD ["uvicorn", "aigov.api:app", "--host", "0.0.0.0", "--port", "8000"]
