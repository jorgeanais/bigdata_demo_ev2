# syntax=docker/dockerfile:1
FROM python:3.11-slim

# pandas/pyarrow instalan más rápido y liviano si evitamos capas de compilación innecesarias
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Instala dependencias primero para aprovechar el cache de capas de Docker
COPY docker/requirements-collector.txt ./requirements-collector.txt
RUN pip install --no-cache-dir -r requirements-collector.txt

# Copia sólo el script que necesitamos (no todo el repo)
COPY resources/bus_data_collector.py ./bus_data_collector.py

# Usuario sin privilegios (buena práctica para un servicio de larga duración)
RUN useradd --create-home --uid 1000 collector \
    && mkdir -p /app/data \
    && chown -R collector:collector /app
USER collector

ENV OUTPUT_DIR=/app/data

VOLUME ["/app/data"]

CMD ["python", "bus_data_collector.py"]
