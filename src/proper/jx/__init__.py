"""
Jx | Copyright (c) Juan-Pablo Scaletti

Vendored from https://github.com/jpscaletti/jx at version 0.16.0
(commit 64d71b7, 2026-09-26), MIT license. From here on this copy is
Proper's own: it can change without a Jx release.
"""

from .catalog import CData, Catalog  # noqa
from .nodes import walk  # noqa
from .parser import parse_ast  # noqa

# The node classes stay in `jx.nodes`. Several of them have names a template
# library is bound to use for something else -- `Component` above all, which
# here is a tag in the tree and not the thing that renders one.
from .exceptions import (
    JxException,  # noqa
    TemplateSyntaxError,  # noqa
    ComponentNotFoundError,  # noqa
    MissingRequiredArgument,  # noqa
    InvalidPropType,  # noqa
    DuplicateDefDeclaration,  # noqa
    InvalidArgument,  # noqa
    InvalidImport,  # noqa
    PathTraversalError,  # noqa
    MaxRecursionDepthError,  # noqa
    FileEncodingError,  # noqa
)
from .tools import CheckError  # noqa
