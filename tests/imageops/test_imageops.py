from pathlib import Path

import pytest
import pyvips

from proper.storage.imageops import blur, grayscale, sepia, transform_image


HERE = Path(__file__).parent.absolute()
SOURCE = str(HERE / "armendariz-road.jpg")  # 600 x 448


@pytest.fixture()
def rgb_image():
    """Create a simple 2x2 RGB pyvips image."""
    pyvips = pytest.importorskip("pyvips")
    # 2x2 red image (255, 0, 0) in sRGB
    image = pyvips.Image.black(2, 2, bands=3).add([255, 0, 0]).cast("uchar")
    return image.copy(interpretation=pyvips.Interpretation.SRGB)


@pytest.fixture()
def rgba_image(rgb_image):
    """Create a 2x2 RGBA image with full opacity."""
    return rgb_image.addalpha()


def assert_similar(image1, image2, threshold=4):
    f1 = fingerprint(image1)
    f2 = fingerprint(image2)
    diff = 0
    for a, b in zip(f1, f2, strict=True):
        if a != b:
            diff += 1

    print("DIFFERENCE:", diff)
    assert threshold > diff


def fingerprint(image: pyvips.Image, power: int = 3):
    """
    Difference Hash (computes differences horizontally)
    Follows http://www.hackerfactor.com/blog/index.php?/archives/529-Kind-of-Like-That.html
    """
    size = 2**power
    image = image.thumbnail_image(size, height=size, size="force")
    image = image.flatten().colourspace("b-w")[0]
    pixels = image.tolist()
    diff = []
    for row in pixels:
        diff.extend([a > b for a, b in zip(row[1:], row[:-1], strict=True)])
    return diff


# --- Tests ---


def test_transform_invalid():
    with pytest.raises(ValueError):
        transform_image(SOURCE, foo=())


def test_transform_fit_fliphor():
    imbytes = transform_image(SOURCE, resize_to_fit=(400, 400), fliphor=())
    image = pyvips.Image.new_from_buffer(imbytes, "")
    ref = pyvips.Image.new_from_file(str(HERE / "fit-fliphor.jpg"))

    assert [image.width, image.height] == [400, 299]
    assert_similar(image, ref)


def test_transform_fill_sepia():
    imbytes = transform_image(SOURCE, resize_to_fill=(400, 400), sepia=())
    image = pyvips.Image.new_from_buffer(imbytes, "")
    ref = pyvips.Image.new_from_file(str(HERE / "fill-sepia.jpg"))

    assert [image.width, image.height] == [400, 400]
    assert_similar(image, ref)


def test_transform_grayscale_pad():
    imbytes = transform_image(SOURCE, grayscale=(), resize_and_pad=(400, 400))
    image = pyvips.Image.new_from_buffer(imbytes, "")
    ref = pyvips.Image.new_from_file(str(HERE / "grayscale-pad.jpg"))

    assert [image.width, image.height] == [400, 400]
    assert_similar(image, ref)


def test_transform_rotate_flip_blur():
    imbytes = transform_image(
        SOURCE,
        rotate=(10, {"background": [255, 255, 255]}),
        flipver=(),
        blur=6,
    )
    image = pyvips.Image.new_from_buffer(imbytes, "")
    ref = pyvips.Image.new_from_file(str(HERE / "rotate-flip-blur.jpg"))

    assert [image.width, image.height] == [669, 545]
    assert_similar(image, ref)


def test_transform_composite():
    imbytes = transform_image(
        SOURCE,
        composite=(str(HERE / "fit-fliphor.jpg"), {"blend": "multiply"}),
    )
    image = pyvips.Image.new_from_buffer(imbytes, "")
    ref = pyvips.Image.new_from_file(str(HERE / "composite1.jpg"))

    assert [image.width, image.height] == [600, 448]
    assert_similar(image, ref)


def test_transform_composite2_with_gravity_and_offset():
    imbytes = transform_image(
        SOURCE,
        composite=(str(HERE / "fit-fliphor.jpg"), {"gravity": "north-west", "offset": [10, 10]}),
    )
    image = pyvips.Image.new_from_buffer(imbytes, "")
    ref = pyvips.Image.new_from_file(str(HERE / "composite2.jpg"))

    assert [image.width, image.height] == [600, 448]
    assert_similar(image, ref)


# --- imageops - sepia and grayscale filters ---


def test_sepia_returns_3_band_image(rgb_image):
    result = sepia(rgb_image)
    assert result.bands == 3


def test_sepia_preserves_alpha(rgba_image):
    result = sepia(rgba_image)
    assert result.bands == 4
    assert result.hasalpha()


def test_default_produces_warm_tones(rgb_image):
    result = sepia(rgb_image)
    # For a pure red input, R channel should be brightest
    pixel = result(0, 0)
    assert pixel[0] > pixel[1] > pixel[2]


def test_custom_tone(rgb_image):
    # Equal multipliers should produce identical channels (grayscale)
    result = sepia(rgb_image, 1.0, 1.0, 1.0)
    pixel = result(0, 0)
    assert pixel[0] == pixel[1] == pixel[2]


def test_grayscale_returns_3_band_image(rgb_image):
    result = grayscale(rgb_image)
    assert result.bands == 3


def test_grayscale_all_channels_equal(rgb_image):
    result = grayscale(rgb_image)
    pixel = result(0, 0)
    assert pixel[0] == pixel[1] == pixel[2]


def test_grayscale_preserves_alpha(rgba_image):
    result = grayscale(rgba_image)
    assert result.bands == 4
    assert result.hasalpha()


def test_custom_weights(rgb_image):
    # Only red channel contributes → pure red input → bright gray
    bright = grayscale(rgb_image, 1.0, 0.0, 0.0)
    # Only green channel contributes → pure red input → black
    dark = grayscale(rgb_image, 0.0, 1.0, 0.0)
    assert bright(0, 0)[0] > dark(0, 0)[0]


def test_returns_image(rgb_image):
    result = blur(rgb_image, 1.5)
    assert result.width == rgb_image.width
    assert result.height == rgb_image.height
    assert result.bands == rgb_image.bands


def test_preserves_alpha(rgba_image):
    result = blur(rgba_image, 1.5)
    assert result.bands == 4
    assert result.hasalpha()
