#!/usr/bin/env python3
"""Check the `proper` skill (`skills/proper/`), the docs agents read.

- Every relative link (`file.md`, `file.md#anchor`, `#anchor`) points to a
  file that exists and a heading in it. Anchors are the GitHub slugs of the
  headings (lowercase, spaces to dashes, punctuation removed) or an
  explicit `{#anchor}` on a heading.
- Every doc has a frontmatter with `title` (`name` in `SKILL.md`),
  `description`, a `last_verified` date and the `sources` it was checked
  against: paths of this repository, which must exist.
- Every ```` ```python ```` block parses. A block may be an indented
  fragment, the entries of a dict, or a signature with a bare `*,`; those
  are allowed. `[[app_name]]` is the blueprint's placeholder, not Python:
  the examples say `myapp`.
- Every `from proper... import name` of the blocks resolves (run it with
  `uv run`, so `proper` imports).
- A doc whose `sources` have a commit newer than its `last_verified` is
  reported as possibly stale. That is a warning: the date is updated only
  after reading the whole doc against the code.

```bash
uv run python bin/check-skill.py
```

Prints one line per problem and exits with 1 on an error (not on a stale
doc).
"""
import ast
import importlib
import re
import subprocess
import sys
import textwrap
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills" / "proper"

errors = 0
warnings = 0


def error(rel: Path, msg: str) -> None:
    global errors
    errors += 1
    print(f"{rel}: {msg}")


def warn(rel: Path, msg: str) -> None:
    global warnings
    warnings += 1
    print(f"{rel}: warning: {msg}")


# ---------------------------------------------------------------- frontmatter

def frontmatter(text: str) -> dict | None:
    """The keys of the frontmatter: strings, and a list for `sources`."""
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end < 0:
        return None
    data: dict = {}
    key = ""
    for line in text[4:end].split("\n"):
        if line.startswith("  - ") and key:
            data.setdefault(key, [])
            data[key].append(line[4:].strip())
        elif ":" in line and not line.startswith(" "):
            key, _, value = line.partition(":")
            key = key.strip()
            data[key] = value.strip() or []
    return data


def check_frontmatter(rel: Path, text: str) -> dict:
    data = frontmatter(text)
    if data is None:
        error(rel, "no frontmatter")
        return {}
    name_key = "name" if rel.name == "SKILL.md" else "title"
    for key in (name_key, "description", "last_verified", "sources"):
        if not data.get(key):
            error(rel, f"frontmatter without `{key}`")
    try:
        date.fromisoformat(str(data.get("last_verified", "")))
    except ValueError:
        error(rel, f"`last_verified` is not a date: {data.get('last_verified')!r}")
    sources = data.get("sources")
    if sources and not isinstance(sources, list):
        error(rel, "`sources` must be a list of paths")
        data["sources"] = []
    for src in data.get("sources") or []:
        if not (ROOT / src).exists():
            error(rel, f"source does not exist: {src}")
    return data


# ---------------------------------------------------------------- links

def slug(title: str) -> str:
    s = re.sub(r"[`*]", "", title).strip().lower()
    s = re.sub(r"[^\w\- ]", "", s)
    return s.replace(" ", "-")


def anchors(path: Path) -> set[str]:
    out, in_code = set(), False
    for line in path.read_text().split("\n"):
        if line.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        m = re.match(r"^#{1,6} (.+)$", line)
        if m:
            out.add(slug(m.group(1)))
        for m in re.finditer(r"\{#([\w-]+)\}", line):
            out.add(m.group(1))
    return out


def check_links(f: Path, rel: Path, text: str, cache: dict[Path, set[str]]) -> None:
    for m in re.finditer(r"\]\(([^)\s]+)\)", text):
        target = m.group(1)
        if target.startswith(("http://", "https://", "mailto:")):
            continue
        if target.startswith("#"):
            if target[1:] not in cache[f]:
                error(rel, f"broken anchor {target}")
            continue
        if ".md" not in target:
            continue
        path, _, anchor = target.partition("#")
        dest = (f.parent / path).resolve()
        if not dest.exists():
            error(rel, f"missing file {target}")
            continue
        if anchor and anchor not in cache.get(dest, anchors(dest)):
            error(rel, f"missing anchor {target}")


# ---------------------------------------------------------------- python blocks

BLOCK = re.compile(r"^```python\b[^\n]*\n(.*?)^```", re.M | re.S)
SIGNATURE = re.compile(r"[(,]\s*\*,|^\s*\*,", re.M)


def parse(code: str) -> ast.Module | None:
    """The tree of the block, as written, dedented, or as the entries of a
    dict; `None` if it is a signature with a bare `*,`."""
    code = textwrap.dedent(code)
    for candidate in (code, "{\n" + code + "\n}"):
        try:
            return ast.parse(candidate)
        except SyntaxError:
            pass
    if SIGNATURE.search(code):
        return None
    raise SyntaxError(code)


def check_import(module: str, name: str) -> bool:
    try:
        mod = importlib.import_module(module)
    except Exception:
        return False
    if name == "*" or hasattr(mod, name):
        return True
    try:
        importlib.import_module(f"{module}.{name}")
        return True
    except Exception:
        return False


def check_python(rel: Path, text: str) -> None:
    for m in BLOCK.finditer(text):
        code = m.group(1)
        line = text[: m.start()].count("\n") + 1
        if "[[app_name]]" in code:
            error(rel, f"line {line}: `[[app_name]]` in an example; say `myapp`")
            continue
        try:
            tree = parse(code)
        except SyntaxError:
            try:
                ast.parse(textwrap.dedent(code))
            except SyntaxError as e:
                error(rel, f"line {line + (e.lineno or 1) - 1}: {e.msg}: {(e.text or '').strip()}")
            continue
        if tree is None:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or not node.module:
                continue
            if node.module.split(".")[0] != "proper" or node.level:
                continue
            for alias in node.names:
                if not check_import(node.module, alias.name):
                    error(rel, f"line {line + node.lineno - 1}: `from {node.module} import {alias.name}` does not resolve")


# ---------------------------------------------------------------- freshness

def last_commit(sources: list[str]) -> tuple[str, str]:
    """The date and the path of the newest commit that touched `sources`."""
    newest = ("", "")
    for src in sources:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%cs", "--", f":(literal){src}"],
            cwd=ROOT, capture_output=True, text=True, check=True,
        ).stdout.strip()
        if out > newest[0]:
            newest = (out, src)
    return newest


def check_freshness(rel: Path, data: dict) -> None:
    sources = data.get("sources") or []
    verified = str(data.get("last_verified", ""))
    if not sources or not verified:
        return
    changed, src = last_commit(sources)
    if changed > verified:
        warn(rel, f"verified {verified}, but {src} changed on {changed}")


# ---------------------------------------------------------------- main

def main() -> int:
    files = sorted(SKILL.rglob("*.md"))
    cache = {f: anchors(f) for f in files}
    for f in files:
        rel = f.relative_to(SKILL)
        text = f.read_text()
        data = check_frontmatter(rel, text)
        check_links(f, rel, text, cache)
        check_python(rel, text)
        check_freshness(rel, data)
    print(f"{len(files)} files, {errors} error(s), {warnings} possibly stale")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
