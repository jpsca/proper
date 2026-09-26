"""boto3, redis and pyvips are imported the first time something needs
them, never at startup: together they cost tens of megabytes per process,
and most apps use at most one of them.
"""
import subprocess
import sys

import pytest

from proper.storage import imageops


def _import_and_report():
    code = (
        "import sys\n"
        "import proper.app, proper.storage.attachment, proper.channels.cable, "
        "proper.cache.redis_cache, proper.storage.services.s3\n"
        "print(sorted(m for m in ('boto3', 'botocore', 'redis', 'pyvips') "
        "if m in sys.modules))\n"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    return out.stdout.strip()


def test_nothing_heavy_is_imported_with_the_framework():
    assert _import_and_report() == "[]"


class TestRedisCable:
    def test_missing_library_is_reported(self, monkeypatch):
        import proper.channels.cable as mod

        monkeypatch.setattr(mod, "redis", None)
        monkeypatch.setattr(mod, "aioredis", None)
        monkeypatch.setitem(sys.modules, "redis", None)
        with pytest.raises(ImportError, match="redis is required"):
            mod.RedisCable()

    def test_the_library_is_loaded_on_first_use(self, monkeypatch):
        import proper.channels.cable as mod

        monkeypatch.setattr(mod, "redis", None)
        monkeypatch.setattr(mod, "aioredis", None)
        mod.RedisCable()
        assert mod.redis is not None
        assert mod.aioredis is not None


class TestS3:
    def test_missing_library_is_reported(self, monkeypatch):
        import proper.storage.services.s3 as mod

        monkeypatch.setattr(mod, "boto3", None)
        monkeypatch.setattr(mod, "BotoConfig", None)
        monkeypatch.setitem(sys.modules, "boto3", None)
        with pytest.raises(ImportError, match="boto3 is required"):
            mod.S3(None, bucket="b")


class TestPyvips:
    @pytest.fixture()
    def unloaded(self, monkeypatch):
        monkeypatch.setattr(imageops, "pyvips", None)
        yield
        # Put the real module back for the other tests, with the default
        # loader allowlist.
        imageops.pyvips = None
        imageops.restrict_loaders()
        imageops.load_pyvips()

    def test_missing_library_gives_none(self, unloaded, monkeypatch):
        monkeypatch.setitem(sys.modules, "pyvips", None)
        assert imageops.load_pyvips() is None
        with pytest.raises(ImportError, match="pyvips is required"):
            imageops.transform_image(b"", resize_to_fit=(2, 2))

    def test_loaders_are_restricted_when_the_library_loads(self, unloaded):
        # Restricting before the library is loaded only records the choice...
        imageops.restrict_loaders(("VipsForeignLoadPng",))
        assert imageops.pyvips is None

        # ...and it is applied the moment the library comes in.
        vips = imageops.load_pyvips()
        assert vips is not None
        png = vips.Image.black(2, 2).cast("uchar").write_to_buffer(".png")
        jpg = vips.Image.black(2, 2).cast("uchar").write_to_buffer(".jpg")
        vips.Image.new_from_buffer(png, "").avg()
        with pytest.raises(vips.Error):
            vips.Image.new_from_buffer(jpg, "").avg()

    def test_loading_twice_is_a_no_op(self):
        first = imageops.load_pyvips()
        assert imageops.load_pyvips() is first
