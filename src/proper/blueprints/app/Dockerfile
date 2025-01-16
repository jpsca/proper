# syntax=docker/dockerfile:1.2

# `python-base` sets up all our shared environment variables.
FROM python:3.12 as python-base

ENV \
    # All configurations are included in the following environment variables.
    # Python:
    # Send standard output and error to terminal to view them in real-time.
    PYTHONUNBUFFERED=1 \
    # Avoid creating .pyc files on importing source modules.
    PYTHONDONTWRITEBYTECODE=1 \
    \
    # Pip:
    # Disable pip cache.
    PIP_NO_CACHE_DIR=off \
    # Disable pip version check.
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    \
    # Paths:
    # This is where the requirements and virtual environment will live.
    WORKDIR="/app" \
    VIRTUAL_ENV="/app/.venv"

# Prepend poetry and venv to path.
ENV PATH="$VIRTUAL_ENV/bin:$PATH"



# `builder-base` stage is used to build dependencies and create the virtual environment.
FROM python-base as builder-base

RUN apt-get update -y \
    && apt-get upgrade -y \
    && apt-get autoremove -y \
    && apt-get install -y --no-install-recommends curl \
    && apt-get clean \
    && rm -r /var/lib/apt/lists

# Install uv
RUN --mount=type=cache,target=/root/.cache \
    curl -LsSf https://astral.sh/uv/install.sh | sh

# Copy project requirement files here to ensure they will be cached.
WORKDIR $WORKDIR
COPY pyproject.toml uv.lock ./

# Install runtime dependencies
RUN --mount=type=cache,target=/root/.cache \
    # --no-root: Do not install the root package (your project).
    uv sync --group dev --group test


# `production` image used for runtime
FROM python-base as production

RUN apt-get update -y \
    && apt-get upgrade -y \
    && apt-get autoremove -y \
    && apt-get install -y --no-install-recommends curl libvips42 \
    && apt-get clean \
    && rm -r /var/lib/apt/lists

COPY --from=builder-base $VIRTUAL_ENV $VIRTUAL_ENV

WORKDIR $WORKDIR
COPY pyproject.toml uv.lock ./

# For external API.
EXPOSE 8080
