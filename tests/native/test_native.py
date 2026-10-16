"""`proper._native`: the library compiled from Pascal, checked against Python."""
import hashlib
import hmac
import os

import pytest

from proper import _native
from proper._native import build


KERNELS = {0: "scalar", 1: "avx2", 2: "sha-ni", 3: "crypto-ext"}
DATA = os.urandom(5000)


@pytest.fixture()
def kernel():
    """Switch kernels in a test, and back to the one chosen at load."""
    lib = _native.lib
    chosen = lib.proper_sha256_kernel()

    def use(k):
        if not lib.proper_sha256_use(k):
            pytest.skip(f"no {KERNELS[k]} kernel on this CPU")

    yield use
    assert lib.proper_sha256_use(chosen)


def sha256(data):
    digest = _native.ffi.new("unsigned char[32]")
    _native.lib.proper_sha256(data, len(data), digest)
    return bytes(digest)


def hmac_sha256(key, msg):
    prepared = _native.ffi.new("char[]", _native.lib.proper_hmac_key_size())
    _native.lib.proper_hmac_key(key, len(key), prepared)
    digest = _native.ffi.new("unsigned char[32]")
    _native.lib.proper_hmac_sha256(prepared, msg, len(msg), digest)
    return bytes(digest)


@pytest.mark.parametrize("k", KERNELS)
def test_sha256_of_every_length(kernel, k):
    kernel(k)
    for n in [*range(0, 300), 1000, 4096, 4999]:
        assert sha256(DATA[:n]) == hashlib.sha256(DATA[:n]).digest(), n


@pytest.mark.parametrize("k", KERNELS)
def test_hmac(kernel, k):
    kernel(k)
    for klen in (0, 1, 32, 63, 64, 65, 200, 1000):
        key = DATA[100:100 + klen]
        for n in (0, 1, 55, 56, 64, 119, 120, 200, 1000):
            assert hmac_sha256(key, DATA[:n]) == hmac.new(key, DATA[:n], hashlib.sha256).digest()


def test_the_best_kernel_is_chosen():
    lib = _native.lib
    chosen = lib.proper_sha256_kernel()
    best = next(k for k in (2, 3, 1, 0) if lib.proper_sha256_use(k))
    assert lib.proper_sha256_use(chosen)
    assert chosen == best


def test_an_unknown_kernel():
    assert _native.lib.proper_sha256_use(99) == 0
    assert _native.lib.proper_sha256_use(-1) == 0


@pytest.mark.parametrize("secret_len", [0, 1, 32, 64, 65, 200])
@pytest.mark.parametrize("salt", [b"", b"session cookie", b"s" * 100])
def test_derive_key(secret_len, salt):
    """HMAC-SHA256 of the salt keyed with the secret, as itsdangerous derives it."""
    secret = DATA[:secret_len]
    prepared = _native.ffi.new("char[]", _native.lib.proper_hmac_key_size())
    _native.lib.proper_derive_key(secret, len(secret), salt, len(salt), prepared)
    digest = _native.ffi.new("unsigned char[32]")
    _native.lib.proper_hmac_sha256(prepared, b"message", 7, digest)
    derived = hmac.new(secret, salt, hashlib.sha256).digest()
    assert bytes(digest) == hmac.new(derived, b"message", hashlib.sha256).digest()


def test_buffers_too_small_to_sign_into():
    keys = _native.Signing([b"k" * 32], b"s")
    stream = _native._buffers.stream
    json = b'{"v": "' + b"ab" * 100 + b'"}'
    out = _native.ffi.new("char[]", 1000)
    scratch = _native.ffi.new("char[]", 1000)
    lib = _native.lib
    # the output, then the scratch buffer (where zlib writes) too small
    assert lib.proper_sign_json(keys._newest, stream, json, len(json), 1, out, 10,
                                scratch, 1000) == _native.TOO_SMALL
    assert lib.proper_sign_json(keys._newest, stream, json, len(json), 1, out, 1000,
                                scratch, 4) == _native.TOO_SMALL
    # the stream is reset at each call: a failed one leaves it usable
    assert lib.proper_sign_json(keys._newest, stream, json, len(json), 1, out, 1000,
                                scratch, 1000) > 0


def test_the_version():
    assert _native.ffi.string(_native.lib.proper_native_version()) == b"0.1.0"


def test_without_the_library(tmp_path):
    with pytest.raises(ImportError, match="src/proper/_native/build.py"):
        _native._load(tmp_path / "missing.so")


def test_build(tmp_path):
    out = build.build(tmp_path / "lib.so")
    ffi, lib = _native._load(out)
    assert ffi.string(lib.proper_native_version()) == b"0.1.0"


def test_build_without_fpc(monkeypatch):
    monkeypatch.delenv("PROPER_FPC", raising=False)
    monkeypatch.setattr(build.shutil, "which", lambda name: None)
    with pytest.raises(RuntimeError, match="Free Pascal"):
        build.build()


def test_build_shows_what_fpc_says(tmp_path):
    fpc = tmp_path / "fpc"
    fpc.write_text("#!/bin/sh\necho 'proper_native.pas(1,1) Fatal: something is wrong'\nexit 1\n")
    fpc.chmod(0o755)
    with pytest.raises(RuntimeError, match="Fatal: something is wrong"):
        build.build(tmp_path / "lib.so", fpc=str(fpc))
