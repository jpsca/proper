import typing as t
from pathlib import Path

from proper.helpers import format_locale, logger


TPath = str | Path


class Reader:
    """Functions related to loading and parsing translation files.

    Arguments:

    - paths: path or a list of paths (relative or absolute) that will
        be searched for the translations.

    """

    __slots__ = ("paths",)

    def __init__(self, *paths: TPath):
        self.paths = self._process_paths(paths)

    def load(self) -> dict[str, t.Any]:
        """Search for locale files on `folderpath`,
        load and parse them to build a big dictionary with all the
        translations data.
        """
        translations = {}

        for path in self.paths:
            for filepath in path.glob("**/*.yaml"):
                if filepath.is_file():
                    logger.debug("Loading translations from %s", filepath)
                    self._update_translations(translations, filepath)

            for filepath in path.glob("**/*.yml"):
                if filepath.is_file():
                    logger.debug("Loading translations from %s", filepath)
                    self._update_translations(translations, filepath)

        return translations

    def _process_paths(self, ipaths: tuple[TPath, ...]) -> list[Path]:
        paths = []
        for ipath in ipaths:
            path = Path(ipath).resolve()
            if not path.exists():
                continue
            if not path.is_dir():
                path = path.parent
            paths.append(path)

        return paths

    def _update_translations(self, translations: dict[str, t.Any], filepath: Path):
        """Update the `translations` dictionary with the translation data
        extracted from the file in `filepath`.
        """
        import poyo

        data = poyo.parse_string(filepath.read_text())

        for locale, trans in data.items():
            locale = format_locale(locale)
            translations.setdefault(locale, {})
            deep_update(translations[locale], trans)


def deep_update(source: dict, overrides: dict) -> dict:
    """Update a nested dictionary or similar mapping.
    Modify `source` in place.
    """
    for key, value in overrides.items():
        if isinstance(value, dict) and value:
            returned = deep_update(source.get(key, {}), value)
            source[key] = returned
        else:
            source[key] = overrides[key]
    return source
