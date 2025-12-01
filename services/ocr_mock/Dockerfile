FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml README.md /app/
COPY services /app/services
RUN pip install --no-cache-dir fastapi uvicorn

CMD ["uvicorn", "services.ocr_mock.main:app", "--host", "0.0.0.0", "--port", "8081"]

