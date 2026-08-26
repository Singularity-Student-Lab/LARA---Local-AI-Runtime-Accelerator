FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY gateway/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY gateway/app /app/app
COPY database /app/database
COPY alembic.ini /app/alembic.ini
COPY inference/configs /app/inference/configs

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 8080

# --workers 1 is not a default, it's a correctness requirement: the scheduler's admission
# semaphore is in-process state. Multiple workers would each hold their own semaphore and
# silently multiply the GPU concurrency ceiling (blueprint section 4, Session 4).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
