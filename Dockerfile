# The deployed image (docs/deployment.md): the FastAPI app serving the built web UI, and the CLI
# (refresh, prune). The CPU models are cached in /models, a volume.

FROM node:22-slim@sha256:4b150b48b4116e2a22f2c39cc27025fbf4f153e2078fd3b14d159fdb5c7279da AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.13-slim@sha256:2d44738ebf4ce5f63b9d9ea871e9c7cfdc0426f7b0c97cac915fd88ded1d86bb
# Nothing installs packages at runtime; pip's vendored libraries carry known advisories.
RUN rm -rf /usr/local/bin/pip* /usr/local/lib/python3.13/site-packages/pip* \
    /usr/local/lib/python3.13/ensurepip
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock ./
# uv is mounted for the build only, so the image doesn't ship it.
RUN --mount=from=ghcr.io/astral-sh/uv:0.11.21@sha256:ff07b86af50d4d9391d9daf4ff89ce427bc544f9aae87057e69a1cc0aa369946,source=/uv,target=/bin/uv \
    uv sync --frozen --no-dev --no-install-project
# The project stays where it is (an editable install): the eval harness and the source registry
# find evals/ and config/ relative to the source tree.
COPY README.md alembic.ini ./
COPY config ./config
COPY evals/datasets ./evals/datasets
COPY src ./src
RUN --mount=from=ghcr.io/astral-sh/uv:0.11.21@sha256:ff07b86af50d4d9391d9daf4ff89ce427bc544f9aae87057e69a1cc0aa369946,source=/uv,target=/bin/uv \
    uv sync --frozen --no-dev
COPY --from=web /web/dist ./web/dist
RUN useradd --uid 1000 --create-home app && mkdir /app/data /models && chown app:app /app/data /models
USER app
ENV PATH=/app/.venv/bin:$PATH FASTEMBED_CACHE_PATH=/models WEB_DIST=/app/web/dist
EXPOSE 8000
# One worker: the rate limits and token budgets live in process memory (api/limits.py). No access
# log: it would keep every visitor's IP address in the container logs (see the privacy policy).
CMD ["uvicorn", "rag_stack.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--no-access-log"]
