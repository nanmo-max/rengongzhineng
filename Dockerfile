FROM mcr.microsoft.com/azurelinux/base/python:3.12@sha256:379135d4dbe66b12825a54d4ed7aef21aa61227533ff1b9151d70f95f9266746

ARG PIP_INDEX_URL=https://pypi.org/simple

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    BRACE_FORMAL_RELEASE=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_RETRIES=10 \
    OMP_NUM_THREADS=4 \
    OPENBLAS_NUM_THREADS=4 \
    MKL_NUM_THREADS=4

WORKDIR /app
RUN tdnf install -y shadow-utils \
    && tdnf clean all
COPY requirements.lock pyproject.toml README.md ./
RUN python3 -m pip install --no-cache-dir --index-url "${PIP_INDEX_URL}" --only-binary=:all: -r requirements.lock
COPY src ./src
RUN python3 -m pip install --no-cache-dir --no-deps . \
    && rm -rf /app/src /app/build /app/pyproject.toml /app/README.md /app/requirements.lock \
    && find /usr/lib/python3.12/site-packages -type d -name __pycache__ -prune -exec rm -rf '{}' +
COPY submission/harness.py /app/harness.py
COPY submission/contest_submission.py /app/contest_submission.py

RUN useradd --create-home --uid 10001 brace
USER brace
ENV CONTEST_SUBMISSION=contest_submission \
    BRACE_POLICY_MODE=portfolio \
    BRACE_MAX_TRAINING_ROUNDS=8 \
    BRACE_MIN_RELATIVE_IMPROVEMENT=0.0 \
    BRACE_MAX_REPLAY_SAMPLES=4096
ENTRYPOINT ["python3", "/app/harness.py"]
CMD ["--help"]
