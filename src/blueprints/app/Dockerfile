# syntax=docker/dockerfile:1.2

# `python-base` sets up all our shared environment variables.
FROM python:3.12-slim as python-base

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
    # Poetry:
    # https://python-poetry.org/docs/configuration/#using-environment-variables
    POETRY_VERSION=1.8.2 \
    # Install packages in this directory.
    POETRY_HOME="/opt/poetry" \
    # Enable poetry to set up the virtual environment in the project's root directory
    # with the venv directory named `.venv`.
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    # Disable interactive questions.
    POETRY_NO_INTERACTION=1 \
    \
    # Paths:
    # This is where the requirements and virtual environment will live.
    WORKDIR="/app" \
    VENV_PATH="/app/.venv"

# Prepend poetry and venv to path.
ENV PATH="$POETRY_HOME/bin:$VENV_PATH/bin:$PATH"



# `builder-base` stage is used to build dependencies and create the virtual environment.
FROM python-base as builder-base

RUN apt-get update -y \
    && apt-get upgrade -y \
    && apt-get autoremove -y \
    && apt-get install -y --no-install-recommends curl \
    && apt-get clean \
    && rm -r /var/lib/apt/lists

# Install poetry. It respects $POETRY_VERSION & $POETRY_HOME.
RUN --mount=type=cache,target=/root/.cache \
    curl -sSL https://install.python-poetry.org | python -

# Copy project requirement files here to ensure they will be cached.
WORKDIR $WORKDIR
COPY pyproject.toml poetry.lock ./

# Install runtime dependencies, where it uses $POETRY_VIRTUALENVS_IN_PROJECT internally.
RUN --mount=type=cache,target=/root/.cache \
    # --no-root: Do not install the root package (your project).
    poetry install --no-root --only main



# `production` image used for runtime
FROM python-base as production

RUN apt-get update -y \
    && apt-get upgrade -y \
    && apt-get autoremove -y \
    && apt-get install -y --no-install-recommends curl libvips42 \
    && apt-get clean \
    && rm -r /var/lib/apt/lists

COPY --from=builder-base $POETRY_HOME $POETRY_HOME
COPY --from=builder-base $VENV_PATH $VENV_PATH

WORKDIR $WORKDIR
COPY pyproject.toml poetry.lock ./

# For external API.
EXPOSE 8080
