from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any, Optional


DEFAULT_CROP = "centre"
DEFAULT_EXTEND = "background"
DEFAULT_GRAVITY = "centre"
SUPPORTED_OPERATIONS = (
    "adaptive_blur",
    "adaptive_resize",
    "adaptive_sharpen",
    "adjoin",
    "affine",
    "alpha",
    "annotate",
    "antialias",
    "append",
    "apply",
    "attenuate",
    "authenticate",
    "auto_gamma",
    "auto_level",
    "auto_orient",
    "auto_threshold",
    "backdrop",
    "background",
    "bench",
    "bias",
    "bilateral_blur",
    "black_point_compensation",
    "black_threshold",
    "blend",
    "blue_primary",
    "blue_shift",
    "blur",
    "border",
    "bordercolor",
    "borderwidth",
    "brightness_contrast",
    "cache",
    "canny",
    "caption",
    "channel",
    "channel_fx",
    "charcoal",
    "chop",
    "clahe",
    "clamp",
    "clip",
    "clip_path",
    "clone",
    "clut",
    "coalesce",
    "colorize",
    "colormap",
    "color_matrix",
    "colors",
    "colorspace",
    "colourspace",
    "color_threshold",
    "combine",
    "combine_options",
    "comment",
    "compare",
    "complex",
    "compose",
    "composite",
    "compress",
    "connected_components",
    "contrast",
    "contrast_stretch",
    "convert",
    "convolve",
    "copy",
    "crop",
    "cycle",
    "deconstruct",
    "define",
    "delay",
    "delete",
    "density",
    "depth",
    "descend",
    "deskew",
    "despeckle",
    "direction",
    "displace",
    "dispose",
    "dissimilarity_threshold",
    "dissolve",
    "distort",
    "dither",
    "draw",
    "duplicate",
    "edge",
    "emboss",
    "encoding",
    "endian",
    "enhance",
    "equalize",
    "evaluate",
    "evaluate_sequence",
    "extent",
    "extract",
    "family",
    "features",
    "fft",
    "fill",
    "filter",
    "flatten",
    "flip",
    "floodfill",
    "flop",
    "font",
    "foreground",
    "format",
    "frame",
    "function",
    "fuzz",
    "fx",
    "gamma",
    "gaussian_blur",
    "geometry",
    "gravity",
    "grayscale",
    "green_primary",
    "hald_clut",
    "highlight_color",
    "hough_lines",
    "iconGeometry",
    "iconic",
    "identify",
    "ift",
    "illuminant",
    "immutable",
    "implode",
    "insert",
    "intensity",
    "intent",
    "interlace",
    "interline_spacing",
    "interpolate",
    "interpolative_resize",
    "interword_spacing",
    "kerning",
    "kmeans",
    "kuwahara",
    "label",
    "lat",
    "layers",
    "level",
    "level_colors",
    "limit",
    "limits",
    "linear_stretch",
    "linewidth",
    "liquid_rescale",
    "list",
    "loader",
    "log",
    "loop",
    "lowlight_color",
    "magnify",
    "map",
    "mattecolor",
    "median",
    "mean_shift",
    "metric",
    "mode",
    "modulate",
    "moments",
    "monitor",
    "monochrome",
    "morph",
    "morphology",
    "mosaic",
    "motion_blur",
    "name",
    "negate",
    "noise",
    "normalize",
    "opaque",
    "ordered_dither",
    "orient",
    "page",
    "paint",
    "pause",
    "perceptible",
    "ping",
    "pointsize",
    "polaroid",
    "poly",
    "posterize",
    "precision",
    "preview",
    "process",
    "quality",
    "quantize",
    "quiet",
    "radial_blur",
    "raise",
    "random_threshold",
    "range_threshold",
    "red_primary",
    "regard_warnings",
    "region",
    "remote",
    "render",
    "repage",
    "resample",
    "resize",
    "respect_parentheses",
    "reverse",
    "roll",
    "rotate",
    "sample",
    "sampling_factor",
    "saver",
    "scale",
    "scene",
    "screen",
    "seed",
    "segment",
    "selective_blur",
    "separate",
    "sepia_tone",
    "shade",
    "shadow",
    "shared_memory",
    "sharpen",
    "shave",
    "shear",
    "sigmoidal_contrast",
    "silent",
    "similarity_threshold",
    "size",
    "sketch",
    "smush",
    "snaps",
    "solarize",
    "sort_pixels",
    "sparse_color",
    "splice",
    "spread",
    "statistic",
    "stegano",
    "stereo",
    "storage_type",
    "stretch",
    "strip",
    "stroke",
    "strokewidth",
    "style",
    "subimage_search",
    "swap",
    "swirl",
    "synchronize",
    "taint",
    "text_font",
    "threshold",
    "thumbnail",
    "tile_offset",
    "tint",
    "title",
    "transform",
    "transparent",
    "transparent_color",
    "transpose",
    "transverse",
    "treedepth",
    "trim",
    "type",
    "undercolor",
    "unique_colors",
    "units",
    "unsharp",
    "update",
    "valid_image",
    "view",
    "vignette",
    "virtual_pixel",
    "visual",
    "watermark",
    "wave",
    "wavelet_denoise",
    "weight",
    "white_balance",
    "white_point",
    "white_threshold",
    "window",
    "window_group",
)


class ImagePipeline:
    def __init__(self, image) -> None:
        self.image = image

    def __getattr__(self, __name: str) -> "Any":
        if __name not in SUPPORTED_OPERATIONS:
            raise AttributeError(__name)

    def resize_to_limit(
        self, width: int = None, height: int = None, **opts
    ) -> "ImagePipeline":
        """Downsizes the image to fit within the specified dimensions while
        retaining the original aspect ratio. Will only resize the image if
        it's larger than the specified dimensions.

        It's possible to omit one dimension, in which case the image will
        be resized only by the provided dimension.

        Any additional options are forwarded to `pyvips.Image.thumbnail_image`.
        """
        return self

    def resize_to_fit(
        self, width: int = None, height: int = None, **opts
    ) -> "ImagePipeline":
        """Resizes the image to fit within the specified dimensions while
        retaining the original aspect ratio. Will downsize the image if
        it's larger than the specified dimensions or upsize if
        it's smaller.

        It's possible to omit one dimension, in which case the image will
        be resized only by the provided dimension.

        Any additional options are forwarded to `pyvips.Image.thumbnail_image`.
        """
        pass
        return self

    def resize_to_fill(
        self, width: int = None, height: int = None, crop: str = DEFAULT_CROP, **opts
    ) -> "ImagePipeline":
        """Resizes the image to fill the specified dimensions while
        retaining the original aspect ratio. If necessary, will crop the image
        in the larger dimension.

        Crop option is "centre" by default. Acceptable options are currently:
        - "attention": look for features likely to draw human attention
        - "centre": just take the centre
        - "entropy": use an entropy measure
        - "low": (v8.8+) crop is positioned at the top or left
        - "high": (v8.8+) crop is positioned at the bottom or right
        - "none" or `None`: do nothing

        Any additional options are forwarded to `pyvips.Image.thumbnail_image`.
        """
        return self

    def resize_and_pad(
        self,
        width: int = None,
        height: int = None,
        *,
        alpha: bool = False,
        extend: str = DEFAULT_EXTEND,
        background: "Optional[str]" = None,
        gravity: str = DEFAULT_GRAVITY,
        **opts
    ) -> "ImagePipeline":
        """Resizes the image to fit within the specified dimensions while retaining
        the original aspect ratio. If necessary, will pad the remaining area with
        transparent color if source image has alpha channel, black otherwise.

        If you're converting from a format that doesn't support transparent colors
        (e.g. JPEG) to a format that does (e.g. PNG), setting `alpha` to `True` will
        add the alpha channel to the image.

        The `extend` and `background` options are also accepted and forwarded
        to Vips. See: https://www.libvips.org/API/current/libvips-conversion.html#vips-gravity

        ```python
        pipeline.resize_and_pad(400, 400, extend="copy")
        ````

        The `gravity` option can be used to specify the direction where the source image
        will be positioned (defaults to "centre").

        ```python
        pipeline.resize_and_pad(400, 400, gravity="north-west")
        ```

        Any additional options are forwarded to `pyvips.Image.thumbnail_image`.
        """
        pass
        return self

    def run(self):
        image = self.image
        pass
        return image
