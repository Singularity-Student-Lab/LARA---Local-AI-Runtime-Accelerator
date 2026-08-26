# lara-telemetry reuses the gateway's app package (app.db, app.modes.pressure, app.config)
# rather than duplicating the schema or the NVML sampling logic - one source of truth for
# both the live pressure evaluator (Phase F, in-process) and this durable collector (Phase H).
FROM python:3.12-slim

WORKDIR /app

COPY gateway/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY gateway/app /app/app
COPY monitoring/collector /app/monitoring/collector
RUN touch /app/monitoring/__init__.py

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "monitoring.collector.main"]
