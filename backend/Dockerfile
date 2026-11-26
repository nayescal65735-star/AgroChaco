# syntax=docker/dockerfile:1

FROM python:3.12-slim-bookworm AS motor-builder

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        cmake \
        libopenmpi-dev \
        openmpi-bin \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /tmp/motor-src
COPY motor/ /tmp/motor-src/

RUN cmake -S /tmp/motor-src -B /tmp/motor-build \
    && cmake --build /tmp/motor-build --parallel "$(nproc)" \
    && test -x /tmp/motor-src/bin/agrochaco_secuencial \
    && test -x /tmp/motor-src/bin/agrochaco_openmp \
    && test -x /tmp/motor-src/bin/agrochaco_mpi \
    && test -x /tmp/motor-src/bin/agrochaco_hibrido \
    && test -x /tmp/motor-src/bin/test_motor


FROM python:3.12-slim-bookworm AS runtime

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libgomp1 \
        libopenmpi3 \
        openmpi-bin \
        libstdc++6 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
    && rm -f /tmp/requirements.txt

RUN groupadd --gid 10001 agrochaco \
    && useradd --uid 10001 --gid agrochaco --create-home --shell /usr/sbin/nologin agrochaco

WORKDIR /app

ENV PYTHONPATH=/app/backend \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY backend/ /app/backend/
COPY --from=motor-builder /tmp/motor-src/bin/ /app/motor/bin/
COPY motor/config/ /app/motor/config/

RUN mkdir -p /app/results/simulations \
    && chown -R agrochaco:agrochaco /app

USER agrochaco

EXPOSE 8001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
