import os
import subprocess
import time

import boto3
import peewee as pw
import pytest
import redis
from botocore.exceptions import ClientError, EndpointConnectionError

from proper import App, current
from proper.models import ProperModel


@pytest.fixture()
def app():
    config = {
        "SECRET_KEYS": ["*" * 50],
        "DEBUG": False,
    }
    app = App(__name__, config)
    current.app = app
    return app


@pytest.fixture()
def db():
    database = pw.SqliteDatabase(":memory:")
    database.connect(reuse_if_open=True)
    yield database
    database.close()


@pytest.fixture()
def BaseModel(app, db):
    class BaseModel(ProperModel):
        class Meta:
            database = db

    return BaseModel


# --- Docker container fixtures ---


def _redis_ready(url) -> bool:
    try:
        r = redis.from_url(url)
        r.ping()
        r.close()
        return True
    except Exception:
        return False


def _minio_ready(endpoint, access_key, secret_key) -> bool:
    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
    )
    try:
        client.list_buckets()
        return True
    except (EndpointConnectionError, ClientError):
        return False


REDIS_CONTAINER = "redis:7-alpine"
REDIS_PORT = 19736
REDIS_NAME = "proper-test-redis"


def _docker_available() -> bool:
    try:
        result = subprocess.run(
            ["docker", "info"], capture_output=True, timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


@pytest.fixture(scope="session")
def redis_url():
    """Provide a Redis URL: reuse a local Redis if present, else spin up a container."""
    # 1. Honor an explicit URL from the environment.
    env_url = os.environ.get("REDIS_URL")
    if env_url and _redis_ready(env_url):
        yield env_url
        return

    # 2. Reuse a Redis already running on the default port.
    default_url = "redis://127.0.0.1:6379/0"
    if _redis_ready(default_url):
        yield default_url
        return

    # 3. Fall back to a disposable Docker container.
    if not _docker_available():
        pytest.skip(
            "No Redis available: set REDIS_URL, run redis on :6379, or start Docker"
        )

    url = f"redis://127.0.0.1:{REDIS_PORT}/0"

    subprocess.run(["docker", "rm", "-f", REDIS_NAME], capture_output=True)
    result = subprocess.run(
        [
            "docker", "run", "-d",
            "--name", REDIS_NAME,
            "-p", f"{REDIS_PORT}:6379",
            REDIS_CONTAINER,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.skip(f"Could not start Redis container: {result.stderr}")

    for _ in range(30):
        if _redis_ready(url):
            break
        time.sleep(0.5)
    else:
        subprocess.run(["docker", "rm", "-f", REDIS_NAME], capture_output=True)
        pytest.skip("Redis did not become ready in time")

    yield url

    subprocess.run(["docker", "rm", "-f", REDIS_NAME], capture_output=True)


MINIO_CONTAINER = "minio/minio"
MINIO_PORT = 19123
MINIO_NAME = "proper-test-minio"


@pytest.fixture(scope="session")
def MINIO_ROOT_USER():
    return "minioadmin"


@pytest.fixture(scope="session")
def MINIO_ROOT_PASSWORD():
    return "minioadmin"


@pytest.fixture(scope="session")
def MINIO_BUCKET():
    return "test-bucket"


@pytest.fixture(scope="session")
def minio(MINIO_ROOT_USER, MINIO_ROOT_PASSWORD, MINIO_BUCKET):
    """Start a MinIO container for the test session, skip if Docker is unavailable."""
    if not _docker_available():
        pytest.skip("Docker not available (start the daemon to run MinIO tests)")

    endpoint = f"http://127.0.0.1:{MINIO_PORT}"
    subprocess.run(
        ["docker", "rm", "-f", MINIO_NAME],
        capture_output=True,
    )
    result = subprocess.run(
        [
            "docker", "run", "-d",
            "--name", MINIO_NAME,
            "-p", f"{MINIO_PORT}:9000",
            "-e", f"MINIO_ROOT_USER={MINIO_ROOT_USER}",
            "-e", f"MINIO_ROOT_PASSWORD={MINIO_ROOT_PASSWORD}",
            MINIO_CONTAINER, "server", "/data",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.skip(f"Could not start MinIO container: {result.stderr}")

    for _ in range(30):
        if _minio_ready(endpoint, MINIO_ROOT_USER, MINIO_ROOT_PASSWORD):
            break
        time.sleep(0.5)
    else:
        subprocess.run(["docker", "rm", "-f", MINIO_NAME], capture_output=True)
        pytest.skip("MinIO did not become ready in time")

    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=MINIO_ROOT_USER,
        aws_secret_access_key=MINIO_ROOT_PASSWORD,
    )
    client.create_bucket(Bucket=MINIO_BUCKET)

    yield endpoint

    subprocess.run(
        ["docker", "rm", "-f", MINIO_NAME],
        capture_output=True,
    )
