FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OMP_NUM_THREADS=4 \
    OPENBLAS_NUM_THREADS=4 \
    MKL_NUM_THREADS=4

WORKDIR /app
COPY requirements.lock pyproject.toml README.md ./
RUN python -m pip install --no-cache-dir --only-binary=:all: -r requirements.lock
COPY src ./src
RUN python -m pip install --no-cache-dir --no-deps .

RUN useradd --create-home --uid 10001 brace
USER brace
ENTRYPOINT ["python", "-m", "brace_msi"]
CMD ["--help"]
