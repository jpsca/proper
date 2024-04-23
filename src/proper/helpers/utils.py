# Based on code from the Werkzeug project, Copyright 2007 Pallets,
# with modifications for the Proper project.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
# notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
# notice, this list of conditions and the following disclaimer in the
# documentation and/or other materials provided with the distribution.
# 3. Neither the name of the copyright holder nor the names of its
# contributors may be used to endorse or promote products derived from
# this software without specific prior written permission.
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
import os
import pkgutil
import re
import sys
import typing as t
import unicodedata
from pathlib import Path


__all__ = (
    "Undefined",
    "secure_filename",
    "ImportStringError",
    "import_string",
    "find_modules",
)

RX_FILENAME_ASCII_STRIP = re.compile(r"[^A-Za-z0-9_.-]")

WINDOWS_DEVICE_FILES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(10)),
    *(f"LPT{i}" for i in range(10)),
}


class Undefined:
    """A default value for when `None` wants to be used as a possible
    default value"""
    pass


def secure_filename(filename: str) -> str:
    r"""Pass it a filename and it will return a secure version of it.

    This filename can then safely be stored on a regular file system and
    passed to `os.path.join`. The filename returned is an ASCII only
    string for maximum portability.

    On windows systems the function also makes sure that the file is not
    named after one of the special device files.

    >>> secure_filename("My cool movie.mov")
    'My_cool_movie.mov'
    >>> secure_filename("../../../etc/passwd")
    'etc_passwd'
    >>> secure_filename('i contain cool \xfcml\xe4uts.txt')
    'i_contain_cool_umlauts.txt'

    The function might return an empty filename. It's your responsibility
    to ensure that the filename is unique and that you abort or
    generate a random filename if the function returned an empty one.

    Arguments:

    - filename: the filename to secure

    """
    filename = unicodedata.normalize("NFKD", filename)
    filename = filename.encode("ascii", "ignore").decode("ascii")

    for sep in os.sep, os.path.altsep:
        if sep:
            filename = filename.replace(sep, " ")

    filename = "_".join(filename.split())
    filename = str(RX_FILENAME_ASCII_STRIP.sub("", filename)).strip("._")

    # on nt a couple of special files are present in each folder. We
    # have to ensure that the target file is not such a filename. In
    # this case we prepend an underline
    if (
        os.name == "nt"
        and filename
        and filename.split(".")[0].upper() in WINDOWS_DEVICE_FILES
    ):
        filename = f"_{filename}"

    return filename


class ImportStringError(ImportError):
    """Provides information about a failed `import_string` attempt."""

    #: String in dotted notation that failed to be imported.
    import_name: str
    #: Wrapped exception.
    exception: BaseException

    def __init__(self, import_name: str, exception: BaseException) -> None:
        self.import_name = import_name
        self.exception = exception
        msg = import_name
        name = ""
        tracked = []
        for part in import_name.replace(":", ".").split("."):
            name = f"{name}.{part}" if name else part
            imported = import_string(name, silent=True)
            if imported:
                tracked.append((name, getattr(imported, "__file__", None)))
            else:
                track = [f"- {n!r} found in {i!r}." for n, i in tracked]
                track.append(f"- {name!r} not found.")
                track_str = "\n".join(track)
                msg = (
                    f"import_string() failed for {import_name!r}. Possible reasons"
                    f" are:\n\n"
                    "- missing __init__.py in a package;\n"
                    "- package or module path not included in sys.path;\n"
                    "- duplicated package or module name taking precedence in"
                    " sys.path;\n"
                    "- missing module, class, function or variable;\n\n"
                    f"Debugged import:\n\n{track_str}\n\n"
                    f"Original exception:\n\n{type(exception).__name__}: {exception}"
                )
                break

        super().__init__(msg)

    def __repr__(self) -> str:
        return f"<{type(self).__name__}({self.import_name!r}, {self.exception!r})>"


def import_string(import_name: str, silent: bool = False) -> t.Any:
    """Imports an object based on a string.

    This is useful if you want to use import paths as endpoints or
    something similar. An import path can be specified either in dotted
    notation (`xml.sax.saxutils.escape`) or with a colon as object
    delimiter (`xml.sax.saxutils:escape`).

    If `silent` is True the return value will be `None` if the import fails.

    Arguments:

    - import_name:
        The dotted name for the object to import.

    - silent:
        If set to `True` import errors are ignored and
        `None` is returned instead.

    """
    import_name = import_name.replace(":", ".")
    try:
        try:
            __import__(import_name)
        except ImportError:
            if "." not in import_name:
                raise
        else:
            return sys.modules[import_name]

        module_name, obj_name = import_name.rsplit(".", 1)
        module = __import__(module_name, globals(), locals(), [obj_name])
        try:
            return getattr(module, obj_name)
        except AttributeError as e:
            raise ImportError(e) from None

    except ImportError as e:
        if not silent:
            raise ImportStringError(import_name, e).with_traceback(
                sys.exc_info()[2]
            ) from None

    return None


def find_modules(
    import_path: str | Path,
    include_packages: bool = False,
    recursive: bool = False,
    *,
    prefix: str = ""
) -> t.Iterator[str]:
    """Finds all the modules below a path.

    This can be useful to automatically import all views so
    that their metaclasses / function decorators have a chance to register
    themselves on the application.

    Packages are not returned unless `include_packages` is `True`. This can
    also recursively list modules but in that case it will import all the
    packages to get the correct load path of that module.

    Arguments:

    - import_path:
        The dotted name for the package to find child modules.

    - include_packages:
        set to `True` if packages should be returned, too.

    - recursive:
        set to `True` if recursion should happen.

    """
    prefix.rstrip(".")
    import_path = Path(import_path).resolve()
    if import_path.is_file():
        import_path = import_path.parent

    for _, modname, ispkg in pkgutil.iter_modules([str(import_path)]):
        if ispkg:
            if include_packages:
                yield modname
            if recursive:
                modpath = import_path / prefix / modname
                yield from find_modules(modpath, include_packages, True, prefix=prefix)
        else:
            yield f"{prefix}.{modname}"
