"""
Jx | Copyright (c) Juan-Pablo Scaletti
"""

import hashlib
import importlib
import shutil
import threading
import typing as t
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from types import CodeType

import jinja2
from jinja2.compiler import CodeGenerator

from . import utils
from .codegen import SAFE_FILTER, JxCodeGenerator, jx_safe
from .component import AssetCache, Component
from .exceptions import ComponentNotFoundError, FileEncodingError
from .meta import extract_metadata
from .parser import JxParser
from .utils import logger


@dataclass(frozen=True, slots=True)
class Folder:
    """A folder registered with `add_folder`, kept so tooling can ask the
    catalog where its components live instead of guessing from source code."""

    path: Path
    prefix: str  # normalized, without the `@` or trailing `/`; "" when unprefixed
    assets: Path | None = None


@dataclass(frozen=True, slots=True)
class CData:
    """
    An immutable snapshot of a compiled component. Never mutated in place:
    a reload builds a new one and swaps it into `Catalog.components`, so any
    reader holding a reference keeps a self-consistent view of one version.
    """

    base_path: Path
    path: Path
    # Only set by `_compile`: it describes the source the snapshot was
    # built from. A registered-but-uncompiled snapshot leaves it at 0.
    mtime: float = 0.0
    code: CodeType | None = None
    tmpl: "jinja2.Template | None" = None
    required: dict[str, type | None] = field(default_factory=dict)  # { attr: type or None }
    optional: dict[str, tuple[t.Any, type | None]] = field(default_factory=dict)  # { attr: (default, type or None) }
    imports: dict[str, str] = field(default_factory=dict)  # { name: relpath }
    css: tuple[str, ...] = ()
    js: tuple[str, ...] = ()
    slots: tuple[str, ...] = ()


def _qualified(obj) -> str:
    """A name for a class or function that is the same in every process."""
    return f"{getattr(obj, '__module__', '')}.{getattr(obj, '__qualname__', obj)}"


def _stable(value) -> str:
    """
    Describe a setting that may be a callable, without using its identity.

    `str()` on a function includes its memory address, which changes on every
    interpreter start. `autoescape=select_autoescape(...)` is the common case —
    it is what Flask sets up — so a digest built on `str()` would give every
    worker process a different one and a shared bytecode cache would never hit.

    The closure is read because that is where `select_autoescape` keeps the
    extension lists; two differently configured callables must not collide.
    """
    if not callable(value):
        return str(value)
    parts = [_qualified(value)]
    try:
        parts.extend(sorted(repr(cell.cell_contents) for cell in value.__closure__ or ()))
    except (AttributeError, ValueError):  # pragma: no cover - empty/odd cells
        pass
    return "|".join(parts)


class Catalog:

    # IDEA: This dict could be replaced by a dict-like object
    # that uses a LRU cache (to limit the memory used)
    # or even a shared Redis/Memcache cache.
    components: dict[str, CData]

    def __init__(
        self,
        folder: str | Path | None = None,
        *,
        jinja_env: jinja2.Environment | None = None,
        extensions: list | None = None,
        filters: dict[str, t.Any] | None = None,
        tests: dict[str, t.Any] | None = None,
        auto_reload: bool = True,
        asset_resolver: Callable[[str, str], str] | None = None,
        file_ext: str = ".jx",
        bytecode_cache: "jinja2.BytecodeCache | None" = None,
        **template_globals: t.Any,
    ) -> None:
        """
        Manager of the components and their global settings.

        Arguments:
            folder:
                Optional folder path to scan for components. It's a shortcut to
                calling `add_folder` when only one is used.
            jinja_env:
                Optional Jinja2 environment to use for rendering.
            extensions:
                Optional extra Jinja2 extensions to add to the environment.
            filters:
                Optional extra Jinja2 filters to add to the environment.
            tests:
                Optional extra Jinja2 tests to add to the environment.
            auto_reload:
                Whether to check the last-modified time of the components files and
                automatically re-process them if they change. The performance impact of
                leaving it on is minimal, but *might* be noticeable when rendering a
                component that uses a large number of child components.
            asset_resolver:
                Optional callable that transforms asset URLs for components from
                folders registered with an `assets` folder.
                Receives `(url, prefix)` and returns the resolved URL.
                Only invoked for components whose prefix has a registered assets
                folder; all other asset URLs pass through unchanged.
            file_ext:
                File extension (including the leading dot) used to discover
                component files within registered folders. Defaults to `.jx`.
                Set to `.jinja` to keep the legacy naming, or any other value
                if you prefer your own convention.
            bytecode_cache:
                Optional `jinja2.BytecodeCache` used to keep compiled
                components between runs, e.g. `jinja2.FileSystemBytecodeCache()`
                or `jinja2.MemcachedBytecodeCache(client)`.

                Compiled components are always cached in memory for the life of
                the process, so this only pays off across process boundaries:
                a restarted server, a worker that did not fork from a warm
                parent, a short-lived process. Compiling is the great majority
                of the cost of loading a component, so where it applies the
                difference is large.

                An environment passed as `jinja_env` that already carries a
                `bytecode_cache` is used as well; this argument takes
                precedence over it.
            **template_globals:
                Variables to make available to all components by default.

        """
        self._lock = threading.RLock()  # Serializes recompilation and folder registration
        self.components = {}
        self._asset_cache: AssetCache = {}
        # Components are immutable, so one instance can serve every render of
        # that component instead of being rebuilt on each access to a child.
        self._component_cache: dict[str, Component] = {}
        self.assets_folders: dict[str, Path] = {}
        self.folders: list[Folder] = []
        self.asset_resolver = asset_resolver
        self.jinja_env = self._make_jinja_env(
            jinja_env=jinja_env,
            globals=template_globals,
            filters=filters,
            tests=tests,
            extensions=extensions,
        )
        if bytecode_cache is not None:
            self.jinja_env.bytecode_cache = bytecode_cache
        self._env_fingerprint = self._fingerprint_env()
        self._auto_reload = auto_reload
        self.file_ext = file_ext
        if folder:
            self.add_folder(folder)

    def add_folder(
        self,
        path: str | Path,
        *,
        prefix: str = "",
        assets: str | Path | None = None,
    ) -> None:
        """
        Add a folder path from which to search for components, optionally under a prefix.

        Components without a prefix can be imported as a path relative to the folder,
        e.g.: `sub/folder/component.jx` or with a path relative to the component
        where it is used: `./folder/component.jx`.

        Relative imports cannot go outside the folder.

        Components added with a prefix must be imported using the `@prefix/`
        syntax: `@prefix/sub/folder/component.jx`. If the importing is
        done from within a component with the prefix itself, a relative
        import can also be used, e.g.: `./component.jx`.

        All the folders added under the same prefix will be treated as if they
        were a single folder. This means if you add two folders, under the same prefix,
        with a component with the same subpath/filename, the one in the folder
        added **first** will be used and the other ignored.

        WARNING: You cannot move or delete components files from the folder after
        calling this method, but you can call it again to add new components added
        to the folder.

        Arguments:
            path:
                Absolute path of the folder with component files.
            prefix:
                Optional path prefix that all the components in the folder
                will have. The default is empty.
            assets:
                Optional path to a folder containing CSS/JS assets for
                this folder's components. When set, the `asset_resolver`
                will be invoked for asset URLs from these components.

        """
        base_path = Path(path).resolve()
        prefix = prefix.replace("\\", "/").strip("./@ ")

        assets_path = None
        if assets is not None:
            if not prefix:
                raise ValueError("Cannot register assets folder without a prefix")
            # Resolved out here because it touches the filesystem; the lock
            # below only needs to cover the shared-state write.
            assets_path = Path(assets).resolve()
        assets_prefix = prefix

        prefix = f"@{prefix}/" if prefix else ""
        if prefix:
            logger.debug(f"Adding folder `{base_path}` with the prefix `{prefix}`")
        else:
            logger.debug(f"Adding folder `{base_path}`")

        with self._lock:
            if assets_path is not None:
                self.assets_folders[assets_prefix] = assets_path
            self.folders.append(
                Folder(path=base_path, prefix=assets_prefix, assets=assets_path)
            )

            for filepath in base_path.rglob(f"*{self.file_ext}"):
                relpath = f"{prefix}{filepath.relative_to(base_path).as_posix()}"
                if relpath in self.components:
                    logger.debug(f"Component already exists: {relpath}")
                    continue
                cdata = CData(base_path=base_path, path=filepath)
                self.components[relpath] = cdata

    add_path = add_folder  # alias

    def add_package(self, package_name: str, *, prefix: str) -> None:
        """
        Register components (and optionally assets) from an installed Python package.

        The package module must expose a `JX_COMPONENTS` attribute pointing to
        the components folder (e.g. via `importlib.resources.files`).
        It may also expose `JX_ASSETS` pointing to an assets folder.

        Arguments:
            package_name:
                The importable package name (e.g. `"my_ui_kit"`).
            prefix:
                Prefix for the components (e.g. `"ui"`).

        """
        mod = importlib.import_module(package_name)
        components = getattr(mod, "JX_COMPONENTS", None)
        if components is None:
            raise ValueError(
                f"Package '{package_name}' does not have a JX_COMPONENTS attribute"
            )
        assets = getattr(mod, "JX_ASSETS", None)
        self.add_folder(components, prefix=prefix, assets=assets)

    def get_assets_folder(self, prefix: str) -> Path | None:
        """
        Return the registered assets folder for a given prefix, or `None`.

        Arguments:
            prefix:
                The prefix to look up (e.g. `"ui"`).

        """
        prefix = prefix.replace("\\", "/").strip("./@ ")
        return self.assets_folders.get(prefix)

    def collect_assets(self, output: str | Path) -> list[tuple[str, Path]]:
        """
        Copy all registered package assets to an output folder.

        For each prefix that has a registered assets folder, files are
        copied to `<output>/<prefix>/`. Returns a list of
        `(prefix, relative_path)` tuples for every file copied.

        Arguments:
            output:
                Destination folder.

        """
        output = Path(output)
        collected: list[tuple[str, Path]] = []
        for prefix, assets_dir in self.assets_folders.items():
            dest_dir = output / prefix if prefix else output
            for src_file in assets_dir.rglob("*"):
                if src_file.is_file():
                    rel = src_file.relative_to(assets_dir)
                    dest = dest_dir / rel
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src_file, dest)
                    collected.append((prefix, rel))
        return collected

    def render(
        self, relpath: str, globals: dict[str, t.Any] | None = None, **kwargs
    ) -> str:
        """
        Render a component with the given relative path and context.

        Arguments:
            relpath:
                The path of the component to render, including the extension, relative to its view folder.
                e.g.: "sub/component.jx". Always use the forward slash (/) as the path separator.
            globals:
                Optional global variables to make available to the component and all its
                imported components.
            **kwargs:
                Keyword arguments to pass to the component.
                They will be available in the component's context but not to its imported components.

        Returns:
            The rendered component as a string.

        """
        relpath = relpath.replace("\\", "/").strip("/")
        co = self.get_component(relpath)
        return co.render(_globals=self._prepare_globals(co, globals), **kwargs)

    def render_string(
        self, source: str, globals: dict[str, t.Any] | None = None, **kwargs
    ) -> str:
        """
        Render a component from a string source.
        Works like `render`, but the component is not cached and cannot do relative imports.

        Arguments:
            source:
                The Jinja2 source code of the component to render.
            globals:
                Optional global variables to make available to the component and all its
                imported components.
            **kwargs:
                Keyword arguments to pass to the component.
                They will be available in the component's context but not to its imported components.

        Returns:
            The rendered component as a string.

        """
        meta = extract_metadata(source, base_path=Path(), fullpath=Path())
        name = "<string>"

        parser = JxParser(name=name, source=source, components=list(meta.imports.keys()))
        parsed_source, slots = parser.parse()

        code = self.jinja_env.compile(source=parsed_source, name=name, filename=name)
        tmpl = jinja2.Template.from_code(self.jinja_env, code, self.jinja_env.globals)

        co = Component(
            relpath=name,
            tmpl=tmpl,
            get_component=self.get_component,
            required=meta.required,
            optional=meta.optional,
            imports=meta.imports,
            css=meta.css,
            js=meta.js,
            slots=slots,
            asset_resolver=self._resolve_asset_url if self.asset_resolver else None,
            # No asset cache: every string component is named `<string>`, so
            # sharing the catalog's cache would serve one source's assets to
            # every other one. Matches this method not caching the template.
        )
        return co.render(_globals=self._prepare_globals(co, globals), **kwargs)

    def has(self, relpath: str) -> bool:
        """Return True if a component with the given relative path is registered.

        Does not read the file or recompile — just checks the catalog index.
        """
        relpath = relpath.replace("\\", "/").strip("/")
        return relpath in self.components

    def get_component_data(self, relpath: str) -> CData:
        """
        Get the component data from the cache.
        If the file has been updated, the component is re-processed.

        Arguments:
            relpath:
                The path of the component to render, including the extension, relative to its view folder.
                e.g.: "sub/component.jx". Always use the forward slash (/) as the path separator.

        """
        # A single dict lookup yields a complete, immutable snapshot, so the
        # common case needs no lock at all.
        cdata = self.components.get(relpath)
        if cdata is None:
            raise ComponentNotFoundError(relpath)
        if self._is_fresh(cdata):
            return cdata

        with self._lock:
            # Another thread may have recompiled it while we waited for the lock.
            cdata = self.components[relpath]
            if self._is_fresh(cdata):
                return cdata
            return self._compile(relpath, cdata)

    def get_component(self, relpath: str) -> Component:
        """
        Instantiate and return a component object by its relative path.

        Arguments:
            relpath:
                The path of the component to render, including the extension, relative to its view folder.
                e.g.: "sub/component.jx". Always use the forward slash (/) as the path separator.

        """
        cdata = self.get_component_data(relpath)
        assert cdata.tmpl is not None

        # Read the cache *after* recompiling: `_compile` replaces the dict, and
        # an entry written into the old one would be lost. A stale entry can
        # never be served, because the template identity has to match.
        component_cache = self._component_cache
        cached = component_cache.get(relpath)
        if cached is not None and cached.tmpl is cdata.tmpl:
            return cached

        component = Component(
            relpath=relpath,
            tmpl=cdata.tmpl,
            get_component=self.get_component,
            required=cdata.required,
            optional=cdata.optional,
            imports=cdata.imports,
            css=cdata.css,
            js=cdata.js,
            slots=cdata.slots,
            asset_resolver=self._resolve_asset_url if self.asset_resolver else None,
            asset_cache=self._get_asset_cache,
            cache_children=not self.auto_reload,
        )
        component_cache[relpath] = component
        return component

    def list_components(self) -> list[str]:
        """
        Return all registered component paths.

        Returns:
            A list of component relative paths (e.g., ["button.jx", "card.jx"]).

        """
        with self._lock:
            return list(self.components.keys())

    def get_signature(self, relpath: str) -> dict[str, t.Any]:
        """
        Return a component's signature including its arguments and metadata.

        Arguments:
            relpath:
                The path of the component, including the extension, relative to its view folder.
                e.g.: "sub/component.jx". Always use the forward slash (/) as the path separator.

        Returns:
            A dictionary containing:
                - required: dict of required argument names mapped to their type (or None)
                - optional: dict of optional arguments mapped to (default_value, type or None)
                - slots: tuple of slot names
                - css: tuple of CSS file URLs
                - js: tuple of JS file URLs

        """
        cdata = self.get_component_data(relpath)
        return {
            "required": cdata.required,
            "optional": cdata.optional,
            "slots": cdata.slots,
            "css": cdata.css,
            "js": cdata.js,
        }

    @property
    def auto_reload(self) -> bool:
        return self._auto_reload

    @auto_reload.setter
    def auto_reload(self, value: bool) -> None:
        """
        Turning auto-reload on has to invalidate the component cache.

        A component built while it was off carries `cache_children=True`, and
        remembers its children without ever stat'ing them again. Left in place,
        those instances would go on ignoring edits after the setting says they
        should not.
        """
        if value == self._auto_reload:
            return
        self._auto_reload = value
        with self._lock:
            self._component_cache = {}

    # Private

    def _get_asset_cache(self) -> AssetCache:
        """The live asset cache. Components ask for it, they do not hold it."""
        return self._asset_cache

    def _is_fresh(self, cdata: CData) -> bool:
        """
        Whether a snapshot can be served as-is, without recompiling.
        """
        if cdata.code is None:
            return False
        # The attribute, not the property: this runs once per component access,
        # and a property read is a Python call.
        if not self._auto_reload:
            return True
        return cdata.path.stat().st_mtime == cdata.mtime

    def _compile(self, relpath: str, cdata: CData) -> CData:
        """
        Recompile a component and publish it. The caller must hold `self._lock`.
        """
        # Read the mtime before the content, never after: if the file is
        # rewritten in between, this records an mtime older than the source we
        # compiled, and `_is_fresh` recompiles once more. Stat'ing afterwards
        # would pair a new mtime with the old source and cache it forever.
        mtime = cdata.path.stat().st_mtime
        try:
            source = cdata.path.read_text(encoding="utf-8")
        except UnicodeDecodeError as err:
            raise FileEncodingError(cdata.path.as_posix()) from err
        meta = extract_metadata(source, base_path=cdata.base_path, fullpath=cdata.path)

        parser = JxParser(
            name=relpath, source=source, components=list(meta.imports.keys())
        )
        parsed_source, slots = parser.parse()
        logger.debug(f"Parsed {relpath}:\n{parsed_source}")
        code = self._compile_code(
            source=parsed_source, name=relpath, filename=cdata.path.as_posix()
        )
        tmpl = jinja2.Template.from_code(self.jinja_env, code, self.jinja_env.globals)

        fresh = CData(
            base_path=cdata.base_path,
            path=cdata.path,
            mtime=mtime,
            code=code,
            tmpl=tmpl,
            required=meta.required,
            optional=meta.optional,
            imports=meta.imports,
            css=meta.css,
            js=meta.js,
            slots=slots,
        )
        # The swap is a single atomic store, so a reader either sees the whole
        # old snapshot or the whole new one, never a mix. Publish it before
        # dropping the asset cache; `get_component` reads the two in the
        # opposite order, which rules out caching stale assets.
        self.components[relpath] = fresh
        self._asset_cache = {}
        # Dropped together: a cached component holds a reference to the asset
        # cache that was live when it was built.
        self._component_cache = {}
        return fresh

    def _fingerprint_env(self) -> str:
        """
        A short digest of everything about the environment that changes the
        code Jinja generates.

        Jinja keys a bytecode bucket by template name and source checksum only,
        so flipping `autoescape` or adding an extension would otherwise keep
        serving the bytecode compiled under the old settings.

        Every part has to be stable across processes, or a shared filesystem or
        memcached cache never hits: a digest that changes each time the process
        starts is the same as having no cache at all.
        """
        env = self.jinja_env
        parts = (
            jinja2.__version__,
            _stable(env.autoescape),
            str(env.optimized),
            env.block_start_string,
            env.block_end_string,
            env.variable_start_string,
            env.variable_end_string,
            env.comment_start_string,
            env.comment_end_string,
            env.line_statement_prefix or "",
            env.line_comment_prefix or "",
            str(env.trim_blocks),
            str(env.lstrip_blocks),
            str(env.keep_trailing_newline),
            env.newline_sequence,
            str(env.is_async),
            ",".join(sorted(env.extensions)),
            # Sandboxing is a codegen decision, not only a runtime one: an
            # intercepted operator compiles to `environment.call_binop(...)`.
            # Sharing a bucket with a plain environment would hand sandboxed
            # rendering code that never calls the sandbox's hooks.
            str(env.sandboxed),
            ",".join(sorted(getattr(env, "intercepted_binops", ()))),
            ",".join(sorted(getattr(env, "intercepted_unops", ()))),
            _qualified(env.code_generator_class),
        )
        return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:12]

    def _compile_code(self, *, source: str, name: str, filename: str) -> CodeType:
        """
        Compile a parsed component, going through the bytecode cache if there
        is one.

        This is the same three-step dance `jinja2.BaseLoader.load` does. Jx
        never goes through a loader, which is why it has to be done here.
        """
        bcc = self.jinja_env.bytecode_cache
        if bcc is None:
            return self.jinja_env.compile(
                source=source, name=name, filename=filename
            )

        bucket = bcc.get_bucket(
            self.jinja_env, f"{name}|{self._env_fingerprint}", filename, source
        )
        if bucket.code is None:
            bucket.code = self.jinja_env.compile(
                source=source, name=name, filename=filename
            )
            bcc.set_bucket(bucket)
        return bucket.code

    def _prepare_globals(
        self, co: Component, globals: dict[str, t.Any] | None = None
    ) -> dict[str, t.Any]:
        """
        Build the globals dict for a top-level render, including asset helpers.
        """
        result = {**(globals or {})}
        result["assets"] = {
            "collect_css": co.collect_css,
            "collect_js": co.collect_js,
            "render_css": co.render_css,
            "render_js": co.render_js,
            "render": co.render_assets,
        }
        return result

    def _resolve_asset_url(self, url: str, prefix: str) -> str:
        """
        Resolve an asset URL through the configured `asset_resolver`.
        Only invoked for prefixes that have a registered assets folder.
        """
        if self.asset_resolver and prefix in self.assets_folders:
            return self.asset_resolver(url, prefix)
        return url

    def _make_jinja_env(
        self,
        *,
        jinja_env: jinja2.Environment | None = None,
        globals: dict[str, t.Any] | None = None,
        filters: dict[str, t.Any] | None = None,
        tests: dict[str, t.Any] | None = None,
        extensions: list | None = None,
    ) -> jinja2.Environment:
        """
        Create a new Jinja2 environment with the specified settings.

        Arguments:
            jinja_env:
                Optional Jinja2 environment to use as a base.
            globals:
                Optional global variables to add to the environment.
            filters:
                Optional extra Jinja2 filters to add to the environment.
            extensions:
                Optional extra Jinja2 extensions to add to the environment.
            tests:
                Optional extra Jinja2 tests to add to the environment.

        """
        # We do `getattr(self, "jinja_env", None)` so a user can
        # subclass and add a `jinja_env` as attribute to the class.
        jinja_env = jinja_env or getattr(self, "jinja_env", None)
        if jinja_env:
            # It could be `jinja_env.overlay()` instead, but that
            # might lead to confusion if the user expects changes
            # to the original environment to be reflected here.
            env = jinja_env
        else:
            env = jinja2.Environment()
            env.autoescape = True
            env.undefined = jinja2.StrictUndefined

        globals = globals or {}
        globals.update(
            {
                # A unique ID generator for HTML elements, see `utils.get_random_id`
                # docstring for more information.
                "_get_random_id": utils.get_random_id,
            }
        )
        env.globals.update(globals)

        filters = filters or {}
        env.filters.update(filters)
        # Registered unconditionally: the marker has to resolve even when the
        # environment keeps its own code generator, see `jx.codegen`.
        env.filters[SAFE_FILTER] = jx_safe

        # Only claim the seat if nobody else is using it. An environment that
        # arrives with its own generator keeps it, and the marker degrades to
        # the identity filter registered above.
        if env.code_generator_class is CodeGenerator:
            env.code_generator_class = JxCodeGenerator

        tests = tests or {}
        env.tests.update(tests)

        extensions = list(extensions or [])
        # The "jinja2.ext.do" extension allows the use of the "do" statement in templates,
        # that execute statements without outputting a value.
        # Is specially useful for manipulating the `attrs` object.
        extensions.append("jinja2.ext.do")
        for ext in extensions:
            env.add_extension(ext)

        return env
