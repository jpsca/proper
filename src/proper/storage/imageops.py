import re
import typing as t
from pathlib import Path


try:
    import pyvips
except (ImportError, OSError):
    # ImportError: the python `pyvips` package isn't installed.
    # OSError: the package is installed but the libvips system library
    # can't be loaded (pyvips raises this on cffi.dlopen failure).
    pyvips = None  # type: ignore


if t.TYPE_CHECKING:
    from collections.abc import Callable

    class Image(t.Protocol):
        width: int
        height: int
        bands: int
        addalpha: Callable[[], "Image"]
        autorot: Callable[[], "Image"]
        bandjoin: Callable[..., "Image"]
        cast: Callable[..., "Image"]
        colourspace: Callable[..., "Image"]
        composite: Callable[..., "Image"]
        conv: Callable[..., "Image"]
        extract_band: Callable[..., "Image"]
        fliphor: Callable[[], "Image"]
        flipver: Callable[[], "Image"]
        gaussblur: Callable[..., "Image"]
        gravity: Callable[..., "Image"]
        hasalpha: Callable[[], bool]
        recomb: Callable[..., "Image"]
        similarity: Callable[..., "Image"]
        thumbnail_image: Callable[..., "Image"]
        write_to_buffer: Callable[..., bytes]


MAX_COORD = 10000000

ANTI_GRAVITY = {
    "north": "south",
    "south": "north",
    "east": "west",
    "west": "east",
}


def transform_image(
    source: str | bytes | bytearray,
    load: dict | None = None,
    save: dict | None = None,
    **ops: t.Any,
) -> bytes:
    if pyvips is None:
        raise ImportError("pyvips is required to use the image processing features.")

    load = load or {}
    save = save or {}

    autorot = load.pop("autorot", load.pop("autorotate", True))
    if isinstance(source, (bytes, bytearray)):
        image = pyvips.Image.new_from_buffer(source, "", **load)
    else:
        image = pyvips.Image.new_from_file(source, **load)
    if image is None:
        raise ValueError("Could not load image from source")
    image = t.cast("Image", image)

    if autorot:
        image = image.autorot()

    for name, values in ops.items():
        op = VALID_OPS.get(name)
        if op is None:
            raise ValueError(f"Invalid transformation: {name}")

        if not isinstance(values, (list, tuple)):
            values = (values,)
        if values and isinstance(values[-1], dict):
            kw = values[-1]
            args = values[:-1]
        else:
            args = values
            kw = {}

        image = op(image, *args, **kw)

    format = save.pop("format", ".jpg").lower()
    if not format.startswith("."):
        format = "." + format
    return image.write_to_buffer(format, **save)


def resize_to_fit(
    image: "Image", width: int | None = None,
    height: int | None = None,
    size: t.Literal["both"] | t.Literal["down"] | t.Literal["up"] | t.Literal["force"] = "both",
    **options
) -> "Image":
    """
    Resizes the image to fit within the specified dimensions while retaining
    the original aspect ratio. Will downsize the image if it's larger than the
    specified dimensions or upsize if it's smaller.

    ```python
    pipeline = ImageProcessing(image)  # 600x800
    result = pipeline.resize_to_fit(400, 400).run()
    pyvips.Image.new_from_file(result.path).size  # [300, 400]
    ```

    It's possible to omit one dimension, in which case the image will be resized
    only by the provided dimension.

    ```python
    pipeline.resize_to_fit(400, None)
    # or
    pipeline.resize_to_fit(None, 400)
    ```

    By default, the image will be downsized if it's larger than the specified dimensions
    and upsized if it's smaller. You can control this behavior with the `size` option:

    ```python
    pipeline = ImageProcessing(image)  # 400x300
    pipeline.resize_to_fit(500, 500, size="down")  # -> [400, 300]
    pipeline.resize_to_fit(500, 500, size="up")  # -> [500, 375]
    pipeline.resize_to_fit(500, 500, size="force")  # -> [500, 500]  (ignoring aspect ratio)
    ```

    Any other options are forwarded to `pyvips.Image.thumbnail_image()`:

    ```python
    pipeline.resize_to_fit(400, 400, linear=True)
    ```

    See [vips_thumbnail()](https://www.libvips.org/API/current/ctor.Image.thumbnail.html)
    for more details.
    """
    iwidth, iheight = _default_dimensions(width, height)
    options["size"] = size
    return _thumbnail(image, iwidth, iheight, **options)


def resize_to_limit(image: "Image", width: int | None = None, height: int | None = None, **options) -> "Image":
    """
    Resizes the image to fit within the specified dimensions while retaining
    the original aspect ratio. Will only downsize the image if it's larger than
    the specified dimensions, but won't upsize if it's smaller.

    ```python
    pipeline = ImageProcessing(image)  # 400x300
    result = pipeline.resize_to_limit(500, 500).run()
    pyvips.Image.new_from_file(result.path).size  # [400, 300]
    ```

    Any other options are forwarded to `pyvips.Image.thumbnail_image()`:

    ```python
    pipeline.resize_to_limit(400, 400, linear=True)
    ```

    See [vips_thumbnail()](https://www.libvips.org/API/current/ctor.Image.thumbnail.html)
    for more details.
    """
    options["size"] = "down"
    return resize_to_fit(image, width, height, **options)


def resize_to_fill(image: "Image", width: int, height: int, **options) -> "Image":
    """
    Resizes the image to fill the specified dimensions while retaining
    the original aspect ratio. If necessary, will crop the image in the
    larger dimension.

    ```python
    pipeline = ImageProcessing(image)  # 600x800
    result = pipeline.resize_to_fill(400, 400).run()
    pyvips.Image.new_from_file(result.path).size # [400, 400]
    ```

    Any other options are forwarded to `pyvips.Image.thumbnail_image()`:

    ```python
    pipeline.resize_to_fill(400, 400, crop="attention") # smart crop
    ```

    See [vips_thumbnail()](https://www.libvips.org/API/current/ctor.Image.thumbnail.html)
    for more details.
    """
    assert pyvips
    options.setdefault("crop", pyvips.Interesting.CENTRE)
    return _thumbnail(image, width, height, **options)


def resize_and_pad(
    image: "Image",
    width: int,
    height: int,
    *,
    gravity: str = "",
    extend: str = "",
    background: list[float] | None = None,
    alpha: bool = False,
    **options,
) -> "Image":
    """
    Resizes the image to fit within the specified dimensions while retaining
    the original aspect ratio. If necessary, will pad the remaining area with
    transparent color if source image has alpha channel, black otherwise.

    ```python
    pipeline = ImageProcessing(image)  # 600x800
    result = pipeline.resize_and_pad(400, 400).run()
    pyvips.Image.new_from_file(result.path).size  # [400, 400]
    ```

    If you're converting from a format that doesn't support transparent
    colors (e.g. JPEG) to a format that does (e.g. PNG), setting `alpha`
    to `True` will add the alpha channel to the image:

    ```python
    pipeline.resize_and_pad(400, 400, alpha=True)
    ```

    The `extend` and `background` options are also accepted and are forwarded
    to pyvips.Image.gravity():

    ```python
    pipeline.resize_and_pad(400, 400, extend="copy")
    ```

    The `gravity` option can be used to specify the direction where the source
    image will be positioned (defaults to "centre").

    ```python
    pipeline.resize_and_pad(400, 400, gravity="north-west")
    ```

    Any other options are forwarded to `pyvips.Image.thumbnail_image()`:

    ```python
    pipeline.resize_to_fill(400, 400, linear=True)
    ```

    See [vips_thumbnail()](https://www.libvips.org/API/current/ctor.Image.thumbnail.html)
    and [vips_gravity()](https://www.libvips.org/API/current/libvips-conversion.html#vips-gravity)
    for more details.
    """
    assert pyvips
    extend = extend or pyvips.Extend.BLACK
    gravity = gravity or pyvips.Interesting.CENTRE
    image = _thumbnail(image, width, height, **options)
    if alpha and not image.hasalpha():
        image = image.addalpha()
    background = background or [0.0, 0.0, 0.0]
    return image.gravity(gravity, width, height, extend=extend, background=background)


def rotate(
    image: "Image", degrees: float, *, background: list[float] | None = None, **options
) -> "Image":
    """Rotates the image by an arbitrary angle.

    ```python
    ImageProcessing(source).rotate(90)
    ```

    For degrees that are not a multiple of 90, you can also specify a
    background color for the empty triangles in the corners, left over
    from rotating the image.

    ```python
    ImageProcessing(source).rotate(45, background: [0, 0, 0])
    ```

    Any other options are forwarded to `pyvips.Image.similarity()`.
    See [vips_similarity()](http://libvips.github.io/libvips/API/current/libvips-resample.html#vips-similarity)
    for more details.
    """
    background = background or [0.0, 0.0, 0.0]
    return image.similarity(angle=degrees, background=background, **options)


def composite(
    image: "Image",
    overlay: "str | Path | Image | list[str | Path | Image]",
    *,
    blend: str = "over",
    gravity: str | None = "north-west",
    offset: list[float] | None = None,
    **options,
) -> "Image":
    """
    Blend the specified image or array of images over the current one.
    One use case for this can be applying a watermark.

    ```python
    watermarked = ImageProcessing("source.png").composite("watermark.png").save()

    # OR

    watermarked = ImageProcessing("source.png") \
        .composite(["watermark1.png", "watermark2.png"]) \
        .save()
    ```

    The overlay can be a string, a `Path`, or a `pyvips.Image`.
    The blend mode can be specified via the `blend=` option (defaults to "over").

    ```python
    .composite(overlay, blend="atop")
    ```

    The direction and position of the overlayed image can be controlled via
    the `gravity=` and `offset=` options:

    ```python
    .composite(overlay, gravity="south-east")
    .composite(overlay, gravity="north-west", offset=[55, 55])
    ```

    Any additional options are forwarded to `pyvips.Image.composite()`.

    ```python
    .composite(overlay, premultiplied=True)
    ```

    See [vips_composite()](https://www.libvips.org/API/current/type_func.Image.composite.html)
    for more details.
    """
    sources = overlay if isinstance(overlay, list) else [overlay]
    sources = t.cast("list[str | Path | Image]", sources)
    overlays = [_to_image_with_alpha(source) for source in sources]

    if gravity:
        # apply offset with correct gravity and make remainder transparent
        if offset:
            overlays_ = []
            for ov in overlays:
                anti_gravity = _multi_replace(gravity, ANTI_GRAVITY)
                ov = ov.gravity(
                    anti_gravity, image.width + offset[0], image.height + offset[-1]
                )
                overlays_.append(ov)
            overlays = overlays_

        # create image-sized transparent background and apply specified gravity
        overlays = [ov.gravity(gravity, image.width, image.height) for ov in overlays]

    # apply the composition
    return image.composite(overlays, blend, **options)


def fliphor(image: "Image", *_args, **_kw):
    """Flip horizontally."""
    return image.fliphor()


def flipver(image: "Image", *_args, **_kw):
    """Flip vertically."""
    return image.flipver()


def sepia(image: "Image", r: float = 1.0, g: float = 0.89, b: float = 0.7, **_kw) -> "Image":
    """Apply a sepia tone filter.

    The three values control the per-channel multipliers applied after
    converting to grayscale.  The defaults produce a classic warm sepia.

    ```python
    attachment.variant(sepia=())                    # classic sepia
    attachment.variant(sepia=(1.0, 0.85, 0.6))      # warmer
    attachment.variant(sepia=(0.9, 0.9, 0.8))       # subtle, cooler
    ```
    """
    assert pyvips
    if image.hasalpha():
        alpha = image.extract_band(image.bands - 1)
        image = image.extract_band(0, n=image.bands - 1)
    else:
        alpha = None

    if image.bands < 3:
        image = image.colourspace("srgb")

    # Standard luminance weights (BT.601)
    luma = [0.299, 0.587, 0.114]
    matrix = pyvips.Image.new_from_array([
        [v * r for v in luma],
        [v * g for v in luma],
        [v * b for v in luma],
    ])
    image = image.recomb(matrix)
    image = image.cast("uchar")

    if alpha is not None:
        image = image.bandjoin(alpha)

    return image


def grayscale(
    image: "Image", r: float = 0.299, g: float = 0.587, b: float = 0.114, **_kw,
) -> "Image":
    """Convert to grayscale.

    The three values control how much each source channel contributes
    to the result.  The defaults use BT.601 perceptual luminance weights.

    ```python
    attachment.variant(grayscale=())                  # standard
    attachment.variant(grayscale=(0.333, 0.333, 0.334))  # equal weight
    attachment.variant(grayscale=(0.0, 1.0, 0.0))     # green channel only
    ```
    """
    assert pyvips

    if image.hasalpha():
        alpha = image.extract_band(image.bands - 1)
        image = image.extract_band(0, n=image.bands - 1)
    else:
        alpha = None

    if image.bands < 3:
        image = image.colourspace("srgb")

    luma = [r, g, b]
    matrix = pyvips.Image.new_from_array([luma, luma, luma])
    image = image.recomb(matrix)
    image = image.cast("uchar")

    if alpha is not None:
        image = image.bandjoin(alpha)

    return image


def blur(image: "Image", sigma: float = 4.0, **options) -> "Image":
    """Apply a Gaussian blur.

    ```python
    attachment.variant(blur=(2.5,))
    attachment.variant(blur=(5.0, {"precision": "integer"}))
    ```
    """
    return image.gaussblur(sigma, **options)


VALID_OPS = {
    "resize": resize_to_limit,
    "resize_to_limit": resize_to_limit,
    "resize_to_fit": resize_to_fit,
    "resize_to_fill": resize_to_fill,
    "resize_and_pad": resize_and_pad,
    "rotate": rotate,
    "composite": composite,
    "fliphor": fliphor,
    "flipver": flipver,
    "sepia": sepia,
    "grayscale": grayscale,
    "blur": blur,
}


def _multi_replace(string: str, substitutions: dict[str, str]) -> str:
    substrings = sorted(substitutions.keys(), key=lambda s: len(s), reverse=True)
    regex = re.compile("|".join(re.escape(s) for s in substrings))
    return regex.sub(lambda match: substitutions[match.group(0)], string)


def _thumbnail(image: "Image", width: int, height: int, **options) -> "Image":
    """Resizes the image according to the specified parameters,
    and sharpens the resulting thumbnail.
    """
    assert pyvips
    # We're already autorotating when loading the image
    if pyvips.at_least_libvips(8, 8):  # pragma: no cover
        options["no_rotate"] = True
    else:  # pragma: no cover
        options["auto_rotate"] = False

    image = image.thumbnail_image(width, height=height, **options)
    # Default sharpening mask that provides a fast and mild sharpen.
    sharpen = pyvips.Image.new_from_array([[-1, -1, -1], [-1, 32, -1], [-1, -1, -1]], 24)
    image = image.conv(sharpen, precision=pyvips.Precision.INTEGER)
    return image


def _default_dimensions(width: int | None, height: int | None) -> tuple[int, int]:
    if not (width or height):
        raise ValueError("either width or height must be specified")
    return width or MAX_COORD, height or MAX_COORD


def _to_image_with_alpha(source: "str | Path | Image") -> "Image":
    assert pyvips
    if isinstance(source, pyvips.Image):
        image = source
    else:
        image = pyvips.Image.new_from_file(source)
    image = t.cast("Image", image)
    if not image.hasalpha():
        image = image.addalpha()
    return image
