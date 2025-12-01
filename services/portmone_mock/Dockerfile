FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml poetry.lock* /app/
RUN pip install --no-cache-dir poetry && poetry config virtualenvs.create false && poetry install --only main

COPY . /app

ENV PORT=8082
EXPOSE 8082

CMD ["uvicorn", "services.portmone_mock.main:app", "--host", "0.0.0.0", "--port", "8082"]

