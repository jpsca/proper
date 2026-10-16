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
    assert _native.lib.proper_hmac_key(key, len(key), prepared) == 0
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
    for klen in (0, 1, 32, 63, 64):
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


def test_a_key_longer_than_64_bytes():
    with pytest.raises(ValueError):
        _native.Signing([b"k" * 65])


def test_a_buffer_too_small_to_sign_into():
    keys = _native.Signing([b"k" * 32])
    out = _native.ffi.new("char[]", 10)
    assert _native.lib.proper_sign(keys._newest, b"abc", 3, 1, out, 10) == _native.TOO_SMALL


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
