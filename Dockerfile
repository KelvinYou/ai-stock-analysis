FROM python:3.12-slim

ARG APP_VERSION=0.3.0

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    SETUPTOOLS_SCM_PRETEND_VERSION=${APP_VERSION} \
    SETUPTOOLS_SCM_PRETEND_VERSION_FOR_AI_STOCK_ANALYSIS=${APP_VERSION}

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint

# claude-agent-sdk bundles a platform-native Claude Code CLI. This image does
# not run `claude login` and does not copy ~/.claude; the worker receives its
# provider credential through the platform secret manager at runtime.
RUN pip install --no-cache-dir .

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin appuser \
    && chmod 0555 /usr/local/bin/docker-entrypoint \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

ENTRYPOINT ["/usr/local/bin/docker-entrypoint"]
# The worker service overrides this command with `stock-analysis-worker`.
CMD ["api"]
