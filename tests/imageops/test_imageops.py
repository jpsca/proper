from pathlib import Path

import pytest
import pyvips

from proper.storage.imageops import transform_image


# --- Helpers ---


HERE = Path(__file__).parent.absolute()
SOURCE = str(HERE / "armendariz-road.jpg")  # 600 x 448


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
