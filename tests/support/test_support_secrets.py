import os

import pytest

from proper.support import secrets


def test_new_master_key_file(dst):
    master_key = secrets.new_master_key_file(dst)
    key_path = dst / secrets.MASTER_KEY_FILE

    assert key_path.is_file()
    assert key_path.read_bytes() == master_key


def test_read_master_key_from_file(dst):
    master_key = secrets.new_master_key_file(dst)
    assert secrets.read_master_key(dst) == master_key


def test_read_master_key_from_env(dst):
    master_key = secrets.generate_master_key()
    os.environ[secrets.MASTER_KEY_ENV] = master_key.decode("utf8")
    assert secrets.read_master_key(dst) == master_key
    del os.environ[secrets.MASTER_KEY_ENV]


def test_master_key_env_over_file(dst):
    master_key_env = secrets.generate_master_key()
    os.environ[secrets.MASTER_KEY_ENV] = master_key_env.decode("utf8")

    master_key_file = secrets.new_master_key_file(dst)

    assert master_key_file != master_key_env
    assert secrets.read_master_key(dst) == master_key_env
    del os.environ[secrets.MASTER_KEY_ENV]


def test_make_defaults():
    ds = secrets.make_prod_default_secrets()
    assert ds
    assert "secret_key: " in ds

    ds_again = secrets.make_prod_default_secrets()
    assert ds != ds_again


def test_read_secrets(dst):
    secrets.new_master_key_file(dst)
    secrets_path = dst / "secrets.enc"
    my_secrets = "This will be encrypted"
    secrets.save_secrets(secrets_path, my_secrets)

    assert secrets.read_secrets(secrets_path) == my_secrets


def test_read_empty_secrets(dst):
    secrets.new_master_key_file(dst)
    secrets_path = dst / "secrets.enc"
    secrets.save_secrets(secrets_path, "")

    assert secrets.read_secrets(secrets_path) == ""


def test_read_empty_secrets_no_master_key(dst):
    secrets_path = dst / "secrets.enc"
    secrets_path.touch()

    assert secrets.read_secrets(secrets_path) == ""


def test_read_no_secrets(dst):
    secrets_path = dst / "secrets.enc"

    with pytest.raises(Exception):
        secrets.read_secrets(secrets_path)


def test_read_secrets_but_no_master_key(dst):
    secrets_path = dst / "secrets.enc"
    secrets_path.write_text("whatever")

    with pytest.raises(IOError):
        secrets.read_secrets(secrets_path)


def test_read_invalid_secrets(dst):
    secrets_path = dst / "secrets.enc"
    secrets_path.write_bytes(b"this is invalid")
    secrets.new_master_key_file(dst)

    with pytest.raises(Exception):
        secrets.read_secrets(secrets_path)
