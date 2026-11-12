FROM mcr.microsoft.com/azurelinux/base/python:3.12@sha256:379135d4dbe66b12825a54d4ed7aef21aa61227533ff1b9151d70f95f9266746

ARG PIP_INDEX_URL=https://pypi.org/simple

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_RETRIES=10 \
    OMP_NUM_THREADS=4 \
    OPENBLAS_NUM_THREADS=4 \
    MKL_NUM_THREADS=4

WORKDIR /app
RUN tdnf install -y shadow-utils \
    && tdnf clean all
COPY requirements.lock requirements-swanlab.lock requirements-pytrio.lock pyproject.toml README.md ./
RUN python3 -m pip install --no-cache-dir --index-url "${PIP_INDEX_URL}" --only-binary=:all: -r requirements.lock
RUN python3 -m pip install --no-cache-dir --index-url "${PIP_INDEX_URL}" -r requirements-swanlab.lock
RUN python3 -m pip install --no-cache-dir --index-url "${PIP_INDEX_URL}" -r requirements-pytrio.lock
COPY src ./src
RUN python3 -m pip install --no-cache-dir --no-deps .

RUN useradd --create-home --uid 10001 brace
USER brace
ENTRYPOINT ["python3", "-m", "brace_msi"]
CMD ["--help"]
